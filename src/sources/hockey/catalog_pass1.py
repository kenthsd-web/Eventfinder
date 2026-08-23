#!/usr/bin/env python3
import json, re, time, shutil, urllib.request, urllib.parse, urllib.error, html, unicodedata
from pathlib import Path
from difflib import SequenceMatcher
from html.parser import HTMLParser

ROOT = Path.home() / "eventfinder"
DATA = ROOT / "data"
CATALOG = DATA / "venue_catalog.json"
DISC = DATA / "hockey_venues_missing_from_catalog_2026_27.json"

OUT_ADDED = DATA / "hockey_venues_added_pass1_2026_27.json"
OUT_UNRES = DATA / "hockey_venues_unresolved_pass1_2026_27.json"
OUT_FALSE = DATA / "hockey_venue_false_labels_2026_27.json"
OUT_SUMMARY = DATA / "hockey_catalog_pass1_summary_2026_27.json"
OUT_ZIP = DATA / "hockey_catalog_pass1_2026_27.zip"

MAP_CACHE = DATA / "hockey_swehockeymap_cache_2026_27.json"
GEO_CACHE = DATA / "hockey_geocode_cache_2026_27.json"

UA_MAP = "Eventfinder/1.0 hockey venue catalog builder"
UA_GEO = "Eventfinder/1.0 hockey venue geocoder (one-time catalog build)"

FALSE_PATTERNS = [
    r"^\s*[abc]\s*-\s*slutspel\s*$",
    r"^\s*[abc]-slutspel\s*$",
    r"\s-\s*gruppspel\s*$",
    r"^\s*grundserie\s*$",
    r"^\s*grundspel\s*$",
    r"^\s*grupp\s+(?:[123ab]|röd|vit)\s*$",
    r"farsta hockey games.*slutspel",
    r"quality trophy.*grupp",
    r"bauer trophy cup",
    r"^thf cupen$",
    r"tyringe hockey cup",
    r"umeå energi cup",
]

MANUAL_SLUGS = {
    "Hovet, Johanneshov": ["hovet"],
    "Isstadion LF Arena": ["lf-arena"],
    "Stallet Norrköping": ["stallet"],
    "Björkängshallens B-hall": ["bjorkangshallen-b-hall", "bjorkangshallen-b"],
    "Gränbyhallen (B)": ["granbyhallen-b", "granbyhallen-b-hall"],
    "Kungsbacka Ishall (A)": ["kungsbacka-ishall-a", "kungsbacka-ishall"],
    "Monitor ERP Arena (B)": ["monitor-erp-arena-b-hall", "monitor-erp-arena-b"],
    "Mälarhöjdens Ishall 2": ["malarhojdens-ishall-2"],
    "NKT Arena Karlskrona A-Hall": ["nkt-arena-karlskrona-a-hall", "nkt-arena-karlskrona"],
    "NKT Arena Karlskrona B-Hall": ["nkt-arena-karlskrona-b-hall"],
    "Nolia Ishall 1": ["nolia-ishall-1", "noliahallen"],
    "Nolia Ishall 2": ["nolia-ishall-2", "noliahallen-2"],
    "Olympiarinken A-Hall": ["olympiarinken-a-hall", "olympiarinken"],
    "Olympiarinken B-Hall": ["olympiarinken-b-hall"],
    "Skellefteå Kraft Arena B-hallen": ["skelleftea-kraft-arena-b-hallen"],
    "Skellefteå Kraft Arena C-hallen": ["skelleftea-kraft-arena-c-hallen"],
    "Tingvalla Isstadion Rink 1": ["tingvalla-isstadion", "tingvalla-isstadion-rink-1"],
    "Trängens IP Hall A": ["trangens-ip-hall-a"],
    "Vilundaparkens Ishall A": ["vilundaparkens-ishall-a", "vilundaparkens-ishall"],
    "Visionite Arena B-hall": ["visionite-arena-b-hall"],
    "Jössarinken A-hall": ["jossarinken-a-hall", "jossarinken"],
    "Jössarinken B-hall": ["jossarinken-b-hall"],
}

class TextCollector(HTMLParser):
    def __init__(self):
        super().__init__()
        self.nodes = []
        self.h1 = []
        self.h2 = []
        self._tag = None
    def handle_starttag(self, tag, attrs):
        if tag.lower() in ("h1","h2"):
            self._tag = tag.lower()
    def handle_endtag(self, tag):
        if self._tag == tag.lower():
            self._tag = None
    def handle_data(self, data):
        t = " ".join(data.split())
        if not t:
            return
        self.nodes.append(t)
        if self._tag == "h1":
            self.h1.append(t)
        elif self._tag == "h2":
            self.h2.append(t)

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
    s = re.sub(r"\b(is- och sporthall|isstadion)\b", lambda m:m.group(0), s)
    s = re.sub(r"[^a-z0-9 -]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s

def slugify(s):
    s = unicodedata.normalize("NFKD", str(s))
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.lower()
    s = s.replace("&"," and ")
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return re.sub(r"-+", "-", s).strip("-")

def false_label(v):
    lv = str(v).casefold()
    return any(re.search(p, lv, flags=re.I) for p in FALSE_PATTERNS)

def catalog_iter(catalog):
    if isinstance(catalog, dict):
        # Standard Eventfinder shape: name -> record
        for k,v in catalog.items():
            if isinstance(v,dict):
                yield k,v
        return
    if isinstance(catalog,list):
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
        if isinstance(aliases,str): aliases=[aliases]
        if isinstance(aliases,list):
            names.update(str(x) for x in aliases if x)
        for n in names:
            nn=norm(n)
            if nn:
                idx[nn]=(key,rec)
    return idx

def rec_verified(rec):
    if rec.get("verified") is True: return True
    return str(rec.get("status","")).casefold() in {"verified","verifierad","ok","true"}

def add_alias_if_possible(catalog, rec, alias):
    aliases=rec.get("aliases")
    if not isinstance(aliases,list):
        aliases=[] if not aliases else [str(aliases)]
    if alias and norm(alias) not in {norm(x) for x in aliases}:
        aliases.append(alias)
        rec["aliases"]=aliases
        save_json(CATALOG,catalog)

def name_score(a,b):
    a,b=norm(a),norm(b)
    if not a or not b: return 0.0
    if a==b: return 1.0
    if len(a)>=5 and a in b: return 0.94
    if len(b)>=5 and b in a: return 0.94
    # Ignore generic hall suffixes for sponsorship/name variants.
    strip_words={"ishall","hallen","hall","arena","isstadion","a","b","c"}
    aa=" ".join(x for x in a.split() if x not in strip_words)
    bb=" ".join(x for x in b.split() if x not in strip_words)
    return max(SequenceMatcher(None,a,b).ratio(), SequenceMatcher(None,aa,bb).ratio() if aa and bb else 0)

def slug_candidates(venue):
    out=[]
    for m in MANUAL_SLUGS.get(venue,[]):
        out.append(m)
    v=str(venue)
    out.append(slugify(v))
    # Remove comma locality, e.g. Hovet, Johanneshov
    if "," in v:
        out.append(slugify(v.split(",",1)[0]))
    # Parenthetical hall markers
    m=re.search(r"\(([ABC])\)", v, flags=re.I)
    if m:
        letter=m.group(1).lower()
        base=re.sub(r"\s*\([ABC]\)\s*","",v,flags=re.I)
        out.extend([slugify(base+" "+letter+" hall"), slugify(base+" "+letter), slugify(base)])
    # Common wording variants
    replacements = [
        ("hallens-b-hall","hallen-b-hall"),
        ("-ishall-a-hall","-ishall-a"),
        ("-ishall-b-hall","-ishall-b"),
        ("-a-hall",""),
        ("-b-hall",""),
        ("-c-hall",""),
    ]
    base=slugify(v)
    for a,b in replacements:
        if a in base:
            out.append(base.replace(a,b).strip("-"))
    # de-dupe
    seen=set()
    ans=[]
    for s in out:
        s=re.sub(r"-+","-",s).strip("-")
        if s and s not in seen:
            seen.add(s); ans.append(s)
    return ans

def http_get(url, ua, timeout=7):
    req=urllib.request.Request(url,headers={"User-Agent":ua,"Accept":"text/html,application/xhtml+xml"})
    try:
        with urllib.request.urlopen(req,timeout=timeout) as r:
            if getattr(r,"status",200) != 200:
                return None
            return r.read().decode("utf-8",errors="replace")
    except Exception:
        return None

def extract_latlon(raw):
    # Try common JSON/JS encodings used for map marker data.
    patterns=[
        r'["\'](?:lat|latitude)["\']\s*:\s*["\']?([5-6]\d(?:\.\d+)?)["\']?.{0,180}?["\'](?:lng|lon|longitude)["\']\s*:\s*["\']?([12]\d(?:\.\d+)?)',
        r'["\'](?:lng|lon|longitude)["\']\s*:\s*["\']?([12]\d(?:\.\d+)?)["\']?.{0,180}?["\'](?:lat|latitude)["\']\s*:\s*["\']?([5-6]\d(?:\.\d+)?)',
        r'\\?"(?:lat|latitude)\\?"\s*:\s*([5-6]\d(?:\.\d+)?).{0,180}?\\?"(?:lng|lon|longitude)\\?"\s*:\s*([12]\d(?:\.\d+)?)',
    ]
    for i,p in enumerate(patterns):
        m=re.search(p,raw,flags=re.I|re.S)
        if m:
            a,b=float(m.group(1)),float(m.group(2))
            if i==1: a,b=b,a
            if 54.0<=a<=70.0 and 9.0<=b<=25.0:
                return a,b
    return None

def parse_map_page(raw):
    p=TextCollector()
    try: p.feed(raw)
    except Exception: pass
    h1=" ".join(p.h1).strip()
    h2=" ".join(p.h2).strip()
    # Usually H2 is city; ignore generic headings if any.
    city=h2 if h2 and len(h2)<60 and "welcome" not in h2.casefold() else ""
    address=""
    for node in p.nodes:
        if re.search(r"\b\d{3}\s?\d{2}\b",node) and len(node)<180:
            address=node
            break
    coords=extract_latlon(raw)
    return {"map_name":h1,"city":city,"address":address,"coords":coords}

def fetch_map_match(venue,map_cache):
    key=venue
    if key in map_cache:
        return map_cache[key]
    best=None
    for slug in slug_candidates(venue):
        url=f"https://swehockeymap.se/arena/{slug}"
        raw=http_get(url,UA_MAP,timeout=6)
        if not raw:
            continue
        info=parse_map_page(raw)
        if not info["map_name"]:
            continue
        sc=name_score(venue,info["map_name"])
        # We require strong agreement. Manual slugs may be slightly different current/old sponsor names,
        # but those will usually still share the rink identity.
        if sc>=0.78 or norm(info["map_name"]) in norm(venue) or norm(venue) in norm(info["map_name"]):
            info.update({"url":url,"slug":slug,"name_score":round(sc,4)})
            best=info
            break
    map_cache[key]=best
    save_json(MAP_CACHE,map_cache)
    return best

_last_geo=[0.0]
def geocode(query,geo_cache):
    q=" ".join(str(query).split()).strip()
    if not q: return None
    if q in geo_cache:
        return geo_cache[q]
    # OSMF public Nominatim: <= 1 req/s, one thread, cached.
    wait=max(0,1.05-(time.time()-_last_geo[0]))
    if wait: time.sleep(wait)
    params=urllib.parse.urlencode({
        "q":q,"format":"jsonv2","addressdetails":1,"limit":5,"countrycodes":"se"
    })
    url="https://nominatim.openstreetmap.org/search?"+params
    req=urllib.request.Request(url,headers={"User-Agent":UA_GEO})
    try:
        with urllib.request.urlopen(req,timeout=8) as r:
            arr=json.loads(r.read().decode("utf-8"))
    except Exception:
        arr=[]
    _last_geo[0]=time.time()
    geo_cache[q]=arr
    save_json(GEO_CACHE,geo_cache)
    return arr

def geocode_best(venue,mapinfo,geo_cache):
    city=mapinfo.get("city","")
    address=mapinfo.get("address","")
    queries=[]
    if address:
        queries.append(address)
    if mapinfo.get("map_name") and city:
        queries.append(f'{mapinfo["map_name"]}, {city}, Sweden')
    if city:
        queries.append(f"{venue}, {city}, Sweden")
    queries.append(f"{venue}, Sweden")
    seen=set()
    for q in queries:
        if not q or q in seen: continue
        seen.add(q)
        arr=geocode(q,geo_cache)
        scored=[]
        for r in arr or []:
            try:
                lat=float(r["lat"]); lon=float(r["lon"])
            except Exception:
                continue
            if not (54<=lat<=70 and 9<=lon<=25): continue
            disp=str(r.get("display_name",""))
            rrname=str(r.get("name") or "")
            a=r.get("address") or {}
            rcity=a.get("city") or a.get("town") or a.get("village") or a.get("municipality") or ""
            ns=max(name_score(venue,rrname),name_score(mapinfo.get("map_name",""),rrname))
            cityok=1.0
            if city:
                cityok=max(name_score(city,rcity), name_score(city,disp))
            # Exact full street/postcode query is strong even if OSM object's name is generic.
            addr_strong = bool(address and re.search(r"\b\d{3}\s?\d{2}\b",address) and q==address)
            score=(2.0 if addr_strong else 0.0)+ns+0.55*cityok
            scored.append((score,addr_strong,ns,cityok,r,q))
        scored.sort(key=lambda x:x[0],reverse=True)
        if not scored: continue
        top=scored[0]
        # Exact address+postcode in Sweden: accept. Otherwise require a clear named venue/locality match.
        if top[1] or (top[2]>=0.72 and top[3]>=0.72):
            return top[4], {"query":top[5],"name_score":round(top[2],4),"city_score":round(top[3],4),"address_strong":top[1]}
    return None,None

def address_from_geo(r,fallback):
    a=r.get("address") or {}
    road=a.get("road") or a.get("pedestrian") or a.get("path") or a.get("square") or ""
    hn=a.get("house_number") or ""
    pc=a.get("postcode") or ""
    city=a.get("city") or a.get("town") or a.get("village") or a.get("municipality") or ""
    first=" ".join(x for x in (str(road).strip(),str(hn).strip()) if x)
    second=" ".join(x for x in (str(pc).strip(),str(city).strip()) if x)
    return ", ".join(x for x in (first,second) if x) or fallback or str(r.get("display_name",""))

def municipality_from_geo(r,city):
    a=r.get("address") or {}
    return a.get("municipality") or a.get("city") or a.get("town") or a.get("village") or city or ""

def add_catalog(catalog,venue,mapinfo,lat,lon,address,source_url,geo_source,geo_meta):
    city=mapinfo.get("city","")
    muni=city
    aliases=[]
    mapname=mapinfo.get("map_name","")
    if mapname and norm(mapname)!=norm(venue):
        aliases.append(mapname)
    rec={
        "name":venue,"arena":venue,"canonical":venue,"canonical_name":venue,
        "aliases":aliases,
        "address":address,"city":city,"ort":city,
        "municipality":muni,"kommun":muni,
        "lat":float(lat),"lon":float(lon),"latitude":float(lat),"longitude":float(lon),
        "verified":True,"status":"verified","location_precision":"venue",
        "source":source_url,
        "verification_source":mapinfo.get("url"),
        "verification_method":"official_swehockey_usage_plus_swehockeymap_location",
        "geocode_source":geo_source,
        "geocode_score":geo_meta,
        "sport":"ishockey",
        "season_verified":"2026-27",
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
    if not CATALOG.exists(): raise SystemExit(f"Saknar {CATALOG}")
    if not DISC.exists(): raise SystemExit(f"Saknar {DISC}")

    backup=DATA/"venue_catalog_before_hockey_catalog_pass1_2026_08_23.json"
    if not backup.exists(): shutil.copy2(CATALOG,backup)

    catalog=load_json(CATALOG,{})
    items=load_json(DISC,[])
    map_cache=load_json(MAP_CACHE,{})
    geo_cache=load_json(GEO_CACHE,{})

    false_items=[]
    real=[]
    for item in items:
        if false_label(item.get("venue","")):
            false_items.append(item)
        else:
            real.append(item)
    save_json(OUT_FALSE,false_items)

    print("======================================")
    print("ISHOCKEY – KATALOGPASS 1 START")
    print("======================================")
    print(f"Discovery saknade totalt: {len(items)}")
    print(f"Felaktiga tävlingsetiketter bortfiltrerade: {len(false_items)}")
    print(f"Verkliga hallar att behandla: {len(real)}")
    print("")

    added=[]
    unresolved=[]
    already=0

    for i,item in enumerate(real,1):
        venue=item.get("venue","").strip()
        idx=cat_index(catalog)
        hit=idx.get(norm(venue))
        if hit and rec_verified(hit[1]):
            already+=1
            print(f"{i}/{len(real)} | REDAN | {venue}",flush=True)
            continue

        print(f"{i}/{len(real)} | SÖKER | {venue}",flush=True)
        mapinfo=fetch_map_match(venue,map_cache)
        if not mapinfo:
            unresolved.append({**item,"reason":"no_strong_swehockeymap_match"})
            save_json(OUT_UNRES,unresolved)
            continue

        # If the matched arena name already exists verified, append current Swehockey name as alias.
        idx=cat_index(catalog)
        alias_hit=idx.get(norm(mapinfo.get("map_name","")))
        if alias_hit and rec_verified(alias_hit[1]):
            add_alias_if_possible(catalog,alias_hit[1],venue)
            already+=1
            added.append({
                "venue":venue,"action":"alias_to_existing",
                "catalog_name":alias_hit[0],"map":mapinfo,
                "official_sources":item.get("sources",[])
            })
            save_json(OUT_ADDED,added)
            print(f"    -> ALIAS till befintlig: {alias_hit[0]}",flush=True)
            continue

        coords=mapinfo.get("coords")
        geo=None; geometa=None
        if coords:
            lat,lon=coords
            geo_source="swehockeymap.se map coordinates"
            address=mapinfo.get("address","")
            if not address:
                # Coordinates are sufficient; retain readable city-level address until a street is found.
                address=mapinfo.get("city","")
        else:
            geo,geometa=geocode_best(venue,mapinfo,geo_cache)
            if not geo:
                unresolved.append({**item,"reason":"location_found_but_no_safe_coordinates","map":mapinfo})
                save_json(OUT_UNRES,unresolved)
                continue
            lat=float(geo["lat"]); lon=float(geo["lon"])
            geo_source="OpenStreetMap Nominatim"
            address=mapinfo.get("address") or address_from_geo(geo,mapinfo.get("city",""))

        # Require city from rink directory; otherwise keep unresolved rather than guessing.
        if not mapinfo.get("city"):
            unresolved.append({**item,"reason":"no_city_from_arena_source","map":mapinfo})
            save_json(OUT_UNRES,unresolved)
            continue

        rec=add_catalog(
            catalog,venue,mapinfo,lat,lon,address,
            (item.get("sources") or ["https://stats.swehockey.se/"])[0],
            geo_source,geometa
        )
        added.append({
            "venue":venue,"action":"added","record":rec,"map":mapinfo,
            "official_sources":item.get("sources",[])
        })
        save_json(OUT_ADDED,added)
        print(f"    -> KLAR | {mapinfo.get('city')} | {address}",flush=True)

    summary={
        "season":"2026-27",
        "discovery_missing_input":len(items),
        "false_competition_labels_removed":len(false_items),
        "real_hockey_venues_processed":len(real),
        "added_or_aliased_this_pass":len(added),
        "already_verified_during_pass":already,
        "unresolved_after_pass":len(unresolved),
        "catalog_backup":str(backup),
        "sources":{
            "usage":"stats.swehockey.se official schedules",
            "arena_identity_address":"swehockeymap.se",
            "coordinates":"swehockeymap map data when available; otherwise OpenStreetMap Nominatim"
        }
    }
    save_json(OUT_SUMMARY,summary)

    import zipfile
    with zipfile.ZipFile(OUT_ZIP,"w",zipfile.ZIP_DEFLATED) as z:
        for p in (OUT_ADDED,OUT_UNRES,OUT_FALSE,OUT_SUMMARY):
            if p.exists(): z.write(p,arcname=p.name)

    print("\n======================================")
    print("ISHOCKEY – KATALOGPASS 1 KLAR")
    print("======================================")
    print(f"Felaktiga etiketter borttagna: {len(false_items)}")
    print(f"Nya/alias verifierade: {len(added)}")
    print(f"Redan verifierade under passet: {already}")
    print(f"Kvar att lösa manuellt/djupare: {len(unresolved)}")
    print(f"Katalogbackup: {backup}")
    print(f"Ladda upp nästa: {OUT_ZIP}")

if __name__=="__main__":
    main()
