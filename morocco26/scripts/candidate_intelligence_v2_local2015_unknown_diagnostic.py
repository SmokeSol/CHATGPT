#!/usr/bin/env python3
from __future__ import annotations
import json,re,unicodedata,zipfile,xml.etree.ElementTree as ET
from collections import defaultdict
from difflib import SequenceMatcher
from pathlib import Path
import requests

ROOT=Path(__file__).resolve().parents[2]
G=ROOT/'morocco26'/'data'/'goal100'; CI=G/'e_collect'/'candidate_intelligence_v2'
DETAIL=CI/'2016'/'pjd_local2015_closed_universe_v1.jsonl'; OUT=CI/'2016'/'pjd_local2015_unknown_diagnostic_v1.json'
URL='https://open.africa/dataset/07a04224-c0ad-4861-9705-0518f5d49dbd/resource/7ae81ece-1b3d-4cdc-ac49-acd6ba37f6ea/download/communes-elus-2015-1-0.xlsx'
NS={'m':'http://schemas.openxmlformats.org/spreadsheetml/2006/main','r':'http://schemas.openxmlformats.org/officeDocument/2006/relationships','pr':'http://schemas.openxmlformats.org/package/2006/relationships'}
DIAC=re.compile(r'[\u0610-\u061a\u064b-\u065f\u0670\u06d6-\u06ed]')

def nar(x):
 s='' if x is None else str(x); s=unicodedata.normalize('NFKC',s).replace('ـ',''); s=DIAC.sub('',s); s=re.sub(r'[إأآٱ]','ا',s).replace('ى','ي').replace('ؤ','و').replace('ئ','ي').replace('هللا','الله')
 s=re.sub(r'\bامل','الم',s); s=re.sub(r'\bاإل','ال',s); s=re.sub(r'اال','ال',s); s=re.sub(r'\s+ي\b','ي',s); s=re.sub(r'[^\u0621-\u063a\u0641-\u064a0-9]+',' ',s).strip(); return re.sub(r'\s+',' ',s)
def cidx(ref):
 letters=re.match(r'[A-Z]+',ref).group(0); n=0
 for c in letters:n=n*26+ord(c)-64
 return n-1
def rows_xlsx(data):
 p=Path('/tmp/c.xlsx'); p.write_bytes(data)
 with zipfile.ZipFile(p) as z:
  shared=[]
  if 'xl/sharedStrings.xml' in z.namelist():
   root=ET.fromstring(z.read('xl/sharedStrings.xml'))
   for si in root.findall('m:si',NS):shared.append(''.join(t.text or '' for t in si.findall('.//m:t',NS)))
  wb=ET.fromstring(z.read('xl/workbook.xml')); rels=ET.fromstring(z.read('xl/_rels/workbook.xml.rels')); rm={x.attrib['Id']:x.attrib['Target'] for x in rels.findall('pr:Relationship',NS)}; sh=next(s for s in wb.findall('m:sheets/m:sheet',NS) if s.attrib['name']=='données'); target=rm[sh.attrib['{'+NS['r']+'}id']]; path='xl/'+target.lstrip('/') if not target.startswith('xl/') else target; root=ET.fromstring(z.read(path)); rr=[]
  for row in root.findall('m:sheetData/m:row',NS):
   vals={}
   for c in row.findall('m:c',NS):
    i=cidx(c.attrib.get('r','A1')); typ=c.attrib.get('t'); v=c.find('m:v',NS); inline=c.find('m:is',NS); val=''
    if typ=='s' and v is not None:val=shared[int(v.text)]
    elif typ=='inlineStr' and inline is not None:val=''.join(t.text or '' for t in inline.findall('.//m:t',NS))
    elif v is not None:val=v.text
    vals[i]=val
   mx=max(vals,default=-1); rr.append([vals.get(i,'') for i in range(mx+1)])
  h=rr[0]; return [dict(zip(h,r+['']*(len(h)-len(r)))) for r in rr[1:]]
def main():
 unknown=[json.loads(x) for x in DETAIL.read_text(encoding='utf-8').splitlines() if x.strip() and '"UNKNOWN"' in x]
 data=requests.get(URL,timeout=90,headers={'User-Agent':'M26-CandidateIntel/1.0'}).content; rows=rows_xlsx(data); idx=defaultdict(list)
 for r in rows:
  n=nar(r.get('prenomNom'))
  if n:idx[n].append(r)
 names=list(idx); out=[]
 for u in unknown:
  q=nar(u['candidate_name_ar']); ranked=[]
  for n in names:
   sc=SequenceMatcher(None,q,n).ratio(); ranked.append((sc,n))
  ranked.sort(reverse=True); candidates=[]
  for sc,n in ranked[:3]:
   candidates.append({'score':round(sc,6),'normalized_name':n,'rows':[{'prenomNom':r.get('prenomNom'),'parti':r.get('parti'),'commune':r.get('commune'),'prefProv':r.get('prefProv'),'role':r.get('role'),'teteDeListe':r.get('teteDeListe')} for r in idx[n]]})
  out.append({'candidate_name_ar':u['candidate_name_ar'],'territory_id':u['territory_id'],'top_candidates':candidates})
 OUT.write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8'); print(json.dumps(out,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
