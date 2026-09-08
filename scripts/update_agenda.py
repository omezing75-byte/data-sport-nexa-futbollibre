#!/usr/bin/env python3
import json
import os
import re
import urllib.request
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

SOURCE = "https://futbollibretv.org.pe/diaries.json"
OUT = "data/agenda.json"
SOURCE_BASE = "https://futbollibretv.org.pe"

# diaries.json gives diary_hour/date_diary without an explicit timezone.
# We map the country/competition to the local timezone used for that event.
TZ = {
    "Argentina": "America/Argentina/Buenos_Aires",
    "Brasil": "America/Sao_Paulo", "Brazil": "America/Sao_Paulo",
    "Colombia": "America/Bogota",
    "Ecuador": "America/Guayaquil",
    "Perú": "America/Lima", "Peru": "America/Lima",
    "Chile": "America/Santiago",
    "Uruguay": "America/Montevideo",
    "Paraguay": "America/Asuncion",
    "Bolivia": "America/La_Paz",
    "México": "America/Mexico_City", "Mexico": "America/Mexico_City",
    "Costa Rica": "America/Costa_Rica",
    "Panamá": "America/Panama", "Panama": "America/Panama",
    "Venezuela": "America/Caracas",
    "Estados Unidos": "America/New_York", "USA": "America/New_York",
    "Canadá": "America/Toronto", "Canada": "America/Toronto",
    "Inglaterra": "Europe/London", "England": "Europe/London",
    "Escocia": "Europe/London",
    "España": "Europe/Madrid", "Spain": "Europe/Madrid",
    "Italia": "Europe/Rome",
    "Francia": "Europe/Paris", "France": "Europe/Paris",
    "Alemania": "Europe/Berlin", "Germany": "Europe/Berlin",
    "Portugal": "Europe/Lisbon",
    "Países Bajos": "Europe/Amsterdam", "Netherlands": "Europe/Amsterdam",
    "Bélgica": "Europe/Brussels", "Belgium": "Europe/Brussels",
    "Turquía": "Europe/Istanbul", "Turkey": "Europe/Istanbul",
    "Arabia Saudita": "Asia/Riyadh", "Saudi Arabia": "Asia/Riyadh",
    "Qatar": "Asia/Qatar",
    "Japón": "Asia/Tokyo", "Japan": "Asia/Tokyo",
    "Corea del Sur": "Asia/Seoul", "South Korea": "Asia/Seoul",
    "Australia": "Australia/Sydney",
}

def clean(value):
    return re.sub(r"\s+", " ", str(value or "")).strip()

def get_timezone(country, description):
    country = clean(country)
    if country in TZ:
        return TZ[country]

    # Competition names frequently identify the event country.
    hints = [
        (r"\bPremier League\b|\bFA Cup\b|\bChampionship\b|\bLeague One\b", "Europe/London"),
        (r"\bLaLiga\b|\bPrimera División\b|\bSegunda División\b|\bCopa del Rey\b", "Europe/Madrid"),
        (r"\bSerie A\b|\bSerie B\b|\bCoppa Italia\b", "Europe/Rome"),
        (r"\bBundesliga\b|\bDFB\b", "Europe/Berlin"),
        (r"\bLigue 1\b|\bCoupe de France\b", "Europe/Paris"),
        (r"\bPrimeira Liga\b|\bTaça de Portugal\b", "Europe/Lisbon"),
        (r"\bEredivisie\b", "Europe/Amsterdam"),
        (r"\bMLS\b|\bUSL\b", "America/New_York"),
        (r"\bLiga MX\b|\bCopa MX\b", "America/Mexico_City"),
        (r"\bLiga 1\b.*\bPeru\b|\bPerú\b", "America/Lima"),
    ]
    for pattern, tz_name in hints:
        if re.search(pattern, description, re.I):
            return tz_name

    # Keep a deterministic fallback for entries where the source does not
    # identify the country. The original source value is still preserved.
    return "UTC"

def absolute_image_url(url):
    url = clean(url)
    if not url:
        return ""
    if url.startswith("http://") or url.startswith("https://"):
        return url
    if url.startswith("//"):
        return "https:" + url
    return SOURCE_BASE.rstrip("/") + "/" + url.lstrip("/")

def main():
    request = urllib.request.Request(
        SOURCE,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; SportNexaAgenda/1.0)",
            "Accept": "application/json",
        },
    )
    with urllib.request.urlopen(request, timeout=45) as response:
        src = json.load(response)

    now_utc = datetime.now(timezone.utc)
    events = []

    for row in src.get("data", []):
        attrs = row.get("attributes") or {}
        description = clean(attrs.get("diary_description"))
        date = clean(attrs.get("date_diary"))
        hour = clean(attrs.get("diary_hour")) or "00:00:00"

        if not description or not date:
            continue

        country_data = ((attrs.get("country") or {}).get("data") or {})
        country_attrs = country_data.get("attributes") or {}
        country_name = clean(country_attrs.get("name"))

        image_data = ((country_attrs.get("image") or {}).get("data") or {})
        image_attrs = image_data.get("attributes") or {}
        logo_url = absolute_image_url(image_attrs.get("url"))

        tz_name = get_timezone(country_name, description)

        try:
            # The diary source supplies a local calendar date/time.
            local_dt = datetime.fromisoformat(
                f"{date}T{hour}"
            ).replace(tzinfo=ZoneInfo(tz_name))
            start_utc = local_dt.astimezone(timezone.utc)
        except Exception:
            continue

        # Do not publish events once they are more than 4 hours past kickoff.
        # IMPORTANT: compare datetime with datetime (never datetime with float).
        # Keep the event while now <= kickoff + 4 hours.
        if now_utc > (start_utc + timedelta(hours=4)):
            continue

        title = description.replace("\n", " ").strip()
        competition = title.split(":", 1)[0].strip() if ":" in title else country_name

        # Keep the useful source data, including the source logo and embeds.
        embeds = []
        for embed_row in ((attrs.get("embeds") or {}).get("data") or []):
            ea = (embed_row.get("attributes") or {})
            embeds.append({
                "id": embed_row.get("id"),
                "name": clean(ea.get("embed_name")),
                "iframe": clean(ea.get("embed_iframe")),
            })

        events.append({
            "id": row.get("id"),
            "title": title,
            "competition": competition,
            "date_diary": date,
            "diary_hour": hour,
            "country": country_name,
            "logo": logo_url,
            "source_timezone": tz_name,
            "source_local": f"{date}T{hour}",
            "start_utc": start_utc.isoformat().replace("+00:00", "Z"),
            "embeds": embeds,
            # Preserve the complete original diary attributes so agenda.json
            # remains a full derivative of diaries.json, not a reduced schedule.
            "source_data": attrs,
        })

    events.sort(key=lambda item: item["start_utc"])

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    output = {
        "updated_at": now_utc.isoformat().replace("+00:00", "Z"),
        "source": SOURCE,
        "retention": "events remain until 4 hours after start",
        "events": events,
    }
    with open(OUT, "w", encoding="utf-8") as file:
        json.dump(output, file, ensure_ascii=False, indent=2)

    print(f"OK: {len(events)} events -> {OUT}")

if __name__ == "__main__":
    main()
