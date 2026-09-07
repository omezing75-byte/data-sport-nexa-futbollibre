import json, base64, re
from urllib.request import Request, urlopen

SOURCE = "https://futbollibretv.org.pe/diaries.json"
OUT = "agenda.json"

# Timezone of the event's competition/country. The source does not expose a
# timezone, so we infer it from country_code / league name / competition.
TZ = {
    "ar":"America/Argentina/Buenos_Aires","bo":"America/La_Paz","br":"America/Sao_Paulo",
    "cl":"America/Santiago","co":"America/Bogota","cr":"America/Costa_Rica",
    "ec":"America/Guayaquil","hn":"America/Tegucigalpa","mx":"America/Mexico_City",
    "pe":"America/Lima","py":"America/Asuncion","uy":"America/Montevideo",
    "us":"America/New_York","ca":"America/Toronto",
    "gb":"Europe/London","eng":"Europe/London","es":"Europe/Madrid","pt":"Europe/Lisbon",
    "fr":"Europe/Paris","de":"Europe/Berlin","it":"Europe/Rome","ch":"Europe/Zurich",
    "nl":"Europe/Amsterdam","tr":"Europe/Istanbul","ru":"Europe/Moscow",
    "sa":"Asia/Riyadh","jp":"Asia/Tokyo","kr":"Asia/Seoul",
    "au":"Australia/Sydney"
}

LEAGUE_INFO = {
    "premier league": ("eng", "Europe/London"),
    "la liga": ("es", "Europe/Madrid"),
    "laliga": ("es", "Europe/Madrid"),
    "segunda división": ("es", "Europe/Madrid"),
    "serie a": ("it", "Europe/Rome"),
    "serie b": ("it", "Europe/Rome"),
    "bundesliga": ("de", "Europe/Berlin"),
    "dfb pokal": ("de", "Europe/Berlin"),
    "ligue 1": ("fr", "Europe/Paris"),
    "ligue 2": ("fr", "Europe/Paris"),
    "primeira liga": ("pt", "Europe/Lisbon"),
    "eredivisie": ("nl", "Europe/Amsterdam"),
    "super lig": ("tr", "Europe/Istanbul"),
    "liga mx": ("mx", "America/Mexico_City"),
    "liga 1": ("pe", "America/Lima"),
    "liga profesional": ("ar", "America/Argentina/Buenos_Aires"),
    "liga profesional argentina": ("ar", "America/Argentina/Buenos_Aires"),
    "brasileirão": ("br", "America/Sao_Paulo"),
    "brasileirao": ("br", "America/Sao_Paulo"),
    "copa libertadores": ("bo", "America/La_Paz"),
    "copa sudamericana": ("bo", "America/La_Paz"),
    "copa chile": ("cl", "America/Santiago"),
    "costa rica": ("cr", "America/Costa_Rica"),
    "liga colombiana": ("co", "America/Bogota"),
    "liga colombia": ("co", "America/Bogota"),
    "ecuador": ("ec", "America/Guayaquil"),
    "paraguay": ("py", "America/Asuncion"),
    "uruguay": ("uy", "America/Montevideo"),
    "mls": ("us", "America/New_York"),
    # Leagues Cup 2026 final/US-hosted matches use US local time. The source
    # currently supplies Toluca-Monterrey at 20:15, matching Houston CDT (UTC-5).
    "league cup": ("mx", "America/Chicago"),
    "leagues cup": ("mx", "America/Chicago"),
}

COUNTRY_ALIASES = {
    "argentina":"ar","bolivia":"bo","brazil":"br","brasil":"br","chile":"cl",
    "colombia":"co","costa rica":"cr","ecuador":"ec","honduras":"hn","mexico":"mx",
    "peru":"pe","perú":"pe","paraguay":"py","uruguay":"uy","united states":"us",
    "usa":"us","england":"eng","spain":"es","españa":"es","italy":"it","italia":"it",
    "germany":"de","alemania":"de","france":"fr","francia":"fr","portugal":"pt",
    "switzerland":"ch","russia":"rus","turkey":"tr","saudi arabia":"sa"
}


def decode_stream(embed_iframe):
    if not embed_iframe:
        return ""
    m = re.search(r'[?&]r=([^&]+)', embed_iframe)
    if not m:
        return ""
    try:
        decoded = base64.b64decode(m.group(1)).decode("utf-8")
    except Exception:
        return ""
    m2 = re.search(r'[?&]stream=([^&]+)', decoded)
    return m2.group(1) if m2 else ""


def clean_text(v):
    return re.sub(r'\\n|\n+', ' ', str(v or '')).strip()


def infer_info(a):
    # Newer API variants may expose country_code directly.
    raw_code = str(a.get("country_code") or a.get("flagCode") or "").strip().lower()
    raw_country = clean_text(a.get("country") if isinstance(a.get("country"), str) else "")
    cdata = a.get("country", {}).get("data") if isinstance(a.get("country"), dict) else None
    cat = clean_text((cdata or {}).get("attributes", {}).get("name", "")) if isinstance(cdata, dict) else ""
    league = clean_text(a.get("league_name") or a.get("league") or cat)

    code = raw_code if raw_code in TZ or raw_code == "gb" else ""
    tz = TZ.get(code, "")
    low = league.lower()
    for key, (fc, ftz) in LEAGUE_INFO.items():
        if key in low:
            return fc, ftz, league

    country_code = COUNTRY_ALIASES.get(raw_country.lower(), "")
    if country_code:
        return country_code, TZ.get(country_code, "UTC"), league

    # Fall back to the source's likely default timezone only when no better
    # country/competition information exists.
    return (code or "pe"), (tz or "America/Lima"), league


req = Request(SOURCE, headers={"User-Agent": "SportNexa-Automation/1.0"})
with urlopen(req, timeout=30) as r:
    src = json.load(r)

sports = {}
for item in src.get("data", []):
    a = item.get("attributes", {})
    date = str(a.get("date_diary") or "").strip()
    hour = str(a.get("diary_hour") or "00:00:00").strip()
    if not date or not hour:
        continue

    flag_code, timezone, league_name = infer_info(a)
    title = clean_text(a.get("diary_description"))
    embeds = a.get("embeds", {}).get("data") or []
    servers, seen = [], set()
    for emb in embeds:
        ea = emb.get("attributes", {})
        stream = decode_stream(ea.get("embed_iframe", ""))
        if stream and stream not in seen:
            seen.add(stream)
            servers.append({
                "name": clean_text(ea.get("embed_name") or "Server"),
                "url": "https://tvf90.com/1.php?stream=" + stream,
                "active": True
            })

    sport_name = "Soccer"
    sport_icon = "⚽"
    if any(k in (league_name + " " + title).lower() for k in ["mlb", "baseball"]):
        sport_name, sport_icon = "Baseball", "⚾"
    elif any(k in (league_name + " " + title).lower() for k in ["nfl", "football americano"]):
        sport_name, sport_icon = "American Football", "🏈"

    league_key = league_name or "Other"
    sport = sports.setdefault(sport_name, {"name": sport_name, "icon": sport_icon, "leagues": {}})
    league = sport["leagues"].setdefault(league_key, {"name": league_key, "events": []})
    league["events"].append({
        "id": str(item.get("id", "")),
        "date": date,
        "time": hour,
        "timezone": timezone,
        "flagCode": flag_code,
        "title": title,
        "servers": servers,
        "agendaOrder": int(item.get("id", 0) or 0)
    })

result = {"sports": []}
for sport in sports.values():
    leagues = []
    for league in sport["leagues"].values():
        league["events"].sort(key=lambda e: (e["date"], e["time"], e["agendaOrder"]))
        leagues.append(league)
    sport["leagues"] = leagues
    result["sports"].append(sport)

with open(OUT, "w", encoding="utf-8") as f:
    json.dump(result, f, ensure_ascii=False, indent=2)
print("Wrote", sum(len(l["events"]) for s in result["sports"] for l in s["leagues"]), "events to", OUT)
