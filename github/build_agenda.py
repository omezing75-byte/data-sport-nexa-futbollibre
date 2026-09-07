import json, base64, re
from urllib.request import Request, urlopen

SOURCE="https://futbollibretv.org.pe/diaries.json"
OUT="agenda.json"

def decode_stream(embed_iframe):
    if not embed_iframe: return ""
    m=re.search(r'[?&]r=([^&]+)', embed_iframe)
    if not m: return ""
    try:
        decoded=base64.b64decode(m.group(1)).decode("utf-8")
    except Exception:
        return ""
    # Expected decoded form: https://...?...stream=xxxxx
    m2=re.search(r'[?&]stream=([^&]+)', decoded)
    return m2.group(1) if m2 else ""

req=Request(SOURCE,headers={"User-Agent":"SportNexa-Automation/1.0"})
with urlopen(req,timeout=30) as r:
    src=json.load(r)

out=[]
for item in src.get("data",[]):
    a=item.get("attributes",{})
    date=a.get("date_diary","")
    hour=a.get("diary_hour","00:00:00")
    title=a.get("diary_description","").replace("\\n"," ").strip()
    country=(a.get("country",{}).get("data") or {}).get("attributes",{})
    category=country.get("name","")
    embeds=(a.get("embeds",{}).get("data") or [])

    servers=[]
    seen=set()
    for emb in embeds:
        ea=emb.get("attributes",{})
        stream=decode_stream(ea.get("embed_iframe",""))
        if stream and stream not in seen:
            seen.add(stream)
            servers.append({"name":ea.get("embed_name","Server"),"stream":stream})

    if date and hour:
        # The source does not declare its timezone. Keep the source wall-clock
        # in date/time and leave timezone explicit for later mapping if needed.
        out.append({
            "id":str(item.get("id","")),
            "date":date,
            "time":hour,
            "datetime":date+"T"+hour,
            "title":title,
            "category":category,
            "stream":servers[0]["stream"] if servers else "",
            "servers":servers
        })

with open(OUT,"w",encoding="utf-8") as f:
    json.dump(out,f,ensure_ascii=False,indent=2)
print("Wrote",len(out),"events to",OUT)
