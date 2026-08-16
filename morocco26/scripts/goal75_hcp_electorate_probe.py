#!/usr/bin/env python3
import json,zipfile,re
from io import BytesIO
from pathlib import Path
import requests
from lxml import etree
R=Path(__file__).resolve().parents[1];O=R/'data'/'goal75';O.mkdir(exist_ok=True)
URL='https://www.hcp.ma/attachment/2232968/'
def main():
 s=requests.Session();s.headers.update({'User-Agent':'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/125 Safari/537.36'})
 r=s.get(URL,timeout=45,allow_redirects=True);out={'url':URL,'status':r.status_code,'final_url':r.url,'content_type':r.headers.get('content-type'),'bytes':len(r.content)}
 if r.status_code==200 and r.content[:2]==b'PK':
  z=zipfile.ZipFile(BytesIO(r.content));xml=z.read('word/document.xml');root=etree.fromstring(xml);ns={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
  pars=[]
  for p in root.xpath('.//w:p',namespaces=ns):
   txt=''.join(p.xpath('.//w:t/text()',namespaces=ns)).strip()
   if txt:pars.append(txt)
  out['paragraphs']=pars
  keys=['Marrakech','Safi','Casablanca','Rabat','Souss','Fès','Tanger','Oriental','Béni','Dakhla','Laâyoune','Drâa','Guelmim','région','inscrits']
  out['matches']=[p for p in pars if any(k.lower() in p.lower() for k in keys)]
  out['tables']=[]
  for tbl in root.xpath('.//w:tbl',namespaces=ns):
   rows=[]
   for tr in tbl.xpath('./w:tr',namespaces=ns):
    cells=[''.join(tc.xpath('.//w:t/text()',namespaces=ns)).strip() for tc in tr.xpath('./w:tc',namespaces=ns)]
    rows.append(cells)
   out['tables'].append(rows)
 (O/'hcp_electorate_probe.json').write_text(json.dumps(out,ensure_ascii=False,indent=2));print(json.dumps({k:v for k,v in out.items() if k not in ('paragraphs','tables')},ensure_ascii=False,indent=2));raise SystemExit(0 if out.get('matches') else 5)
if __name__=='__main__':main()
