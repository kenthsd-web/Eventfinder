#!/usr/bin/env python3
import concurrent.futures
import html
import json
import re
import shutil
import time
import unicodedata
import urllib.parse
import urllib.request
import zipfile
from difflib import SequenceMatcher
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path.home() / "eventfinder"
DATA = ROOT / "data"
CATALOG = DATA / "venue_catalog.json"
INPUT = DATA / "hockey_venues_unresolved_pass1_2026_27.json"

CONTACT_CACHE = DATA / "hockey_swehockey_contacts_cache_2026_27.json"
GEO_CACHE = DATA / "hockey_geocode_cache_2026_27.json"

OUT_ADDED = DATA / "hockey_venues_added_pass2_2026_27.json"
OUT_UNRES = DATA / "hockey_venues_unresolved_pass2_2026_27.json"
OUT_OFFICIAL = DATA / "hockey_venue_official_addresses_2026_27.json"
OUT_SUMMARY = DATA / "hockey_catalog_pass2_summary_2026_27.json"
OUT_ZIP = DATA / "hockey_catalog_pass2_2026_27.zip"

UA_SWE = "Eventfinder/1.0 hockey venue catalog builder"
UA_GEO = "Eventfinder/1.0 hockey venue geocoder (one-time catalog build)"
CONTACT_URL = "https://stats.swehockey.se/Teams/Info/Contacts/{}"

class TextParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tokens = []
    def handle_data(self, data):
        t = " ".join(html.unescape(data).split())
        if t:
            self.tokens.append(t)

def load_json(p, default):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return default

def save_json(p, obj):
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(p)

def norm(s):
    s = html.unescape(str(s or "")).casefold()
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.replace("–","-").replace("—","-")
    s = re.sub(r"[^a-z0-9 -]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()

def name_score(a,b):
    a,b=norm(a),norm(b)
    if not a or not b: return 0.0
    if a==b: return 1.0
    if len(a)>=5 and a in b: return 0.95
    if len(b)>=5 and b in a: return 0.95
    generic={"ishall","hallen","hall","arena","isstadion","center","centrum","a","b","c"}
    aa=" ".join(x for x in a.split() if x not in generic)
    bb=" ".join(x for x in b.split() if x not in generic)
    return max(
        SequenceMatcher(None,a,b).ratio(),
        SequenceMatcher(None,aa,bb).ratio() if aa and bb else 0.0
    )

def catalog_iter(catalog):
    if isinstance(catalog, dict):
        for k,v in catalog.items():
            if isinstance(v,dict):
                yield k,v
    elif isinstance(catalog,list):
        for v in catalog:
            if isinstance(v,dict):
                name=v.get("name") or v.get("arena") or v.get("canonical_name") or v.get("canonical")
                if name:
                    yield str(name),v

def cat_index(catalog):
    idx={}
    for key,rec in catalog_iter(catalog):
        names={str(key)}
        for f in ("name","arena","canonical_name","canonical"):
            if rec.get(f):
                names.add(str(rec[f]))
        aliases=rec.get("aliases") or []
        if isinstance(aliases,str):
            aliases=[aliases]
        if isinstance(aliases,list):
            names.update(str(x) for x in aliases if x)
        for n in names:
            nn=norm(n)
            if nn:
                idx[nn]=(key,rec)
    return idx

def rec_verified(rec):
    if rec.get("verified") is True:
        return True
    return str(rec.get("status","")).casefold() in {"verified","verifierad","ok","true"}

def add_alias(catalog, rec, alias):
    aliases=rec.get("aliases")
    if not isinstance(aliases,list):
        aliases=[] if not aliases else [str(aliases)]
    if alias and norm(alias) not in {norm(x) for x in aliases}:
        aliases.append(alias)
        rec["aliases"]=aliases
        save_json(CATALOG,catalog)

def fetch_contact(gid):
    url=CONTACT_URL.format(gid)
    req=urllib.request.Request(url,headers={"User-Agent":UA_SWE,"Accept":"text/html"})
    try:
        with urllib.request.urlopen(req,timeout=7) as r:
            raw=r.read().decode("utf-8",errors="replace")
        p=TextParser()
        p.feed(raw)
        if "Contact Information" not in p.tokens:
            return str(gid), []
        return str(gid), p.tokens
    except Exception:
        return str(gid), []

POST_RE=re.compile(r"^\s*(\d{3})\s?(\d{2})\s+(.+?)\s*$", re.I)

def looks_phone(s):
    t=str(s).strip()
    return bool(re.fullmatch(r"[+()\d\s/-]{5,}",t))

def looks_email(s):
    return "@" in str(s)

def clean_city(s):
    s=" ".join(str(s).split()).strip()
    return s.title() if s.isupper() else s

def find_official_address(tokens, venue):
    if not tokens:
        return None
    best=[]
    for i,t in enumerate(tokens):
        sc=name_score(venue,t)
        if sc < 0.985:
            continue
        phone_idx=None
        for j in range(i+1,min(len(tokens),i+5)):
            if norm(tokens[j])=="phone":
                phone_idx=j
                break
        if phone_idx is None:
            continue
        postal_idx=None
        postal=None
        for j in range(phone_idx+1,min(len(tokens),phone_idx+12)):
            m=POST_RE.match(tokens[j])
            if m:
                postal_idx=j
                postal=m
                break
            if norm(tokens[j]) in {"colors","contact","venue"}:
                break
        if not postal:
            continue
        postcode=postal.group(1)+postal.group(2)
        city=clean_city(postal.group(3))
        addr=""
        for j in range(postal_idx-1,phone_idx,-1):
            cand=tokens[j].strip()
            nc=norm(cand)
            if not cand or looks_phone(cand) or looks_email(cand):
                continue
            if nc in {"phone","cellphone","venue","colors"}:
                continue
            if name_score(cand,venue) >= 0.90:
                continue
            addr=cand
            break
        full=", ".join(x for x in (addr, f"{postcode[:3]} {postcode[3:]} {city}") if x)
        best.append({
            "matched_name":t,
            "name_score":round(sc,4),
            "address_line":addr,
            "postcode":postcode,
            "city":city,
            "full_address":full
        })
    if not best:
        return None
    best.sort(key=lambda x:x["name_score"],reverse=True)
    return best[0]

def collect_official_addresses(items, contacts):
    out={}
    for item in items:
        venue=item.get("venue","").strip()
        candidates=[]
        for gid in item.get("group_ids",[]):
            tokens=contacts.get(str(gid)) or []
            hit=find_official_address(tokens,venue)
            if hit:
                hit={**hit,"group_id":gid,"source_url":CONTACT_URL.format(gid)}
                candidates.append(hit)
        if candidates:
            candidates.sort(
                key=lambda x:(bool(x.get("address_line")),x.get("name_score",0)),
                reverse=True
            )
            chosen=candidates[0]
            chosen["corroborating_pages"]=len(candidates)
            out[venue]=chosen
    return out

def city_from_map_address(address):
    s=str(address or "")
    m=re.search(r"\b(\d{3})\s?(\d{2})\s+([^,]+)",s)
    if not m:
        return "",""
    return m.group(1)+m.group(2), clean_city(m.group(3).strip())

def fallback_location(item):
    mp=item.get("map") or {}
    address=str(mp.get("address") or "").strip()
    if not address:
        return None
    pc,city=city_from_map_address(address)
    if not city:
        return None
    return {
        "matched_name":mp.get("map_name") or item.get("venue"),
        "name_score":float(mp.get("name_score") or 1.0),
        "address_line":address.split(",",1)[0].strip(),
        "postcode":pc,
        "city":city,
        "full_address":address,
        "source_url":mp.get("url"),
        "group_id":None,
        "source_kind":"swehockeymap_fallback"
    }

_last_geo=[0.0]
def geocode(query, cache):
    q=" ".join(str(query).split()).strip()
    if not q:
        return []
    if q in cache:
        return cache[q]
    wait=max(0.0,1.05-(time.time()-_last_geo[0]))
    if wait:
        time.sleep(wait)
    params=urllib.parse.urlencode({
        "q":q,
        "format":"jsonv2",
        "addressdetails":1,
        "limit":5,
        "countrycodes":"se"
    })
    url="https://nominatim.openstreetmap.org/search?"+params
    req=urllib.request.Request(url,headers={"User-Agent":UA_GEO})
    try:
        with urllib.request.urlopen(req,timeout=8) as r:
            arr=json.loads(r.read().decode("utf-8"))
    except Exception:
        arr=[]
    _last_geo[0]=time.time()
    cache[q]=arr
    save_json(GEO_CACHE,cache)
    return arr

def result_city(r):
    a=r.get("address") or {}
    return str(a.get("city") or a.get("town") or a.get("village") or a.get("municipality") or "")

def result_postcode(r):
    a=r.get("address") or {}
    return re.sub(r"\s+","",str(a.get("postcode") or ""))

def geocode_location(venue,loc,cache):
    city=loc.get("city","")
    pc=re.sub(r"\s+","",loc.get("postcode",""))
    addr=loc.get("address_line","")
    full=loc.get("full_address","")
    queries=[]
    if addr and not re.search(r"\bbox\b",addr,flags=re.I):
        queries.append(full or f"{addr}, {pc} {city}, Sweden")
    if city:
        queries.append(f"{venue}, {city}, Sweden")
    if city and loc.get("matched_name") and norm(loc["matched_name"]) != norm(venue):
        queries.append(f'{loc["matched_name"]}, {city}, Sweden')
    seen=set()
    for q in queries:
        if not q or q in seen:
            continue
        seen.add(q)
        arr=geocode(q,cache)
        scored=[]
        for r in arr:
            try:
                lat=float(r["lat"]); lon=float(r["lon"])
            except Exception:
                continue
            if not (54.0<=lat<=70.0 and 9.0<=lon<=25.0):
                continue
            rpc=result_postcode(r)
            rcity=result_city(r)
            rn=str(r.get("name") or "")
            disp=str(r.get("display_name") or "")
            postcode_ok=bool(pc and rpc and pc==rpc)
            city_sc=max(name_score(city,rcity),name_score(city,disp)) if city else 0
            venue_sc=max(name_score(venue,rn),name_score(loc.get("matched_name",""),rn))
            address_query=bool(addr and not re.search(r"\bbox\b",addr,flags=re.I) and q==(full or f"{addr}, {pc} {city}, Sweden"))
            safe=(address_query and (postcode_ok or city_sc>=0.82)) or (venue_sc>=0.72 and city_sc>=0.72)
            score=(2.2 if postcode_ok else 0)+(1.5 if address_query else 0)+venue_sc+0.6*city_sc
            if safe:
                scored.append((score,r,{
                    "query":q,
                    "postcode_match":postcode_ok,
                    "city_score":round(city_sc,4),
                    "venue_name_score":round(venue_sc,4),
                    "address_query":address_query
                }))
        if scored:
            scored.sort(key=lambda x:x[0],reverse=True)
            return scored[0][1],scored[0][2]
    return None,None

def add_record(catalog,venue,item,loc,geo,meta):
    lat=float(geo["lat"]); lon=float(geo["lon"])
    city=loc.get("city","")
    pc=loc.get("postcode","")
    addr=loc.get("full_address","").replace(", Sweden","").strip(" ,")
    if not addr:
        addr=f"{pc[:3]} {pc[3:]} {city}".strip()
    aliases=[]
    matched=loc.get("matched_name") or ""
    if matched and norm(matched)!=norm(venue):
        aliases.append(matched)
    official_usage=(item.get("sources") or ["https://stats.swehockey.se/"])[0]
    official_address_source=loc.get("source_url") or official_usage
    precision="venue" if meta.get("venue_name_score",0)>=0.72 else "site"
    rec={
        "name":venue,
        "arena":venue,
        "canonical":venue,
        "canonical_name":venue,
        "aliases":aliases,
        "address":addr,
        "city":city,
        "ort":city,
        "municipality":city,
        "kommun":city,
        "lat":lat,
        "lon":lon,
        "latitude":lat,
        "longitude":lon,
        "verified":True,
        "status":"verified",
        "location_precision":precision,
        "sport":"ishockey",
        "season_verified":"2026-27",
        "source":official_usage,
        "verification_source":official_address_source,
        "verification_method":"official_swehockey_usage_and_official_swehockey_venue_address",
        "geocode_source":"OpenStreetMap Nominatim",
        "geocode_score":meta
    }
    if isinstance(catalog,dict):
        catalog[venue]=rec
    elif isinstance(catalog,list):
        catalog.append(rec)
    else:
        raise TypeError("venue_catalog.json måste vara dict eller lista")
    save_json(CATALOG,catalog)
    return rec

def main():
    if not CATALOG.exists():
        raise SystemExit(f"Saknar {CATALOG}")
    if not INPUT.exists():
        raise SystemExit(f"Saknar {INPUT}")
    backup=DATA/"venue_catalog_before_hockey_catalog_pass2_2026_08_23.json"
    if not backup.exists():
        shutil.copy2(CATALOG,backup)
    catalog=load_json(CATALOG,{})
    items=load_json(INPUT,[])
    contact_cache=load_json(CONTACT_CACHE,{})
    geo_cache=load_json(GEO_CACHE,{})
    group_ids=sorted({int(g) for item in items for g in item.get("group_ids",[])})
    missing_gids=[g for g in group_ids if str(g) not in contact_cache]
    print("======================================")
    print("ISHOCKEY – KATALOGPASS 2 START")
    print("======================================")
    print(f"Hallposter från pass 1: {len(items)}")
    print(f"Relevanta Swehockey-grupper: {len(group_ids)}")
    print(f"Kontakt-sidor att hämta: {len(missing_gids)}")
    print("")
    if missing_gids:
        done=0
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
            futs=[ex.submit(fetch_contact,g) for g in missing_gids]
            for fut in concurrent.futures.as_completed(futs):
                gid,tokens=fut.result()
                contact_cache[gid]=tokens
                done+=1
                if done%10==0 or done==len(missing_gids):
                    print(f"Kontaktregister: {done}/{len(missing_gids)}",flush=True)
        save_json(CONTACT_CACHE,contact_cache)
    official=collect_official_addresses(items,contact_cache)
    locations={}
    for item in items:
        venue=item.get("venue","").strip()
        loc=official.get(venue)
        if loc:
            loc={**loc,"source_kind":"official_swehockey_contacts"}
        else:
            loc=fallback_location(item)
        if loc:
            locations[venue]=loc
    save_json(OUT_OFFICIAL,locations)
    print(f"\nHallposter med säker adress/postort före geokodning: {len(locations)}/{len(items)}")
    print("")
    added=[]
    unresolved=[]
    alias_count=0
    already_count=0
    for i,item in enumerate(items,1):
        venue=item.get("venue","").strip()
        idx=cat_index(catalog)
        hit=idx.get(norm(venue))
        if hit and rec_verified(hit[1]):
            already_count+=1
            print(f"{i}/{len(items)} | REDAN | {venue}",flush=True)
            continue
        loc=locations.get(venue)
        if not loc:
            unresolved.append({**item,"pass2_reason":"no_official_or_exact_directory_address"})
            save_json(OUT_UNRES,unresolved)
            print(f"{i}/{len(items)} | KVAR | {venue} | ingen säker adress",flush=True)
            continue
        matched=loc.get("matched_name") or ""
        if matched:
            idx=cat_index(catalog)
            alias_hit=idx.get(norm(matched))
            if alias_hit and rec_verified(alias_hit[1]):
                add_alias(catalog,alias_hit[1],venue)
                alias_count+=1
                added.append({
                    "venue":venue,"action":"alias_to_existing","catalog_name":alias_hit[0],
                    "location":loc,"official_sources":item.get("sources",[])
                })
                save_json(OUT_ADDED,added)
                print(f"{i}/{len(items)} | ALIAS | {venue} -> {alias_hit[0]}",flush=True)
                continue
        geo,meta=geocode_location(venue,loc,geo_cache)
        if not geo:
            unresolved.append({**item,"pass2_reason":"safe_address_but_no_safe_coordinates","pass2_location":loc})
            save_json(OUT_UNRES,unresolved)
            print(f"{i}/{len(items)} | KVAR | {venue} | adress finns, koordinat ej säker",flush=True)
            continue
        rec=add_record(catalog,venue,item,loc,geo,meta)
        added.append({
            "venue":venue,"action":"added","record":rec,
            "location":loc,"official_sources":item.get("sources",[])
        })
        save_json(OUT_ADDED,added)
        print(f"{i}/{len(items)} | KLAR | {venue} | {rec['city']} | {rec['location_precision']}",flush=True)
    summary={
        "season":"2026-27",
        "input_unresolved":len(items),
        "relevant_group_contact_pages":len(group_ids),
        "venues_with_official_or_exact_directory_address":len(locations),
        "added_or_aliased_pass2":len(added),
        "aliases_to_existing":alias_count,
        "already_verified":already_count,
        "unresolved_after_pass2":len(unresolved),
        "catalog_backup":str(backup),
        "primary_sources":{
            "usage_and_addresses":"stats.swehockey.se official schedule + contact pages",
            "fallback_identity_address":"swehockeymap.se exact arena page",
            "coordinates":"OpenStreetMap Nominatim with postcode/city validation"
        }
    }
    save_json(OUT_SUMMARY,summary)
    with zipfile.ZipFile(OUT_ZIP,"w",zipfile.ZIP_DEFLATED) as z:
        for p in (OUT_ADDED,OUT_UNRES,OUT_OFFICIAL,OUT_SUMMARY):
            if p.exists():
                z.write(p,arcname=p.name)
    print("\n======================================")
    print("ISHOCKEY – KATALOGPASS 2 KLAR")
    print("======================================")
    print(f"Med säker adress/postort: {len(locations)}")
    print(f"Nya/alias verifierade i pass 2: {len(added)}")
    print(f"Alias till befintlig katalogpost: {alias_count}")
    print(f"Redan verifierade: {already_count}")
    print(f"Kvar att lösa djupare: {len(unresolved)}")
    print(f"Katalogbackup: {backup}")
    print(f"Ladda upp nästa: {OUT_ZIP}")

if __name__=="__main__":
    main()
