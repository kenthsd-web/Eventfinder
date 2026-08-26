#!/usr/bin/env python3
from __future__ import annotations
import json, re, time, shutil, subprocess, sys, unicodedata, urllib.parse, urllib.request, urllib.error, socket, zipfile
from pathlib import Path
from difflib import SequenceMatcher
from collections import Counter

ROOT = Path.home() / "eventfinder"
DATA = ROOT / "data"
CATALOG = DATA / "venue_catalog.json"
STABLE = DATA / "football_stable_home_venues.json"
MISS = DATA / "football_bulk_catalog_missing.json"
UNRES = DATA / "football_bulk_unresolved.json"
WORK = DATA / "football_bulk_remaining_worklist.json"
CACHE = DATA / "football_nominatim_cache.json"
REPORT = DATA / "football_catalog_pass_report.json"
REMAIN = DATA / "football_catalog_pass_remaining_worklist.json"
LEFTMISS = DATA / "football_catalog_pass_catalog_missing.json"
ZIPOUT = DATA / "football_catalog_pass_remaining.zip"
RELINK = ROOT / "src/sources/football/relink_events_to_venues.py"

UA = "Eventfinder/1.0 venue-verification (personal project; contact: local-user)"


def load_json(p, default):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return default


def save_json(p, obj):
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(p)


def backup(p):
    if p.exists():
        stamp = time.strftime("%Y%m%d_%H%M%S")
        q = p.with_name(p.stem + f"_before_catalog_pass_{stamp}" + p.suffix)
        shutil.copy2(p, q)
        return q
    return None


def norm(s):
    s = unicodedata.normalize("NFKC", str(s or "")).casefold()
    s = s.replace("å", "a").replace("ä", "a").replace("ö", "o")
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return " ".join(s.split())


def base_norm(s):
    s = norm(s)
    # Remove only plan/pitch-level qualifiers, never facility-name words.
    pats = [
        r"\bkonstgras(?:plan)?\b", r"\bnaturgras(?:plan)?\b", r"\bgrasplan\b",
        r"\ba plan\b", r"\bb plan\b", r"\bc plan\b",
        r"\bplan\s*[0-9]+\b", r"\bplan\b",
        r"\b[0-9]+ manna\b", r"\b[0-9]+ m\b", r"\bk\s*[0-9]+\b",
        r"\b11 11 arena\b", r"\b9 9\b", r"\b7 7\b",
    ]
    for p in pats:
        s = re.sub(p, " ", s)
    # A trailing single plan marker/number can be pitch-level.
    s = re.sub(r"\s+(?:a|b|c|1|2|3|4)$", "", s)
    return " ".join(s.split())


def rec_verified(rec):
    if not isinstance(rec, dict):
        return False
    if rec.get("verified") is True:
        return True
    for k in ("status", "verification_status", "verified_status"):
        if str(rec.get(k, "")).casefold() in {"verified", "verifierad", "true", "ok"}:
            return True
    return False


def rec_names(key, rec):
    vals = []
    if key:
        vals.append(str(key))
    if isinstance(rec, dict):
        for k in ("name", "arena", "venue", "canonical", "canonical_name", "canonicalName"):
            v = rec.get(k)
            if isinstance(v, str) and v.strip(): vals.append(v.strip())
        a = rec.get("aliases") or rec.get("alias") or []
        if isinstance(a, str): a = [a]
        if isinstance(a, list): vals.extend(str(x).strip() for x in a if str(x).strip())
    return list(dict.fromkeys(vals))


def rec_city(rec):
    if not isinstance(rec, dict): return ""
    vals=[]
    for k in ("city", "ort", "municipality", "kommun", "locality"):
        v=rec.get(k)
        if isinstance(v,str) and v.strip(): vals.append(v.strip())
    return " ".join(vals)


def catalog_entries(catalog):
    if isinstance(catalog, dict):
        for k,v in catalog.items():
            if isinstance(v,dict): yield str(k), v
    elif isinstance(catalog,list):
        for i,v in enumerate(catalog):
            if isinstance(v,dict):
                key = v.get("name") or v.get("arena") or v.get("venue") or str(i)
                yield str(key), v


def city_ok(target, rec):
    if not target: return True
    rc = rec_city(rec)
    if not rc: return False
    a,b=norm(target),norm(rc)
    return a in b or b in a or SequenceMatcher(None,a,b).ratio() >= 0.82

GENERIC = {"idrottsparken","ringvallen","hagavallen","avallen","prastangen","idrottsplatsen","sportparken","sportfaltet","sportfalt"}

def find_existing(catalog, arena, city):
    na, ba = norm(arena), base_norm(arena)
    exact=[]; base=[]
    for key,rec in catalog_entries(catalog):
        if not rec_verified(rec): continue
        for nm in rec_names(key,rec):
            nn,bb=norm(nm),base_norm(nm)
            if na and nn == na:
                exact.append((key,rec,nm))
            elif ba and bb == ba and len(ba)>=6:
                base.append((key,rec,nm))
    def unique(items, allow_no_city=False):
        # collapse duplicate aliases belonging to same catalog key
        d={}
        for x in items: d[x[0]]=x
        vals=list(d.values())
        cvals=[x for x in vals if city_ok(city,x[1])]
        if len(cvals)==1: return cvals[0]
        if len(vals)==1 and allow_no_city: return vals[0]
        return None
    x=unique(exact, allow_no_city=(base_norm(arena) not in GENERIC))
    if x: return x, "catalog_exact_normalized"
    # Base-name resolution requires a city match unless the name is highly distinctive.
    x=unique(base, allow_no_city=(ba not in GENERIC and len(ba)>=12))
    if x: return x, "catalog_same_site"
    return None, None


def work_city_map(work):
    out={}
    for item in work:
        team=item.get("team","")
        cities=item.get("cities") or {}
        if isinstance(cities,dict) and cities:
            out[team]=max(cities.items(), key=lambda kv: kv[1])[0]
    return out


def get_result_name(r):
    nd=r.get("namedetails") or {}
    vals=[]
    if isinstance(nd,dict):
        for k in ("name","name:sv","official_name","short_name"):
            v=nd.get(k)
            if isinstance(v,str) and v.strip(): vals.append(v.strip())
    dn=str(r.get("display_name") or "")
    if dn: vals.append(dn.split(",",1)[0].strip())
    return vals


def target_city_match(target, r):
    if not target: return 0.5
    a=r.get("address") or {}
    vals=[]
    if isinstance(a,dict):
        for k in ("city","town","village","municipality","county","suburb"):
            v=a.get(k)
            if isinstance(v,str): vals.append(v)
    nt=norm(target)
    if any(nt and (nt in norm(v) or norm(v) in nt) for v in vals): return 1.0
    disp=norm(r.get("display_name",""))
    if nt and nt in disp: return 0.9
    return 0.0


def type_ok(r):
    cat=str(r.get("category") or r.get("class") or "").casefold()
    typ=str(r.get("type") or "").casefold()
    add=str(r.get("addresstype") or "").casefold()
    if cat in {"highway","boundary","railway","waterway","place"}: return False
    if cat == "leisure" and typ in {"pitch","sports_centre","stadium","track","recreation_ground","park"}: return True
    if typ in {"pitch","sports_centre","stadium","recreation_ground"}: return True
    if add in {"pitch","sports_centre","stadium"}: return True
    return False


def score_result(arena, city, r):
    names=get_result_name(r)
    na,ba=norm(arena),base_norm(arena)
    best=0.0
    for nm in names:
        nn,bb=norm(nm),base_norm(nm)
        sims=[SequenceMatcher(None,na,nn).ratio() if na and nn else 0,
              SequenceMatcher(None,ba,bb).ratio() if ba and bb else 0]
        if ba and bb and ba==bb: sims.append(1.0)
        best=max(best,*sims)
    cm=target_city_match(city,r)
    if not type_ok(r): return 0.0,best,cm
    return 0.78*best + 0.22*cm, best, cm


def nominatim_search(q, cache):
    if q in cache: return cache[q]
    params=urllib.parse.urlencode({"q":q,"format":"jsonv2","limit":5,"countrycodes":"se","addressdetails":1,"namedetails":1})
    url="https://nominatim.openstreetmap.org/search?"+params
    req=urllib.request.Request(url, headers={"User-Agent":UA,"Accept-Language":"sv,en;q=0.8"})
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            res=json.loads(resp.read().decode("utf-8"))
            if not isinstance(res,list): res=[]
    except Exception as e:
        res={"_error":str(e)}
    cache[q]=res
    save_json(CACHE,cache)
    # Public Nominatim maximum is 1 request/s. Be conservative.
    time.sleep(1.05)
    return res


def strict_geocode(arena, city, cache):
    queries=[f"{arena}, {city}, Sverige" if city else f"{arena}, Sverige"]
    b=base_norm(arena)
    if b and norm(arena)!=b and b not in {norm(x) for x in queries}:
        queries.append(f"{b}, {city}, Sverige" if city else f"{b}, Sverige")
    allres=[]
    for q in queries[:2]:
        rr=nominatim_search(q,cache)
        if isinstance(rr,list): allres.extend(rr)
        scored=[]
        for r in allres:
            s,nm,cm=score_result(arena,city,r)
            scored.append((s,nm,cm,r))
        scored.sort(key=lambda x:x[0],reverse=True)
        if scored:
            top=scored[0]
            second=scored[1][0] if len(scored)>1 else 0
            # Require strong venue-name agreement, correct locality and a clear winner.
            if top[0]>=0.88 and top[1]>=0.86 and top[2]>=0.9 and (top[0]-second>=0.035 or top[1]>=0.97):
                return top[3], {"score":round(top[0],4),"name_score":round(top[1],4),"city_score":round(top[2],4),"query":q}
    return None,None


def address_from_result(r, fallback_city):
    a=r.get("address") or {}
    if not isinstance(a,dict): a={}
    road=a.get("road") or a.get("pedestrian") or a.get("path") or ""
    hn=a.get("house_number") or ""
    pc=a.get("postcode") or ""
    city=a.get("city") or a.get("town") or a.get("village") or fallback_city or ""
    first=" ".join(x for x in (str(road).strip(),str(hn).strip()) if x)
    second=" ".join(x for x in (str(pc).strip(),str(city).strip()) if x)
    if first and second: return f"{first}, {second}"
    if second: return second
    return str(r.get("display_name") or "")


def municipality_from_result(r, fallback_city):
    a=r.get("address") or {}
    if not isinstance(a,dict): return fallback_city or ""
    return a.get("municipality") or a.get("city") or a.get("town") or fallback_city or ""


def add_catalog(catalog, arena, city, result, source_url, geo_meta):
    lat=float(result["lat"]); lon=float(result["lon"])
    addr=address_from_result(result,city)
    muni=municipality_from_result(result,city)
    rec={
        "name":arena, "arena":arena, "canonical":arena, "canonical_name":arena,
        "aliases":[], "address":addr, "city":city or muni, "ort":city or muni,
        "municipality":muni, "kommun":muni,
        "lat":lat, "lon":lon, "latitude":lat, "longitude":lon,
        "verified":True, "status":"verified", "location_precision":"venue",
        "source":source_url, "verification_source":source_url,
        "geocode_source":"OpenStreetMap Nominatim",
        "geocode_osm_type":result.get("osm_type"), "geocode_osm_id":result.get("osm_id"),
        "geocode_score":geo_meta,
    }
    if isinstance(catalog,dict):
        catalog[arena]=rec
    elif isinstance(catalog,list):
        catalog.append(rec)
    else:
        raise TypeError("venue_catalog.json måste vara dict eller lista")
    save_json(CATALOG,catalog)


def stable_has(stable,team):
    return isinstance(stable,dict) and team in stable and isinstance(stable[team],dict) and str(stable[team].get("status","")).casefold() in {"verified","verifierad","ok"}


def add_stable(stable, team, arena, source_url, method):
    if not isinstance(stable,dict): raise TypeError("football_stable_home_venues.json måste vara ett JSON-objekt")
    stable[team]={"arena":arena,"status":"verified","method":"stable_home_venue","source":source_url,"verification_method":method}
    save_json(STABLE,stable)


def main():
    for p in (CATALOG,STABLE,MISS,WORK):
        if not p.exists():
            print(f"SAKNAS: {p}")
            return 2
    catalog=load_json(CATALOG,{})
    stable=load_json(STABLE,{})
    missing=load_json(MISS,{})
    unresolved=load_json(UNRES,{})
    work=load_json(WORK,[])
    cache=load_json(CACHE,{})
    citymap=work_city_map(work)
    b1=backup(CATALOG); b2=backup(STABLE)

    stats=Counter()
    details={}
    left={}
    items=list(missing.items())
    total=len(items)
    print("======================================")
    print("KATALOGPASS START")
    print("======================================")
    print(f"Lag med verifierad arena men saknad katalogpost: {total}")
    print(f"Event i den gruppen: {sum(int(v.get('count',0)) for _,v in items)}")
    print()

    for i,(team,info) in enumerate(items,1):
        arena=str(info.get("source_arena") or "").strip()
        source=str(info.get("source_url") or "").strip()
        city=citymap.get(team,"")
        count=int(info.get("count",0))
        print(f"{i}/{total} | {team} | {arena}", flush=True)
        if not arena:
            left[team]=info; stats["no_arena"]+=1; continue

        found,method=find_existing(catalog,arena,city)
        if found:
            key,rec,nm=found
            # Stable mapping points to an existing canonical catalog key.
            add_stable(stable,team,key,source,method)
            stats["existing_catalog_teams"]+=1; stats["existing_catalog_events"]+=count
            details[team]={"arena":key,"method":method,"source_arena":arena}
            continue

        result,meta=strict_geocode(arena,city,cache)
        if result:
            add_catalog(catalog,arena,city,result,source,meta)
            add_stable(stable,team,arena,source,"source_arena_plus_strict_nominatim")
            stats["geocoded_teams"]+=1; stats["geocoded_events"]+=count
            details[team]={"arena":arena,"method":"strict_nominatim","meta":meta,"lat":result.get("lat"),"lon":result.get("lon")}
        else:
            left[team]=info
            stats["still_catalog_missing_teams"]+=1; stats["still_catalog_missing_events"]+=count

    save_json(LEFTMISS,left)

    # Filter current remaining worklist using newly verified stable mappings.
    remaining=[]
    for item in work:
        t=item.get("team","")
        if not stable_has(stable,t): remaining.append(item)
    save_json(REMAIN,remaining)

    report={
        "stats":dict(stats), "details":details,
        "catalog_backup":str(b1) if b1 else None, "stable_backup":str(b2) if b2 else None,
        "remaining_worklist_teams":len(remaining), "remaining_worklist_events":sum(int(x.get("count",0)) for x in remaining),
        "catalog_missing_remaining":len(left), "catalog_missing_events_remaining":sum(int(v.get("count",0)) for v in left.values()),
        "source_unresolved_teams":len(unresolved), "source_unresolved_events":sum(int(v.get("count",0)) for v in unresolved.values()) if isinstance(unresolved,dict) else None,
    }
    save_json(REPORT,report)

    print("\n======================================")
    print("KATALOGPASS KLAR")
    print("======================================")
    print(f"Via befintlig verifierad katalog: {stats['existing_catalog_teams']} lag / {stats['existing_catalog_events']} event")
    print(f"Nya strikt geokodade katalogposter: {stats['geocoded_teams']} lag / {stats['geocoded_events']} event")
    print(f"Katalogsaknas efter passet: {len(left)} lag / {sum(int(v.get('count',0)) for v in left.values())} event")
    print(f"Ny restlista: {len(remaining)} lag / {sum(int(x.get('count',0)) for x in remaining)} event")

    relink_out=""
    if RELINK.exists():
        print("\nKör omkoppling...")
        cp=subprocess.run([sys.executable,str(RELINK)],cwd=str(ROOT),capture_output=True,text=True)
        relink_out=(cp.stdout or "")+(cp.stderr or "")
        print(relink_out.strip())
        (DATA/"football_catalog_pass_relink_output.txt").write_text(relink_out,encoding="utf-8")
    else:
        print(f"Relink-script saknas: {RELINK}")

    files=[REMAIN,LEFTMISS,UNRES,REPORT,DATA/"football_catalog_pass_relink_output.txt"]
    with zipfile.ZipFile(ZIPOUT,"w",zipfile.ZIP_DEFLATED) as z:
        for f in files:
            if f.exists(): z.write(f,arcname=f.name)
    print(f"\nLadda upp nästa: {ZIPOUT}")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
