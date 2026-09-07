#!/usr/bin/env python3
import json, os, re, urllib.request
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

SOURCE = "https://futbollibretv.org.pe/diaries.json"
OUT = "data/agenda.json"

# Nama negara/kompetisi -> IANA timezone + kode bendera GitHub.
TZ = {
 "Argentina":("America/Argentina/Buenos_Aires","ar"),
 "Brasil":("America/Sao_Paulo","br"), "Brazil":("America/Sao_Paulo","br"),
 "Colombia":("America/Bogota","co"), "Ecuador":("America/Guayaquil","ec"),
 "Perú":("America/Lima","pe"), "Peru":("America/Lima","pe"),
 "Chile":("America/Santiago","cl"), "Uruguay":("America/Montevideo","uy"),
 "Paraguay":("America/Asuncion","py"), "Bolivia":("America/La_Paz","bo"),
 "México":("America/Mexico_City","mx"), "Mexico":("America/Mexico_City","mx"),
 "Costa Rica":("America/Costa_Rica","cr"), "Panamá":("America/Panama","pa"),
 "Panama":("America/Panama","pa"), "Venezuela":("America/Caracas","ve"),
 "Estados Unidos":("America/New_York","us"), "USA":("America/New_York","us"),
 "Canadá":("America/Toronto","ca"), "Canada":("America/Toronto","ca"),
 "Inglaterra":("Europe/London","gb"), "England":("Europe/London","gb"),
 "Escocia":("Europe/London","gb"), "España":("Europe/Madrid","es"),
 "Spain":("Europe/Madrid","es"), "Italia":("Europe/Rome","it"),
 "Italia":("Europe/Rome","it"), "Francia":("Europe/Paris","fr"),
 "France":("Europe/Paris","fr"), "Alemania":("Europe/Berlin","de"),
 "Germany":("Europe/Berlin","de"), "Portugal":("Europe/Lisbon","pt"),
 "Países Bajos":("Europe/Amsterdam","nl"), "Netherlands":("Europe/Amsterdam","nl"),
 "Bélgica":("Europe/Brussels","be"), "Belgium":("Europe/Brussels","be"),
 "Turquía":("Europe/Istanbul","tr"), "Turkey":("Europe/Istanbul","tr"),
 "Arabia Saudita":("Asia/Riyadh","sa"), "Saudi Arabia":("Asia/Riyadh","sa"),
 "Qatar":("Asia/Qatar","qa"), "Japón":("Asia/Tokyo","jp"), "Japan":("Asia/Tokyo","jp"),
 "Corea del Sur":("Asia/Seoul","kr"), "South Korea":("Asia/Seoul","kr"),
 "Australia":("Australia/Sydney","au"),
}

# Only football/soccer. Other sports in diaries.json are intentionally ignored.
NON_FOOTBALL = re.compile(
 r"\b(MLB|NBA|NFL|NHL|Tennis|Tenis|Golf|Moto\s*GP|MotoGP|F1|Fórmula\s*1|"
 r"Formula\s*1|Indycar|Ciclismo|Cycling|Boxeo|UFC|Rugby|Béisbol|Beisbol)\b",
 re.I)

def clean(s):
    return re.sub(r"\s+"," ",str(s or "")).strip()

def get_tz(country, desc):
    c=clean(country)
    if c in TZ: return TZ[c]
    # competition names sometimes reveal the country
    for k,v in TZ.items():
        if re.search(r"\b"+re.escape(k)+r"\b", desc, re.I):
            return v
    # Common league hints
    hints=[
      (r"Premier League|FA Cup|Championship|League One","Europe/London","gb"),
      (r"LaLiga|Primera División|Segunda División|Copa del Rey","Europe/Madrid","es"),
      (r"Serie A|Serie B|Coppa Italia","Europe/Rome","it"),
      (r"Bundesliga|DFB","Europe/Berlin","de"),
      (r"Ligue 1|Coupe de France","Europe/Paris","fr"),
      (r"Primeira Liga|Taça de Portugal","Europe/Lisbon","pt"),
      (r"Eredivisie","Europe/Amsterdam","nl"),
      (r"MLS|USL","America/New_York","us"),
    ]
    for pat,tz,flag in hints:
        if re.search(pat,desc,re.I): return tz,flag
    return "UTC",""

def main():
    req=urllib.request.Request(SOURCE,headers={"User-Agent":"Mozilla/5.0"})
    with urllib.request.urlopen(req,timeout=30) as r:
        src=json.load(r)

    events=[]
    for row in src.get("data",[]):
        a=row.get("attributes") or {}
        desc=clean(a.get("diary_description"))
        if not desc or NON_FOOTBALL.search(desc):
            continue
        date=clean(a.get("date_diary"))
        hour=clean(a.get("diary_hour")) or "00:00:00"
        country=((a.get("country") or {}).get("data") or {}).get("attributes") or {}
        cname=clean(country.get("name"))
        tzname,flag=get_tz(cname,desc)
        try:
            naive=datetime.fromisoformat(f"{date}T{hour}")
            aware=naive.replace(tzinfo=ZoneInfo(tzname))
            start_utc=aware.astimezone(timezone.utc).isoformat().replace("+00:00","Z")
        except Exception:
            continue

        # Country image is intentionally not copied from the source site.
        # The Blogger template uses the user's GitHub /flags/{code}.png files.
        title=desc.replace("\n"," ")
        competition=title.split(":")[0].strip() if ":" in title else cname
        events.append({
          "id": row.get("id"),
          "title": title,
          "competition": competition,
          "country": cname,
          "flag": flag,
          "source_local": f"{date}T{hour}",
          "source_timezone": tzname,
          "start_utc": start_utc
        })

    events.sort(key=lambda x:x["start_utc"])
    os.makedirs(os.path.dirname(OUT),exist_ok=True)
    with open(OUT,"w",encoding="utf-8") as f:
        json.dump({"updated_at":datetime.now(timezone.utc).isoformat().replace("+00:00","Z"),
                   "source":SOURCE,"events":events},f,ensure_ascii=False,indent=2)
    print(f"OK: {len(events)} football events -> {OUT}")

if __name__=="__main__":
    main()
