#!/usr/bin/env python3
from __future__ import annotations

import json, re, shutil, subprocess, sys, time, unicodedata
import urllib.parse, urllib.request
import zipfile
from collections import Counter
from difflib import SequenceMatcher
from pathlib import Path

ROOT = Path.home() / "eventfinder"
DATA = ROOT / "data"
CATALOG = DATA / "venue_catalog.json"
STABLE = DATA / "football_stable_home_venues.json"
MATCHMAP = DATA / "football_match_venues.json"
WORK = DATA / "football_deep_pass_remaining_worklist.json"
MISSING = DATA / "football_deep_pass_catalog_missing.json"
UNRES = DATA / "football_deep_pass_unresolved.json"
CACHE = DATA / "football_nominatim_cache.json"
OSM_CACHE = DATA / "football_overpass_sports_cache.json"
REPORT = DATA / "football_deep_pass2_report.json"
REMAIN = DATA / "football_deep_pass2_remaining_worklist.json"
LEFTMISS = DATA / "football_deep_pass2_catalog_missing.json"
LEFTUNRES = DATA / "football_deep_pass2_unresolved.json"
RELINK_OUT = DATA / "football_deep_pass2_relink_output.txt"
ZIPOUT = DATA / "football_deep_pass2_remaining.zip"
RELINK = ROOT / "src/sources/football/relink_events_to_venues.py"

UA = "Eventfinder/1.0 venue-verification (personal project; contact: local-user)"

MANUAL_STABLE = {
    # Tidigare manuellt verifierade 2026-källor som behöver en ny katalogchans.
    "Hovås Billdal IF": {
        "arena": "Hovåsvallen 1 Gräs",
        "source": "https://www.svenskalag.se/hovasbilldal-dam/matcher?seasonYear=2026",
        "city": "Göteborg",
    },
    "Gimo IF FK": {
        "arena": "Idrottsgården 1",
        "source": "https://www.laget.se/GimoIFFK-Fotboll-Dam",
        "city": "Gimo",
    },
    "Färjestadens GOIF": {
        "arena": "Tallhöjdens IP 1, Färjestaden",
        "source": "https://farjestadensgoif.web.sportadmin.se/match/?ID=361093&kommande=1",
        "city": "Färjestaden",
    },
    "Färjestadens GOIF B": {
        "arena": "Tallhöjdens IP 1, Färjestaden",
        "source": "https://farjestadensgoif.web.sportadmin.se/match/?ID=361101&kommande=1",
        "city": "Färjestaden",
    },
    "IFK Kalmar C": {
        "arena": "Gröndals IP 1, Kalmar",
        "source": "https://ifkkalmar.web.sportadmin.se/match/?GID=0&ID=555053",
        "city": "Kalmar",
    },
    "Ifö Bromölla IF": {
        "arena": "Strandängens IP A-plan",
        "source": "https://www.ifobif.se/match/?GID=0&ID=524925",
        "city": "Bromölla",
    },
    "Sjöstaden DFF Karlskrona": {
        "arena": "Hästö IP 1",
        "source": "https://www.sjostadendff.se/sjostadendffkarlskrona-div2/matcher?seasonYear=2026",
        "city": "Karlskrona",
    },

    # Direkt verifierade lagvarianter från 2026-matchprogram.
    "Hertzöga BK 2": {
        "arena": "Ilanda IP A-plan",
        "source": "https://www.hertzogabk.se/match/?GID=0&ID=171375",
        "city": "Karlstad",
    },
    "IF Team Hudik 2": {
        "arena": "Glysis Sparbanken Arena",
        "source": "https://www.laget.se/teamhudiku/Division/Game/577788/12316640",
        "city": "Hudiksvall",
    },
    "Mariehem SK 2": {
        "arena": "MSK Arena",
        "source": "https://www.mskumea.com/match/?GID=0&ID=219878",
        "city": "Umeå",
    },
    "Norrstrands IF U": {
        "arena": "ICA Maxi Välsviken Arena A-plan",
        "source": "https://www.norrstrandsif.com/match/?GID=0&ID=176804",
        "city": "Karlstad",
    },
    "Grevie GIK (9m9)": {
        "arena": "Grevieparken A-plan",
        "source": "https://www.greviegik.se/greviegik-dam",
        "city": "Grevie",
    },
    "Öckerö IF (B)": {
        "arena": "Prästängen 1 Konstgräs",
        "source": "https://www.ockeroif.se/match/?GID=0&ID=168725",
        "city": "Öckerö",
    },
    "Ytterby IS (B)": {
        "arena": "Ytterns IP 1 Konstgräs",
        "source": "https://www.laget.se/JuniorlagDamerFotboll/Division/Game/568251/12233606",
        "city": "Ytterby",
    },
}

MANUAL_MATCH = {
    # Högs/Iggesund växlar hemmaplan - exakt matchkoppling.
    "6607998": {"arena":"Kungsvallen","team":"Högs SK / Iggesunds IK","source":"https://www.iggesundsik.se/match/?ID=55213","city":"Hudiksvall"},
    "6608011": {"arena":"Movallen","team":"Högs SK / Iggesunds IK","source":"https://www.iggesundsik.se/match/?ID=55213","city":"Iggesund"},
    "6608015": {"arena":"Kungsvallen","team":"Högs SK / Iggesunds IK","source":"https://www.iggesundsik.se/match/?ID=55213","city":"Hudiksvall"},
    "6608019": {"arena":"Kungsvallen","team":"Högs SK / Iggesunds IK","source":"https://www.iggesundsik.se/match/?ID=55213","city":"Hudiksvall"},

    # Västerås växlar mellan Hitachi Energy Arena och Råby IP.
    "6705142": {"arena":"Hitachi Energy Arena","team":"IFK Västerås FK Dam","source":"https://www.ifk.nu/match/?ID=544702","city":"Västerås"},
    "6705148": {"arena":"Råby IP 3 (konstgräs)","team":"IFK Västerås FK Dam","source":"https://www.ifk.nu/match/?ID=544702","city":"Västerås"},
    "6705156": {"arena":"Hitachi Energy Arena","team":"IFK Västerås FK Dam","source":"https://www.ifk.nu/match/?ID=544702","city":"Västerås"},
    "6705169": {"arena":"Råby IP 3 (konstgräs)","team":"IFK Västerås FK Dam","source":"https://www.ifk.nu/match/?ID=544702","city":"Västerås"},

    # Djurö-Vindö: verifierad matchserie på Sjösalavallen.
    "6603944": {"arena":"Sjösalavallen 1","team":"Djurö-Vindö IF","source":"https://www.dvif.se/nyheter/?ID=17091&NID=1354287","city":"Djurhamn"},
    "6603964": {"arena":"Sjösalavallen 1","team":"Djurö-Vindö IF","source":"https://solbergabk.web.sportadmin.se/match/?GID=0&ID=221351","city":"Djurhamn"},
    "6603974": {"arena":"Sjösalavallen 1","team":"Djurö-Vindö IF","source":"https://www.dvif.se/start/?ID=17091","city":"Djurhamn"},
    "6603984": {"arena":"Sjösalavallen 1","team":"Djurö-Vindö IF","source":"https://www.dvif.se/start/?ID=17091","city":"Djurhamn"},

    # Göteborgs FF (B) byter plan i sista hemmamatchen.
    "6533867": {"arena":"Gröna Vallen 1","team":"Göteborgs FF (B)","source":"https://www.svenskalag.se/gffdam/matcher","city":"Göteborg"},
    "6533878": {"arena":"Gröna Vallen 1","team":"Göteborgs FF (B)","source":"https://www.svenskalag.se/gffdam/matcher","city":"Göteborg"},
    "6533890": {"arena":"Gröna Vallen 1","team":"Göteborgs FF (B)","source":"https://www.svenskalag.se/gffdam/matcher","city":"Göteborg"},
    "6533898": {"arena":"Heden 1 Konstgräs","team":"Göteborgs FF (B)","source":"https://www.svenskalag.se/gffdam/matcher","city":"Göteborg"},

    # Sävedalens IF (B): tre Vallhamra-matcher, sista på Furulundsplan.
    "6533869": {"arena":"Vallhamra 2 Konstgräs","team":"Sävedalens IF (B)","source":"https://www.svenskalag.se/savedalensif/kalender/2026/september","city":"Partille"},
    "6533872": {"arena":"Vallhamra 2 Konstgräs","team":"Sävedalens IF (B)","source":"https://www.svenskalag.se/savedalensif/kalender/2026/september","city":"Partille"},
    "6533882": {"arena":"Vallhamra 2 Konstgräs","team":"Sävedalens IF (B)","source":"https://www.svenskalag.se/savedalensif/kalender/2026/september","city":"Partille"},
    "6533897": {"arena":"Furulundsplan 1 Konstgräs","team":"Sävedalens IF (B)","source":"https://www.svenskalag.se/SIFDamer/matcher","city":"Partille"},

    "6606225": {"arena":"Sjöavallen 1, Fredriksdal","team":"Fredriksdal/Äng","source":"https://www.svenskfotboll.se/","city":"Fredriksdal"},
}

GENERIC = {
    "idrottsparken","ringvallen","hagavallen","avallen","prastangen",
    "idrottsplatsen","sportparken","sportfaltet","sportfalt","movallen",
    "kungsvallen","solhaga","bruksparken","bruksplan","vallen"
}
UNSAFE_ARENA_PATTERNS = (
    r"/",
    r"\b(?:18|19|20)\d{2}\s*[-–]\s*\d{2,4}\b",
    r"\b(?:18|19|20)\d{2}\s*[-–]\b",
)

def load_json(p, default):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return default

def save_json(p, obj):
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp=p.with_suffix(p.suffix+".tmp")
    tmp.write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding="utf-8")
    tmp.replace(p)

def backup(p,tag):
    if not p.exists(): return None
    stamp=time.strftime("%Y%m%d_%H%M%S")
    q=p.with_name(f"{p.stem}_before_{tag}_{stamp}{p.suffix}")
    shutil.copy2(p,q)
    return q

def norm(s):
    s=unicodedata.normalize("NFKC",str(s or "")).casefold()
    s=s.replace("å","a").replace("ä","a").replace("ö","o")
    s=re.sub(r"[^a-z0-9]+"," ",s)
    return " ".join(s.split())

def base_norm(s):
    s=norm(s)
    pats=[
        r"\bkonstgras(?:plan)?\b",r"\bnaturgras(?:plan)?\b",r"\bgras(?:plan)?\b",
        r"\ba plan\b",r"\bb plan\b",r"\bc plan\b",r"\bplan\s*[0-9]+\b",r"\bplan\b",
        r"\b[0-9]+ manna\b",r"\b[0-9]+manna\b",r"\bk\s*[0-9]+\b",
        r"\b11 11 arena\b",r"\b9 9\b",r"\b7 7\b",
    ]
    for p in pats: s=re.sub(p," ",s)
    s=re.sub(r"\s+(?:a|b|c|1|2|3|4)$","",s)
    return " ".join(s.split())

def is_generic(arena):
    b=base_norm(arena)
    return b in GENERIC or len(b)<6

def rec_verified(rec):
    if not isinstance(rec,dict): return False
    if rec.get("verified") is True: return True
    for k in ("status","verification_status","verified_status"):
        if str(rec.get(k,"")).casefold() in {"verified","verifierad","true","ok"}:
            return True
    return False

def rec_names(key,rec):
    vals=[]
    if key: vals.append(str(key))
    if isinstance(rec,dict):
        for k in ("name","arena","venue","canonical","canonical_name","canonicalName"):
            v=rec.get(k)
            if isinstance(v,str) and v.strip(): vals.append(v.strip())
        aliases=rec.get("aliases") or rec.get("alias") or []
        if isinstance(aliases,str): aliases=[aliases]
        if isinstance(aliases,list): vals.extend(str(x).strip() for x in aliases if str(x).strip())
    return list(dict.fromkeys(vals))

def rec_city(rec):
    if not isinstance(rec,dict): return ""
    vals=[]
    for k in ("city","ort","municipality","kommun","locality"):
        v=rec.get(k)
        if isinstance(v,str) and v.strip(): vals.append(v.strip())
    return " ".join(vals)

def catalog_entries(catalog):
    if isinstance(catalog,dict):
        for k,v in catalog.items():
            if isinstance(v,dict): yield str(k),v
    elif isinstance(catalog,list):
        for i,v in enumerate(catalog):
            if isinstance(v,dict):
                key=v.get("name") or v.get("arena") or v.get("venue") or str(i)
                yield str(key),v

def city_match(target,text):
    if not target: return True
    a,b=norm(target),norm(text)
    if not a or not b: return False
    return a in b or b in a or SequenceMatcher(None,a,b).ratio()>=0.82

def find_existing(catalog,arena,city=""):
    na,ba=norm(arena),base_norm(arena)
    exact={}; base={}
    for key,rec in catalog_entries(catalog):
        if not rec_verified(rec): continue
        for nm in rec_names(key,rec):
            nn,bb=norm(nm),base_norm(nm)
            if na and nn==na: exact[key]=(key,rec,nm)
            elif ba and bb==ba and len(ba)>=5: base[key]=(key,rec,nm)
    exact_city=[x for x in exact.values() if city_match(city,rec_city(x[1]))]
    if len(exact_city)==1: return exact_city[0],"catalog_exact_city"
    if len(exact)==1 and not is_generic(arena): return next(iter(exact.values())),"catalog_exact_unique"
    base_city=[x for x in base.values() if city_match(city,rec_city(x[1]))]
    if len(base_city)==1: return base_city[0],"catalog_same_site_city"
    if len(base)==1 and not is_generic(arena) and len(ba)>=10:
        return next(iter(base.values())),"catalog_same_site_unique"
    return None,None

def work_city_map(work):
    out={}
    for item in work if isinstance(work,list) else []:
        team=str(item.get("team",""))
        cities=item.get("cities") or {}
        if isinstance(cities,dict) and cities:
            out[team]=max(cities.items(),key=lambda kv:kv[1])[0]
    return out

def request_json(url,timeout=10,data=None):
    req=urllib.request.Request(url,data=data,headers={"User-Agent":UA,"Accept-Language":"sv,en;q=0.8"})
    with urllib.request.urlopen(req,timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))

def nominatim_search(q,cache,viewbox=None,bounded=False,limit=8):
    key=json.dumps(["search",q,viewbox,bounded,limit],ensure_ascii=False)
    if key in cache: return cache[key]
    params={"q":q,"format":"jsonv2","limit":limit,"countrycodes":"se","addressdetails":1,"namedetails":1}
    if viewbox:
        params["viewbox"]=viewbox
        if bounded: params["bounded"]=1
    url="https://nominatim.openstreetmap.org/search?"+urllib.parse.urlencode(params)
    try:
        res=request_json(url,timeout=8)
        if not isinstance(res,list): res=[]
    except Exception as e:
        res={"_error":str(e)}
    cache[key]=res
    save_json(CACHE,cache)
    time.sleep(1.05)
    return res

def nominatim_reverse(lat,lon,cache):
    key=json.dumps(["reverse",round(float(lat),6),round(float(lon),6)])
    if key in cache: return cache[key]
    params={"lat":lat,"lon":lon,"format":"jsonv2","zoom":18,"addressdetails":1}
    url="https://nominatim.openstreetmap.org/reverse?"+urllib.parse.urlencode(params)
    try:
        res=request_json(url,timeout=8)
        if not isinstance(res,dict): res={}
    except Exception as e:
        res={"_error":str(e)}
    cache[key]=res
    save_json(CACHE,cache)
    time.sleep(1.05)
    return res

def result_names(r):
    vals=[]
    nd=r.get("namedetails") or {}
    if isinstance(nd,dict):
        for k in ("name","name:sv","official_name","short_name","alt_name","loc_name"):
            v=nd.get(k)
            if isinstance(v,str) and v.strip(): vals.append(v.strip())
    dn=str(r.get("display_name") or "")
    if dn: vals.append(dn.split(",",1)[0].strip())
    return list(dict.fromkeys(vals))

def result_city_score(city,r):
    if not city: return 0.5
    vals=[]
    a=r.get("address") or {}
    if isinstance(a,dict):
        for k in ("city","town","village","municipality","county","suburb","hamlet"):
            v=a.get(k)
            if isinstance(v,str) and v.strip(): vals.append(v.strip())
    nc=norm(city)
    if any(nc and (nc in norm(v) or norm(v) in nc) for v in vals): return 1.0
    if nc and nc in norm(r.get("display_name","")): return 0.9
    return 0.0

def sports_type_ok(r):
    # OSM/Nominatim klassificerar svenska idrottsanläggningar ojämnt.
    # Avvisa uppenbart fel typ, men låt stark namn+geografiträff avgöra.
    cat=str(r.get("category") or r.get("class") or "").casefold()
    typ=str(r.get("type") or "").casefold()
    add=str(r.get("addresstype") or "").casefold()
    if cat in {"boundary","railway","waterway"}:
        return False
    if cat=="highway" and typ not in {"services","rest_area"}:
        return False
    if add in {"country","state","county"}:
        return False
    return True

def name_score(arena,names):
    na,ba=norm(arena),base_norm(arena)
    best=0.0
    for nm in names:
        nn,bb=norm(nm),base_norm(nm)
        if na and nn==na: best=max(best,1.0)
        if ba and bb==ba and ba: best=max(best,0.995)
        if na and nn: best=max(best,SequenceMatcher(None,na,nn).ratio())
        if ba and bb: best=max(best,SequenceMatcher(None,ba,bb).ratio())
    return best

def haversine_km(lat1,lon1,lat2,lon2):
    from math import radians,sin,cos,asin,sqrt
    p1,p2=radians(float(lat1)),radians(float(lat2))
    dphi=radians(float(lat2)-float(lat1))
    dl=radians(float(lon2)-float(lon1))
    a=sin(dphi/2)**2+cos(p1)*cos(p2)*sin(dl/2)**2
    return 6371.0088*2*asin(min(1,sqrt(a)))

def score_nominatim(arena,city,r,cc=None):
    if not sports_type_ok(r): return (0,0,0,9999)
    ns=name_score(arena,result_names(r))
    cs=result_city_score(city,r)
    dist=9999.0
    if cc:
        try: dist=haversine_km(cc["lat"],cc["lon"],float(r["lat"]),float(r["lon"]))
        except Exception: pass
    geo=1.0 if dist<=12 else 0.9 if dist<=25 else 0.72 if dist<=45 else 0.45 if dist<=70 else 0.0
    return (0.76*ns+0.14*max(cs,geo)+0.10*geo,ns,max(cs,geo),dist)

def city_center(city,cache):
    if not city: return None
    rr=nominatim_search(f"{city}, Sverige",cache,limit=3)
    if not isinstance(rr,list): return None
    for r in rr:
        try:
            lat=float(r["lat"]); lon=float(r["lon"])
        except Exception:
            continue
        bb=r.get("boundingbox")
        viewbox=None
        if isinstance(bb,list) and len(bb)==4:
            try:
                south,north,west,east=map(float,bb)
                viewbox=f"{west},{north},{east},{south}"
            except Exception:
                pass
        return {"lat":lat,"lon":lon,"viewbox":viewbox}
    return None

def rescue_nominatim(arena,city,cache):
    variants=[arena]
    if "," in arena:
        left=arena.split(",",1)[0].strip()
        if len(left)>=5: variants.append(left)
    b=base_norm(arena)
    if b and norm(b) not in {norm(x) for x in variants}: variants.append(b)
    simplified=re.sub(r"\b(?:A|B|C)-?plan\b|\b(?:konstgräs|naturgräs|gräs)(?:plan)?\b|\bplan\s*\d+\b"," ",arena,flags=re.I)
    simplified=re.sub(r"\bK-?\s*\d+\b"," ",simplified,flags=re.I)
    simplified=" ".join(simplified.split()).strip(" ,")
    if len(simplified)>=5 and norm(simplified) not in {norm(x) for x in variants}: variants.append(simplified)

    cc=city_center(city,cache) if city else None
    seen=set()
    candidates=[]
    for idx,v in enumerate(variants[:4]):
        qs=[f"{v}, {city}, Sverige" if city else f"{v}, Sverige"]
        if idx==0 and not is_generic(arena):
            qs.append(f"{v} idrottsplats, {city}, Sverige" if city else f"{v} idrottsplats, Sverige")
        for q in qs:
            if q in seen: continue
            seen.add(q)
            rr=nominatim_search(q,cache,limit=10)
            if isinstance(rr,list): candidates.extend(rr)

        scored=[]
        dedup=set()
        for r in candidates:
            rid=(r.get("osm_type"),r.get("osm_id"),r.get("lat"),r.get("lon"))
            if rid in dedup: continue
            dedup.add(rid)
            sc,ns,gs,dist=score_nominatim(arena,city,r,cc)
            scored.append((sc,ns,gs,dist,r))
        scored.sort(key=lambda x:(x[0],x[1],-x[3]),reverse=True)
        if not scored: continue
        top=scored[0]
        second=scored[1][0] if len(scored)>1 else 0.0

        generic=is_generic(arena)
        if generic:
            ok = top[1] >= 0.985 and top[3] <= 28 and (top[0]-second>=0.025 or top[1]>=0.999)
        else:
            ok = (
                top[1] >= 0.94 and top[3] <= 50 and (top[0]-second>=0.025 or top[1]>=0.985)
            ) or (
                top[1] >= 0.985 and top[3] <= 75
            )
        if ok:
            return top[4],{
                "method":"nominatim_name_geo",
                "score":round(top[0],4),
                "name_score":round(top[1],4),
                "geo_score":round(top[2],4),
                "distance_km":round(top[3],2),
            }

    # Bounded city search as a final precise rescue.
    if cc and cc.get("viewbox"):
        for v in variants[:3]:
            rr=nominatim_search(v,cache,viewbox=cc["viewbox"],bounded=True,limit=12)
            if not isinstance(rr,list): continue
            scored=[]
            for r in rr:
                sc,ns,gs,dist=score_nominatim(arena,city,r,cc)
                scored.append((sc,ns,gs,dist,r))
            scored.sort(key=lambda x:(x[0],x[1],-x[3]),reverse=True)
            if scored:
                top=scored[0]; second=scored[1][0] if len(scored)>1 else 0
                generic=is_generic(arena)
                need=0.99 if generic else 0.93
                if top[1]>=need and top[3]<=45 and (top[0]-second>=0.025 or top[1]>=0.99):
                    return top[4],{
                        "method":"nominatim_bounded_name_geo",
                        "score":round(top[0],4),
                        "name_score":round(top[1],4),
                        "geo_score":round(top[2],4),
                        "distance_km":round(top[3],2),
                    }
    return None,None

def overpass_city_sports(city,cache,osm_cache):
    nc=norm(city)
    if not nc: return []
    if nc in osm_cache:
        val=osm_cache[nc]
        return val if isinstance(val,list) else []
    cc=city_center(city,cache)
    if not cc:
        osm_cache[nc]={"_error":"city_center_not_found"}
        save_json(OSM_CACHE,osm_cache)
        return []
    lat,lon=cc["lat"],cc["lon"]
    query=f'''[out:json][timeout:25];
(
  nwr(around:30000,{lat},{lon})["name"]["leisure"~"^(pitch|sports_centre|stadium|recreation_ground)$"];
  nwr(around:30000,{lat},{lon})["name"]["sport"="soccer"];
);
out center tags;'''
    url="https://overpass-api.de/api/interpreter"
    try:
        obj=request_json(url,timeout=35,data=urllib.parse.urlencode({"data":query}).encode("utf-8"))
        elems=obj.get("elements",[]) if isinstance(obj,dict) else []
    except Exception as e:
        osm_cache[nc]={"_error":str(e)}
        save_json(OSM_CACHE,osm_cache)
        time.sleep(1.0)
        return []
    out=[]
    for e in elems:
        tags=e.get("tags") or {}
        name=tags.get("name")
        if not name: continue
        if "lat" in e and "lon" in e:
            elat,elon=e["lat"],e["lon"]
        else:
            c=e.get("center") or {}
            elat,elon=c.get("lat"),c.get("lon")
        if elat is None or elon is None: continue
        out.append({"name":name,"lat":float(elat),"lon":float(elon),"tags":tags,"osm_type":e.get("type"),"osm_id":e.get("id")})
    osm_cache[nc]=out
    save_json(OSM_CACHE,osm_cache)
    time.sleep(1.0)
    return out

def rescue_overpass(arena,city,cache,osm_cache):
    if not city: return None,None
    feats=overpass_city_sports(city,cache,osm_cache)
    if not feats: return None,None
    scored=sorted(((name_score(arena,[f.get("name","")]),f) for f in feats),key=lambda x:x[0],reverse=True)
    if not scored: return None,None
    top=scored[0]; second=scored[1][0] if len(scored)>1 else 0
    need=0.985 if is_generic(arena) else 0.90
    if top[0]<need: return None,None
    if top[0]<0.995 and top[0]-second<0.07: return None,None
    f=top[1]
    rev=nominatim_reverse(f["lat"],f["lon"],cache)
    result={
        "lat":str(f["lat"]),"lon":str(f["lon"]),
        "display_name":rev.get("display_name") or f.get("name"),
        "address":rev.get("address") or {},
        "category":"leisure","type":f.get("tags",{}).get("leisure","sports_centre"),
        "namedetails":{"name":f.get("name")},
        "osm_type":f.get("osm_type"),"osm_id":f.get("osm_id"),
    }
    return result,{"method":"overpass_city_sports","name_score":round(top[0],4),"city":city}

def address_from_result(r,fallback_city):
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

def municipality_from_result(r,fallback_city):
    a=r.get("address") or {}
    if not isinstance(a,dict): return fallback_city or ""
    return a.get("municipality") or a.get("city") or a.get("town") or a.get("village") or fallback_city or ""

def add_catalog(catalog,arena,city,result,source,meta):
    lat=float(result["lat"]); lon=float(result["lon"])
    muni=municipality_from_result(result,city)
    rec={
        "name":arena,"arena":arena,"canonical":arena,"canonical_name":arena,
        "aliases":[],"address":address_from_result(result,city),
        "city":city or muni,"ort":city or muni,"municipality":muni,"kommun":muni,
        "lat":lat,"lon":lon,"latitude":lat,"longitude":lon,
        "verified":True,"status":"verified","location_precision":"site",
        "source":source,"verification_source":source,
        "geocode_source":"OpenStreetMap","geocode_osm_type":result.get("osm_type"),
        "geocode_osm_id":result.get("osm_id"),"geocode_score":meta,
    }
    if isinstance(catalog,dict): catalog[arena]=rec
    elif isinstance(catalog,list): catalog.append(rec)
    else: raise TypeError("venue_catalog.json måste vara dict eller lista")
    save_json(CATALOG,catalog)
    return arena

def stable_verified(stable,team):
    if not isinstance(stable,dict) or team not in stable: return False
    v=stable[team]
    if isinstance(v,str): return bool(v.strip())
    if isinstance(v,dict):
        return bool(v.get("arena") or v.get("venue")) and str(v.get("status","verified")).casefold() in {"verified","verifierad","ok","true"}
    return False

def add_stable(stable,team,arena,source,method):
    stable[team]={"arena":arena,"status":"verified","method":"stable_home_venue","source":source,"verification_method":method}
    save_json(STABLE,stable)

def match_verified(matchmap,mid):
    v=matchmap.get(str(mid)) if isinstance(matchmap,dict) else None
    if isinstance(v,str): return bool(v.strip())
    if isinstance(v,dict):
        return bool(v.get("arena") or v.get("venue")) and str(v.get("status","verified")).casefold() in {"verified","verifierad","ok","true"}
    return False

def add_match(matchmap,mid,arena,source,team):
    matchmap[str(mid)]={"arena":arena,"status":"verified","method":"svff_match_specific_verified","source":source,"home_team":team}
    save_json(MATCHMAP,matchmap)

def unsafe_source_arena(arena):
    return any(re.search(p,str(arena or ""),re.I) for p in UNSAFE_ARENA_PATTERNS)

def resolve_catalog_arena(catalog,arena,city,source,cache,osm_cache):
    found,method=find_existing(catalog,arena,city)
    if found: return found[0],method
    result,meta=rescue_nominatim(arena,city,cache)
    if result: return add_catalog(catalog,arena,city,result,source,meta),meta["method"]
    result,meta=rescue_overpass(arena,city,cache,osm_cache)
    if result: return add_catalog(catalog,arena,city,result,source,meta),meta["method"]
    return None,None

def work_events_by_team(work):
    out={}
    for item in work if isinstance(work,list) else []:
        out[str(item.get("team",""))]=item
    return out

def team_fully_solved(team,item,stable,matchmap):
    if stable_verified(stable,team): return True
    events=item.get("events") or []
    mids=[str(e.get("match_id")) for e in events if e.get("match_id")]
    return bool(mids) and len(mids)==len(events) and all(match_verified(matchmap,m) for m in mids)

def ensure_files():
    if not WORK.exists():
        old=DATA/"football_deep_pass_remaining_worklist.json"
        if old.exists(): shutil.copy2(old,WORK)
    if not MISSING.exists():
        old=DATA/"football_deep_pass_catalog_missing.json"
        if old.exists(): shutil.copy2(old,MISSING)
    for p,default in ((STABLE,{}),(MATCHMAP,{}),(CACHE,{}),(OSM_CACHE,{})):
        if not p.exists(): save_json(p,default)
    need=[CATALOG,STABLE,MATCHMAP,WORK,MISSING,UNRES]
    missing=[str(p) for p in need if not p.exists()]
    if missing:
        print("SAKNADE FILER:")
        for x in missing: print(" -",x)
        raise SystemExit(2)

def main():
    ensure_files()
    catalog=load_json(CATALOG,{})
    stable=load_json(STABLE,{})
    matchmap=load_json(MATCHMAP,{})
    work=load_json(WORK,[])
    missing=load_json(MISSING,{})
    unresolved=load_json(UNRES,{})
    cache=load_json(CACHE,{})
    osm_cache=load_json(OSM_CACHE,{})
    citymap=work_city_map(work)
    workmap=work_events_by_team(work)
    stats=Counter(); detail={}
    backups={
        "catalog":str(backup(CATALOG,"deep_pass2") or ""),
        "stable":str(backup(STABLE,"deep_pass2") or ""),
        "match":str(backup(MATCHMAP,"deep_pass2") or ""),
    }

    print("======================================")
    print("DEEP PASS 2 START")
    print("======================================")
    print(f"Restlista: {len(work)} lag / {sum(int(x.get('count',0)) for x in work)} event")
    print(f"Katalogfall: {len(missing) if isinstance(missing,dict) else 0} lag")
    print()

    print("1) Verifierade 2026 hemmaanläggningar")
    for team,info in MANUAL_STABLE.items():
        if team not in workmap: continue
        if stable_verified(stable,team):
            stats["manual_stable_already"]+=1
            continue
        city=citymap.get(team) or info.get("city","")
        arena=info["arena"]; source=info["source"]
        print(f"  {team} -> {arena}",flush=True)
        canonical,method=resolve_catalog_arena(catalog,arena,city,source,cache,osm_cache)
        if canonical:
            add_stable(stable,team,canonical,source,"2026_schedule_"+method)
            stats["manual_stable_added"]+=1
            stats["manual_stable_events"]+=int(workmap[team].get("count",0))
            detail[team]={"type":"stable","arena":canonical,"method":method}
        else:
            stats["manual_stable_catalog_failed"]+=1
            detail[team]={"type":"stable_failed_catalog","arena":arena}

    print("\n2) Verifierade matchspecifika 2026-arenor")
    for mid,info in MANUAL_MATCH.items():
        team=info["team"]; item=workmap.get(team)
        if not item: continue
        current_ids={str(e.get("match_id")) for e in (item.get("events") or [])}
        if mid not in current_ids: continue
        if match_verified(matchmap,mid):
            stats["manual_match_already"]+=1
            continue
        arena=info["arena"]; city=info.get("city") or citymap.get(team,""); source=info["source"]
        print(f"  {mid} | {team} -> {arena}",flush=True)
        canonical,method=resolve_catalog_arena(catalog,arena,city,source,cache,osm_cache)
        if canonical:
            add_match(matchmap,mid,canonical,source,team)
            stats["manual_match_added"]+=1
            detail[f"match:{mid}"]={"type":"match","team":team,"arena":canonical,"method":method}
        else:
            stats["manual_match_catalog_failed"]+=1
            detail[f"match:{mid}"]={"type":"match_failed_catalog","team":team,"arena":arena}

    print("\n3) Räddar verifierade arenakandidater som saknas i katalogen")
    left_missing={}
    items=list(missing.items()) if isinstance(missing,dict) else []
    for i,(team,info) in enumerate(items,1):
        item=workmap.get(team)
        if item and team_fully_solved(team,item,stable,matchmap):
            stats["catalog_skip_already_solved"]+=1
            continue
        arena=str(info.get("source_arena") or "").strip()
        source=str(info.get("source_url") or "").strip()
        city=citymap.get(team,"")
        cnt=int(info.get("count",0))
        print(f"  {i}/{len(items)} | {team} | {arena}",flush=True)
        if not arena:
            left_missing[team]=info; stats["catalog_no_arena"]+=1; continue
        if unsafe_source_arena(arena):
            left_missing[team]=info
            stats["catalog_skipped_unsafe"]+=1
            stats["catalog_skipped_unsafe_events"]+=cnt
            continue
        canonical,method=resolve_catalog_arena(catalog,arena,city,source,cache,osm_cache)
        if canonical:
            add_stable(stable,team,canonical,source,"source_verified_"+method)
            if method.startswith("catalog_"):
                stats["catalog_existing_resolved"]+=1
                stats["catalog_existing_events"]+=cnt
            else:
                stats["catalog_geocoded_resolved"]+=1
                stats["catalog_geocoded_events"]+=cnt
            detail[team]={"type":"catalog_source","arena":canonical,"method":method,"source_arena":arena}
        else:
            left_missing[team]=info
            stats["catalog_still_missing"]+=1
            stats["catalog_still_missing_events"]+=cnt

    remaining=[]
    for item in work:
        team=str(item.get("team",""))
        if not team_fully_solved(team,item,stable,matchmap):
            remaining.append(item)
    save_json(REMAIN,remaining)

    left_unres={}
    if isinstance(unresolved,dict):
        for team,info in unresolved.items():
            item=workmap.get(team)
            if item and not team_fully_solved(team,item,stable,matchmap):
                left_unres[team]=info
    save_json(LEFTUNRES,left_unres)

    filtered_left={}
    for team,info in left_missing.items():
        item=workmap.get(team)
        if not item or not team_fully_solved(team,item,stable,matchmap):
            filtered_left[team]=info
    save_json(LEFTMISS,filtered_left)

    remaining_events=sum(int(x.get("count",0)) for x in remaining)
    report={
        "stats":dict(stats),"backups":backups,"details":detail,
        "remaining_teams":len(remaining),"remaining_events":remaining_events,
        "catalog_missing_remaining_teams":len(filtered_left),
        "catalog_missing_remaining_events":sum(int(v.get("count",0)) for v in filtered_left.values()),
        "source_unresolved_remaining_teams":len(left_unres),
        "source_unresolved_remaining_events":sum(int(v.get("count",0)) for v in left_unres.values()),
    }
    save_json(REPORT,report)

    print("\n======================================")
    print("DEEP PASS 2 KLAR")
    print("======================================")
    print(f"Manuella stable tillagda: {stats['manual_stable_added']} lag / {stats['manual_stable_events']} event")
    print(f"Manuella matcharenor tillagda: {stats['manual_match_added']}")
    print(f"Katalog via befintlig post: {stats['catalog_existing_resolved']} lag / {stats['catalog_existing_events']} event")
    print(f"Katalog via säker georescue: {stats['catalog_geocoded_resolved']} lag / {stats['catalog_geocoded_events']} event")
    print(f"Osäkra fler-/historiska arenor hoppade över: {stats['catalog_skipped_unsafe']} lag / {stats['catalog_skipped_unsafe_events']} event")
    print(f"Restlista efter passet: {len(remaining)} lag / {remaining_events} event")

    if RELINK.exists():
        print("\nKör omkoppling...")
        cp=subprocess.run([sys.executable,str(RELINK)],cwd=str(ROOT),capture_output=True,text=True)
        relink_text=(cp.stdout or "")+(cp.stderr or "")
    else:
        relink_text=f"Relink-script saknas: {RELINK}"
    print(relink_text.strip())
    RELINK_OUT.write_text(relink_text,encoding="utf-8")

    with zipfile.ZipFile(ZIPOUT,"w",zipfile.ZIP_DEFLATED) as z:
        for p in (REMAIN,LEFTMISS,LEFTUNRES,REPORT,RELINK_OUT):
            if p.exists(): z.write(p,arcname=p.name)
    print(f"\nLadda upp nästa: {ZIPOUT}")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
