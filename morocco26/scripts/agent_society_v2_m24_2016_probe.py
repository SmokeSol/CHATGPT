#!/usr/bin/env python3
from __future__ import annotations

import hashlib, json, os, re
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse, urldefrag

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "goal100" / "agent_society_v2" / "probes" / "m24_2016"
RAW = OUT / "raw"
RUN_ID = os.environ.get("ASV2_RUN_ID", "manual")

ROOTS = [
"https://assets.medias24.com/js/carte/election2016/casa_region/index.html",
"https://assets.medias24.com/js/carte/election2016/rabat_region/index.html",
"https://assets.medias24.com/js/carte/election2016/marrakech_region/index.html",
"https://assets.medias24.com/js/carte/election2016/agadir_region/index.html",
"https://assets.medias24.com/js/carte/election2016/fes_region/index.html",
"https://assets.medias24.com/js/carte/election2016/beni_mellal_region/index.html",
"https://assets.medias24.com/js/carte/election2016/tanger_region/index.html",
"https://assets.medias24.com/js/carte/election2016/laayoune_region/index.html",
"https://assets.medias24.com/js/carte/election2016/ouarzazate_region/index.html",
"https://assets.medias24.com/js/carte/election2016/oued_eddahab_region/index.html",
"https://assets.medias24.com/js/carte/election2016/tantan_region/index.html",
"https://assets.medias24.com/js/carte/election2016/oujda_region/index.html",
"https://assets.medias24.com/js/carte/election2016/casa_ville_pre/index.html",
"https://assets.medias24.com/js/carte/election2016/fes_ville_pre/index.html",
"https://assets.medias24.com/js/carte/election2016/marrakech_ville_pre/index.html",
"https://assets.medias24.com/js/carte/election2016/rabat_ville_pre/index.html",
"https://assets.medias24.com/js/carte/election2016/sale_ville_pre/index.html",
]

COMMON = [
"data.json","datas.json","candidats.json","candidates.json","elections.json","resultats.json",
"data.csv","candidats.csv","data.js","main.js","app.js","script.js","scripts.js","map.js",
"js/data.js","js/main.js","js/app.js","js/script.js","js/map.js","assets/data.js","assets/data.json"
]
PARTY_RE = re.compile(r"\b(PJD|PAM|RNI|PI|USFP|PPS|MP|UC|FGD|FFD|MDS)\b", re.I)
URL_RE = re.compile(r"(?:src|href)=[\"']([^\"']+)[\"']|[\"']([^\"']+\.(?:js|json|csv|html?)(?:\?[^\"']*)?)[\"']", re.I)


def sha(b: bytes) -> str: return hashlib.sha256(b).hexdigest()
def clean_url(u: str, base: str) -> str: return urldefrag(urljoin(base,u))[0]
def ok_host(u: str) -> bool: return (urlparse(u).hostname or "").lower() == "assets.medias24.com"

def discover(text: str, base: str) -> list[str]:
    out=set()
    try:
        soup=BeautifulSoup(text,"html.parser")
        for tag,attr in (("script","src"),("link","href"),("a","href"),("iframe","src")):
            for n in soup.find_all(tag):
                if n.get(attr): out.add(clean_url(n.get(attr),base))
    except Exception: pass
    for m in URL_RE.finditer(text):
        v=m.group(1) or m.group(2)
        if v: out.add(clean_url(v,base))
    return sorted(u for u in out if u.startswith("http") and ok_host(u) and "election2016" in u)

def main():
    OUT.mkdir(parents=True,exist_ok=True); RAW.mkdir(parents=True,exist_ok=True)
    s=requests.Session(); s.headers.update({"User-Agent":"Atlas395-ASV2/1.0","Accept":"*/*"})
    q=deque((u,0,None) for u in ROOTS); seen=set(); rec=[]; candidate_text=[]
    max_fetch=400
    while q and len(rec)<max_fetch:
        u,depth,parent=q.popleft()
        if u in seen or depth>3: continue
        seen.add(u)
        try:
            r=s.get(u,timeout=(10,30),allow_redirects=True)
            b=r.content; ct=r.headers.get("content-type","")
            text=""
            if any(x in ct.lower() for x in ("text","json","javascript")) or Path(urlparse(u).path).suffix.lower() in {".html",".htm",".js",".json",".csv",".txt"}:
                text=b.decode("utf-8",errors="replace")
            suffix=Path(urlparse(u).path).suffix or ".bin"
            p=RAW/(sha(u.encode())[:16]+suffix[:8]); p.write_bytes(b)
            parties=sorted(set(x.upper() for x in PARTY_RE.findall(text))) if text else []
            if parties:
                snippets=[]
                for line in text.splitlines():
                    if PARTY_RE.search(line): snippets.append(line[:1000])
                    if len(snippets)>=80: break
                candidate_text.append({"url":u,"parties":parties,"snippets":snippets})
            ds=discover(text,u) if text else []
            if u in ROOTS:
                base=u.rsplit("/",1)[0]+"/"
                ds += [urljoin(base,x) for x in COMMON]
            for v in sorted(set(ds)):
                if v not in seen: q.append((v,depth+1,u))
            rec.append({"url":u,"parent":parent,"depth":depth,"status":r.status_code,"content_type":ct,"bytes":len(b),"sha256":sha(b),"raw_path":str(p.relative_to(ROOT)),"discovered":len(ds),"party_codes":parties})
        except Exception as e:
            rec.append({"url":u,"parent":parent,"depth":depth,"status":None,"error":type(e).__name__+":"+str(e)[:300]})
    status={}
    for x in rec: status[str(x.get("status"))]=status.get(str(x.get("status")),0)+1
    summary={
      "schema_version":"1.0","run_id":RUN_ID,"created_at":datetime.now(timezone.utc).isoformat(),
      "source_article":"https://medias24.com/2016/10/03/legislatives-les-principaux-candidats-circonscription-par-circonscription-17-cartes/",
      "source_article_publication_date":"2016-10-03","target_election_date":"2016-10-07",
      "pre_election_source":True,"root_count":len(ROOTS),"fetch_count":len(rec),"status_counts":status,
      "successful_roots":sum(1 for x in rec if x.get("url") in ROOTS and x.get("status")==200),
      "files_with_party_codes":len(candidate_text),
      "all_party_codes":sorted({p for x in candidate_text for p in x["parties"]}),
      "outcome_data_used":False,"forecast_effect_authorized":False,
    }
    (OUT/"fetch_manifest.json").write_text(json.dumps(rec,ensure_ascii=False,indent=2),encoding="utf-8")
    (OUT/"candidate_text_probe.json").write_text(json.dumps(candidate_text,ensure_ascii=False,indent=2),encoding="utf-8")
    (OUT/"summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(summary,ensure_ascii=False,indent=2))
    if summary["successful_roots"] < 1: raise SystemExit("no 2016 interactive roots fetched")

if __name__=="__main__": main()
