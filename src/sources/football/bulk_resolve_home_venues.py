#!/usr/bin/env python3
import json, re, sys, time, html as htmlmod, subprocess, zipfile, hashlib
from pathlib import Path
from urllib.parse import urlencode, urljoin
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError
from datetime import date

ROOT = Path(__file__).resolve().parents[3] if len(Path(__file__).resolve().parents) >= 4 else Path.cwd()
DATA = ROOT / "data"
WORKLIST = DATA / "football_placeholder_by_home_team.json"
CATALOG = DATA / "venue_catalog.json"
STABLE = DATA / "football_stable_home_venues.json"
OUT_CANDIDATES = DATA / "football_bulk_source_candidates.json"
OUT_MISSING = DATA / "football_bulk_catalog_missing.json"
OUT_UNRESOLVED = DATA / "football_bulk_unresolved.json"
OUT_STATS = DATA / "football_bulk_resolver_stats.json"
OUT_REMAINING = DATA / "football_bulk_remaining_worklist.json"
OUT_RELINK = DATA / "football_bulk_relink_output.txt"
OUT_ZIP = DATA / "football_bulk_remaining.zip"
MATCH_MAP = DATA / "football_match_venues.json"
RELINKER = ROOT / "src" / "sources" / "football" / "relink_events_to_venues.py"
CACHE = DATA / "football_club_source_cache"

BASE = "https://www.svenskafotbollsklubbar.se/"
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 EventfinderVenueResolver/1.0"

# Hand-verifierade i Eventfinder-arbetet. De används som seed och
# måste fortfarande finnas i verifierad venue_catalog innan de skrivs till stable-filen.
MANUAL = {
    "FC Helsingkrona": ("Smörlyckans IP", "https://www.fchelsingkrona.se/om-klubben/om-fc-helsingkrona/"),
    "Hjulsbro IK B": ("UCS Arena", "https://www.hjulsbroik.se/"),
    "IF Hallby FK B (9-m)": ("Bymarksvallen 1", "https://www.laget.se/"),
    "Oxie SK": ("Oxievångs IP, konstgräs", "https://www.svenskafotbollsklubbar.se/"),
    "Roslagsbro IF": ("Vårlyckan IP", "https://www.svenskafotbollsklubbar.se/"),
    "AC Studenterna": ("Solhaga", "https://www.acstudenterna.se/"),
    "AIF Barrikaden": ("Gullviksborgs IP A-plan", "https://www.aifbarrikaden.se/"),
    "Adolfsbergs IK": ("Lugnets IP", "https://www.adolfsbergsik.se/"),
    "Alingsås KIK U": ("Odenplan B-plan", "https://www.alingsaskik.se/"),
    "Alvesta GIF": ("Virdavallen", "https://www.svenskafotbollsklubbar.se/showclub.php?clubid=67"),
    "Annelunds IF U (9:9)": ("Mörlanda B konstgräs", "https://www.annelundsif.se/"),
    "Arnäs IF/Själevad 2": ("Comfort Petterssons Värme Arena K-11", "https://www.laget.se/"),
    "BIK Fotboll": ("Bondsjöhöjdens IP", "https://www.laget.se/"),
    "BK Höllviken": ("Höllvikens IP", "https://www.bkhollviken.se/"),
    "Bele Barkarby FF": ("Veddestavallen", "https://www.belebarkarby.se/"),
    "Bergdalens IK": ("Björkängsvallen", "https://www.bergdalensik.se/"),
    "Billesholms IK": ("Norrlyckan", "https://www.svenskafotbollsklubbar.se/showclub.php?clubid=2472"),
    "Bjärnums GoIF": ("Sparbanksvallen, Bjärnum", "https://www.laget.se/"),
    "Danmarks IF": ("Danelid 1", "https://www.laget.se/"),
    "Donsö IS": ("Donsövallen", "https://www.laget.se/"),
    "Eda IF": ("Hammarsvallen", "https://www.svt.se/nyheter/lokalt/varmland/saga-lamnar-eda-if-for-collegefotboll-i-usa"),
    "Ekets GoIF": ("Ryavallen", "https://www.svenskalag.se/eketsgoif-dam/kontakt"),
    "Eneby BK": ("Fyrby", "https://www.svenskafotbollsklubbar.se/showclub.php?clubid=4208"),
    "FC Hessleholm": ("Österås IP A-plan", "https://www.fchessleholm.se/"),
    "FC Vetlanda Dam": ("Heds Arena", "https://www.laget.se/VETLANDADAM"),
    "Falköpings KIK U": ("Odenplan", "https://www.falkopingskik.se/About"),
    "Finja IF": ("Finja IP", "https://www.svenskalag.se/finjaif/kontakt"),
    "Floda BoIF": ("Flodala IP", "https://www.gp.se/om/floda-boif"),
    "Gislövs IF": ("Gislövs IP", "https://www.svenskafotbollsklubbar.se/showclub.php?clubid=8154"),
    "Glömminge-Algutsrums IF": ("Glömmingelunden", "https://www.svenskafotbollsklubbar.se/showclub.php?clubid=8931"),
    "Hanaskogs IS": ("Västra Heds IP", "https://www.svenskafotbollsklubbar.se/showclub.php?clubid=8284"),
    "Kransen United FF": ("Aspuddens IP 1", "https://www.laget.se/"),
    "Råda BK": ("Rådavallen", "https://www.laget.se/"),
    "Älvsjö AIK DFF": ("Älvsjö IP 1", "https://www.alvsjoaik.se/"),
    "Öckerö IF": ("Prästängen", "https://www.ockeroif.se/"),
}

# Lag som vi redan vet växlar mellan olika anläggningar ska aldrig få global stable-home.
FORCE_MATCH_SPECIFIC = {
    "Djurö-Vindö IF": "2026: hemmamatcher på både Värmdövallen och Sjösalavallen",
}

def load_json(path, default):
    if not path.exists():
        return default
    with path.open(encoding="utf-8") as f:
        return json.load(f)

def save_json(path, obj):
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
        f.write("\n")
    tmp.replace(path)

def norm(s):
    s = htmlmod.unescape(str(s or "")).casefold()
    s = s.replace("–", "-").replace("—", "-")
    s = re.sub(r"[\(\)\[\]\{\},.;:'\"`´]", " ", s)
    s = re.sub(r"[^0-9a-zåäöéüæø+\-/ ]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()

def strip_tags(s):
    s = re.sub(r"<script\b.*?</script>", " ", s, flags=re.I|re.S)
    s = re.sub(r"<style\b.*?</style>", " ", s, flags=re.I|re.S)
    s = re.sub(r"<[^>]+>", " ", s)
    return re.sub(r"\s+", " ", htmlmod.unescape(s)).strip()

def base_variants(team):
    vals = [team]
    t = team.strip()
    # Endast konservativa suffixer. Kombinationslag med / lämnas i första hand exakt.
    patterns = [
        r"\s+\(9[\-m:0-9]*\)\s*$",
        r"\s+\(9m9\)\s*$",
        r"\s+\(9:9\)\s*$",
        r"\s+\(B\)\s*$",
        r"\s+B\s*$",
        r"\s+U\s*$",
        r"\s+Utv-lag\s*$",
        r"\s+F17\s*$",
        r"\s+Dam\s+[23]\s*$",
        r"\s+[23]\s*$",
        r"\s+Dam\s*$",
        r"\s+A\s*$",
    ]
    changed = True
    cur = t
    while changed:
        changed = False
        for p in patterns:
            n = re.sub(p, "", cur, flags=re.I).strip()
            if n != cur and len(n) >= 4:
                cur = n
                vals.append(cur)
                changed = True
    # Hantera "U (9-m)" etc efter parentesrensning
    cur2 = re.sub(r"\s+\([^)]+\)\s*$", "", t).strip()
    if cur2 != t:
        vals.append(cur2)
        cur3 = re.sub(r"\s+(?:U|B|2|3|Dam)\s*$", "", cur2, flags=re.I).strip()
        if cur3 and cur3 != cur2:
            vals.append(cur3)
    out=[]
    seen=set()
    for v in vals:
        k=norm(v)
        if k and k not in seen:
            seen.add(k); out.append(v)
    return out

def fetch(url, tries=1):
    CACHE.mkdir(parents=True, exist_ok=True)
    key=hashlib.sha1(url.encode("utf-8")).hexdigest()+".html"
    cp=CACHE/key
    if cp.exists() and cp.stat().st_size > 100:
        return cp.read_text(encoding="utf-8", errors="ignore")
    last=None
    for i in range(tries):
        try:
            req=Request(url, headers={"User-Agent":UA, "Accept-Language":"sv-SE,sv;q=0.9,en;q=0.5"})
            with urlopen(req, timeout=6) as r:
                raw=r.read()
            text=raw.decode("utf-8","ignore")
            if len(text) > 100:
                cp.write_text(text, encoding="utf-8")
            return text
        except (URLError, HTTPError, TimeoutError) as e:
            last=e
            time.sleep(0.8*(i+1))
    raise last

def search_club(term):
    qs = urlencode({
        "grid[order]":"clubname",
        "grid[search]":term,
        "grid[search_field]":"clubname",
        "grid[sort]":"asc",
        "onlyActiveClubs":"true",
    })
    url = BASE + "?" + qs
    page = fetch(url)
    # fånga showclub-länkar och ankartext
    pat = re.compile(r'<a[^>]+href=["\']([^"\']*showclub\.php\?clubid=\d+[^"\']*)["\'][^>]*>(.*?)</a>', re.I|re.S)
    rows=[]
    for href, inner in pat.findall(page):
        name=strip_tags(inner)
        if not name:
            continue
        rows.append((name, urljoin(BASE, htmlmod.unescape(href))))
    # dedup
    out=[]; seen=set()
    for name,u in rows:
        key=(norm(name),u)
        if key not in seen:
            seen.add(key); out.append((name,u))
    return out

def choose_club(team):
    for idx, term in enumerate(base_variants(team)):
        try:
            rows=search_club(term)
        except Exception:
            continue
        nt=norm(term)
        exact=[r for r in rows if norm(r[0])==nt]
        if len(exact)==1:
            return exact[0][0], exact[0][1], ("exact" if idx==0 else "base")
        # ibland innehåller ankartext extra whitespace/tecken
        close=[r for r in rows if norm(r[0]).replace("-"," ")==nt.replace("-"," ")]
        if len(close)==1:
            return close[0][0], close[0][1], ("exact" if idx==0 else "base")
        time.sleep(0.05)
    return None

def parse_club_page(url):
    page=fetch(url)
    text=strip_tags(page)
    def field(label, next_label):
        m=re.search(re.escape(label)+r"\s+(.*?)\s+"+re.escape(next_label), text, flags=re.I)
        return m.group(1).strip() if m else None
    venue=field("Hemmaplan","Komplett namn")
    hemort=field("Hemort","Kommun")
    kommun=field("Kommun","Hemmaplan")
    m=re.search(r"Senast Uppdaterad\s+(\d{4}-\d{2}-\d{2})", text, flags=re.I)
    updated=m.group(1) if m else None
    return {"venue":venue, "hemort":hemort, "kommun":kommun, "updated":updated, "url":url}

def catalog_entries(obj):
    if isinstance(obj, list):
        for x in obj:
            if isinstance(x,dict):
                yield None,x
    elif isinstance(obj,dict):
        if isinstance(obj.get("venues"),list):
            for x in obj["venues"]:
                if isinstance(x,dict): yield None,x
        else:
            for k,v in obj.items():
                if isinstance(v,dict):
                    yield k,v

def is_verified(rec):
    if rec.get("verified") is True:
        return True
    s=str(rec.get("status","")).casefold()
    if s in {"verified","verifierad","ok","true"}:
        return True
    # Om katalogen inte använder något verifieringsfält alls ska vi inte blockera äldre format.
    keys={k.casefold() for k in rec}
    if "verified" not in keys and "status" not in keys:
        return True
    return False

def build_catalog_index(catalog):
    idx={}
    for key,rec in catalog_entries(catalog):
        if not is_verified(rec):
            continue
        names=[]
        if key: names.append(key)
        for k in ("name","arena","venue","canonical_name","canonical","display_name","namn"):
            v=rec.get(k)
            if isinstance(v,str): names.append(v)
        for k in ("aliases","alias","variants","varianter"):
            v=rec.get(k)
            if isinstance(v,list):
                names.extend(x for x in v if isinstance(x,str))
            elif isinstance(v,str):
                names.append(v)
        canonical=None
        for k in ("canonical_name","canonical","name","arena","venue","display_name","namn"):
            v=rec.get(k)
            if isinstance(v,str) and v.strip():
                canonical=v.strip(); break
        if canonical is None and key:
            canonical=str(key)
        if not canonical:
            continue
        for n in names+[canonical]:
            nn=norm(n)
            if nn:
                idx.setdefault(nn,[]).append((canonical,rec))
    return idx

def site_key(s):
    """Deterministisk anläggningsnyckel, inte fuzzy matching.
    Tar bara bort kända plan-/underlags-suffix så att t.ex.
    'Smörlyckans IP' kan möta 'Smörlyckans IP, konstgräsplan 1'.
    """
    x = norm(s)
    prev = None
    while x and x != prev:
        prev = x
        x = re.sub(r"\s+(?:a|b|c)[ -]?plan(?:en)?$", "", x)
        x = re.sub(r"\s+(?:plan|planen|konstgräsplan|konstgrasplan)\s*[a-z0-9-]*$", "", x)
        x = re.sub(r"\s+(?:konstgräs|konstgras|naturgräs|naturgras)$", "", x)
        x = re.sub(r"\s+(?:11|9|7|5)[ -]?(?:manna|m)$", "", x)
        x = re.sub(r"\s+[1234]$", "", x)
        x = re.sub(r"\s+ip$", "", x)
        x = re.sub(r"\s+idrottsplats$", "", x)
        x = re.sub(r"\s+arena$", "", x) if len(x.split()) > 2 else x
        x = re.sub(r"\s+", " ", x).strip(" -/")
    return x

def build_site_index(catalog):
    out={}
    seen=set()
    for key,rec in catalog_entries(catalog):
        if not is_verified(rec):
            continue
        names=[]
        if key: names.append(str(key))
        for k in ("name","arena","venue","canonical_name","canonical","display_name","namn"):
            v=rec.get(k)
            if isinstance(v,str): names.append(v)
        for k in ("aliases","alias","variants","varianter"):
            v=rec.get(k)
            if isinstance(v,list): names.extend(str(x) for x in v if isinstance(x,str))
            elif isinstance(v,str): names.append(v)
        canonical=None
        for k in ("canonical_name","canonical","name","arena","venue","display_name","namn"):
            v=rec.get(k)
            if isinstance(v,str) and v.strip():
                canonical=v.strip(); break
        if canonical is None and key: canonical=str(key)
        if not canonical: continue
        for n in names+[canonical]:
            sk=site_key(n)
            marker=(sk,canonical)
            if sk and marker not in seen:
                seen.add(marker)
                out.setdefault(sk,[]).append((canonical,rec))
    return out

def _coord(rec, keys):
    for k in keys:
        v=rec.get(k)
        try:
            if v is not None and str(v).strip() != "": return float(v)
        except Exception:
            pass
    return None

def same_physical_site(rows):
    if len(rows) < 2:
        return bool(rows)
    addrs=[]; coords=[]
    for _,r in rows:
        a=None
        for k in ("address","adress","street_address","formatted_address"):
            if isinstance(r.get(k),str) and r.get(k).strip():
                a=norm(r.get(k)); break
        if a: addrs.append(a)
        lat=_coord(r,("lat","latitude")); lon=_coord(r,("lon","lng","longitude"))
        if lat is not None and lon is not None: coords.append((lat,lon))
    if len(addrs)==len(rows) and len(set(addrs))==1:
        return True
    if len(coords)==len(rows):
        lats=[x[0] for x in coords]; lons=[x[1] for x in coords]
        if max(lats)-min(lats) <= 0.002 and max(lons)-min(lons) <= 0.004:
            return True
    return False

def find_catalog(venue, idx, site_idx):
    if not venue:
        return None, None
    hits=idx.get(norm(venue),[])
    canon={h[0] for h in hits}
    if len(canon)==1:
        return next(iter(canon)), "exact"
    sk=site_key(venue)
    rows=site_idx.get(sk,[]) if sk else []
    scanon={x[0] for x in rows}
    if len(scanon)==1:
        return next(iter(scanon)), "unique_site"
    if len(scanon)>1 and same_physical_site(rows):
        # Samma verifierade kartpunkt/site, flera planposter: välj kortaste kanoniska namn.
        return sorted(scanon,key=lambda x:(len(x),x.casefold()))[0], "same_physical_site"
    return None, None

def looks_multi_ground(v):
    if not v:
        return False
    # Slash/semicolon or explicit " och " usually means more than one facility.
    # Manual overrides are exempt because they were separately verified.
    return bool(re.search(r"\s(?:/|;|\boch\b)\s", str(v), flags=re.I))

def count_events(worklist, teams):
    s=set(teams)
    return sum(int(x.get("count",0)) for x in worklist if x.get("team") in s)

def main():
    work=load_json(WORKLIST,[])
    catalog=load_json(CATALOG,[])
    stable=load_json(STABLE,{})
    if not isinstance(stable,dict):
        print("FEL: football_stable_home_venues.json måste vara ett JSON-objekt.", file=sys.stderr)
        sys.exit(2)
    cidx=build_catalog_index(catalog)
    site_idx=build_site_index(catalog)
    if not cidx:
        print("FEL: kunde inte bygga verifierat index från venue_catalog.json", file=sys.stderr)
        sys.exit(2)

    candidates={}
    missing={}
    unresolved={}
    added=0
    added_events=0
    already=0
    manual_used=0
    source_used=0

    total=len(work)
    for i,item in enumerate(work,1):
        team=item.get("team","").strip()
        print(f"{i}/{total} | {team}", flush=True)
        if not team:
            continue
        if team in stable and isinstance(stable[team],dict) and stable[team].get("arena"):
            already += 1
            continue
        if team in FORCE_MATCH_SPECIFIC:
            unresolved[team]={
                "count":item.get("count",0),
                "reason":"match_specific_required",
                "detail":FORCE_MATCH_SPECIFIC[team],
                "events":item.get("events",[]),
            }
            continue

        source_venue=None; source_url=None; mode=None; source_name=None; updated=None
        if team in MANUAL:
            source_venue,source_url=MANUAL[team]
            mode="manual_verified"
            source_name=team
            manual_used += 1
        else:
            hit=choose_club(team)
            if hit:
                source_name,source_url,mode=hit
                try:
                    info=parse_club_page(source_url)
                except Exception as e:
                    unresolved[team]={
                        "count":item.get("count",0),
                        "reason":"club_page_fetch_failed",
                        "source_url":source_url,
                        "error":str(e),
                        "events":item.get("events",[]),
                    }
                    continue
                source_venue=info.get("venue")
                updated=info.get("updated")
                source_used += 1

        if not source_venue or norm(source_venue) in {"saknas","okänd","okant","-"}:
            unresolved[team]={
                "count":item.get("count",0),
                "reason":"no_unambiguous_home_ground_source",
                "events":item.get("events",[]),
            }
            continue

        # En basträff (t.ex. "Klubb" för "Klubb U") är bra som kandidat men
        # inte tillräcklig för en permanent stable-home-mappning.
        if mode == "base":
            candidates[team]={
                "count":item.get("count",0),
                "source_team":source_name,
                "source_arena":source_venue,
                "source_url":source_url,
                "source_updated":updated,
                "match_mode":mode,
            }
            unresolved[team]={
                "count":item.get("count",0),
                "reason":"team_variant_requires_team_specific_verification",
                "candidate":candidates[team],
                "events":item.get("events",[]),
            }
            continue

        if mode != "manual_verified" and looks_multi_ground(source_venue):
            unresolved[team]={
                "count":item.get("count",0),
                "reason":"source_lists_multiple_home_grounds",
                "source_arena":source_venue,
                "source_url":source_url,
                "events":item.get("events",[]),
            }
            continue

        candidates[team]={
            "count":item.get("count",0),
            "source_team":source_name,
            "source_arena":source_venue,
            "source_url":source_url,
            "source_updated":updated,
            "match_mode":mode,
        }

        canonical, catalog_mode=find_catalog(source_venue,cidx,site_idx)
        if not canonical:
            missing[team]={
                **candidates[team],
                "reason":"arena_not_exactly_found_in_verified_venue_catalog",
                "events":item.get("events",[]),
            }
            continue

        stable[team]={
            "arena":canonical,
            "status":"verified",
            "method":"stable_home_venue",
            "source":source_url,
            "source_arena":source_venue,
            "source_team":source_name,
            "source_updated":updated,
            "resolution":"bulk_" + str(catalog_mode),
        }
        added += 1
        added_events += int(item.get("count",0))
        save_json(STABLE,stable)

        if i % 25 == 0 or i == total:
            print(f"{i}/{total} | nya stable: {added} | event täckta: {added_events} | katalogsaknas: {len(missing)} | olösta: {len(unresolved)}", flush=True)
        time.sleep(0.12)

    # Backup before writing
    if STABLE.exists():
        bak=DATA/"football_stable_home_venues_before_bulk.json"
        if not bak.exists():
            bak.write_text(STABLE.read_text(encoding="utf-8"),encoding="utf-8")
    save_json(STABLE,stable)
    save_json(OUT_CANDIDATES,candidates)
    save_json(OUT_MISSING,missing)
    save_json(OUT_UNRESOLVED,unresolved)

    unresolved_events=sum(int(v.get("count",0)) for v in unresolved.values())
    missing_events=sum(int(v.get("count",0)) for v in missing.values())
    stats={
        "worklist_teams":len(work),
        "worklist_events":sum(int(x.get("count",0)) for x in work),
        "already_stable_teams":already,
        "new_stable_teams":added,
        "new_stable_events":added_events,
        "source_candidates":len(candidates),
        "catalog_missing_teams":len(missing),
        "catalog_missing_events":missing_events,
        "unresolved_source_teams":len(unresolved),
        "unresolved_source_events":unresolved_events,
        "manual_seed_used":manual_used,
        "club_database_used":source_used,
    }
    # Kör befintlig relinker direkt så användaren bara behöver ett enda bulkkommando.
    relink_rc=None
    relink_unresolved=None
    relink_text=""
    if RELINKER.exists():
        try:
            cp=subprocess.run([sys.executable, str(RELINKER)], cwd=str(ROOT),
                              text=True, capture_output=True, timeout=600)
            relink_rc=cp.returncode
            relink_text=(cp.stdout or "") + (("\n" + cp.stderr) if cp.stderr else "")
            OUT_RELINK.write_text(relink_text, encoding="utf-8")
            m=re.search(r"Ingen arenakandidat\s*:\s*(\d+)", relink_text, flags=re.I)
            if m: relink_unresolved=int(m.group(1))
        except Exception as e:
            relink_rc=-1
            relink_text="Relinker kunde inte köras: " + repr(e)
            OUT_RELINK.write_text(relink_text + "\n", encoding="utf-8")

    # Skapa en ny kompakt arbetslista. Matchspecifika mappningar räknas bort per match.
    match_map=load_json(MATCH_MAP,{})
    if not isinstance(match_map,dict): match_map={}
    remaining=[]
    remaining_events=0
    for item in work:
        team=str(item.get("team","")).strip()
        if team in stable and isinstance(stable.get(team),dict) and stable[team].get("arena"):
            continue
        evs=[]
        for ev in item.get("events",[]) or []:
            mid=str(ev.get("match_id","")).strip()
            if mid and mid in match_map:
                continue
            evs.append(ev)
        if not evs:
            continue
        ni=dict(item)
        ni["events"]=evs
        ni["count"]=len(evs)
        remaining.append(ni)
        remaining_events += len(evs)
    save_json(OUT_REMAINING,remaining)

    stats["remaining_worklist_teams"]=len(remaining)
    stats["remaining_worklist_events"]=remaining_events
    stats["relink_return_code"]=relink_rc
    stats["relink_unresolved_events"]=relink_unresolved
    save_json(OUT_STATS,stats)

    # En enda ZIP att ladda upp om något fortfarande återstår.
    with zipfile.ZipFile(OUT_ZIP,"w",compression=zipfile.ZIP_DEFLATED) as z:
        for fp in (OUT_REMAINING,OUT_MISSING,OUT_UNRESOLVED,OUT_CANDIDATES,OUT_STATS,OUT_RELINK):
            if fp.exists(): z.write(fp, arcname=fp.name)

    print("\nBULKRESOLVER KLAR")
    for k,v in stats.items():
        print(f"{k}: {v}")
    if relink_text:
        print("\n--- RELINKER ---")
        print(relink_text.strip())
    print(f"\nUppdaterad: {STABLE}")
    print(f"Kandidater: {OUT_CANDIDATES}")
    print(f"Saknas i katalog: {OUT_MISSING}")
    print(f"Olösta källor: {OUT_UNRESOLVED}")
    print(f"Ny restlista: {OUT_REMAINING}")
    print(f"Ladda upp vid behov: {OUT_ZIP}")

if __name__=="__main__":
    main()
