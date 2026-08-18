#!/usr/bin/env python3
from __future__ import annotations
import json,re,unicodedata,zipfile,xml.etree.ElementTree as ET
from collections import defaultdict
from difflib import SequenceMatcher
from pathlib import Path
import requests

ROOT=Path(__file__).resolve().parents[2]; CI=ROOT/'morocco26'/'data'/'goal100'/'e_collect'/'candidate_intelligence_v2'
DETAIL=CI/'2021'/'pjd_local2015_closed_universe_v1.jsonl'; OUT=CI/'2021'/'pjd_local2015_unknown_diagnostic_v1.json'
URL='https://open.africa/dataset/07a04224-c0ad-4861-9705-0518f5d49dbd/resource/7ae81ece-1b3d-4cdc-ac49-acd6ba37f6ea/download/communes-elus-2015-1-0.xlsx'
NS={'m':'http://schemas.openxmlformats.org/spreadsheetml/2006/main','r':'http://schemas.openxmlformats.org/officeDocument/2006/relationships','pr':'http://schemas.openxmlformats.org/package/2006/relationships'}
DIAC=re.compile(r'[\u0610-\u061a\u064b-\u065f\u0670\u06d6-\u06ed]')
def nar(x):
 s='' if x is None else str(x); s=unicodedata.normalize('NFKC',s).replace('ـ',''); s=DIAC.sub('',s); s=re.sub(r'[إأآٱ]','ا',s).replace('ى','ي').replace('ؤ','و').replace('ئ','ي').replace('هللا','الله'); s=re.sub(r'\bامل','الم',s); s=re.sub(r'\bاإل','ال',s); s=re.sub(r'اال','ال',s); s=re.sub(r'\s+ي\b','ي',s); s=re.sub(r'[^\u0621-\u063a\u0641-\u064a0-9]+',' ',s).strip(); return re.sub(r'\s+',' ',s)
def ci(ref):
 letters=re.match(r'[A-Z]+',ref).group(0); n=0
 for c in letters:n=n*26+ord(c)-64
 return n-1
def parse_xlsx(data):
 p=Path('/tmp/communes-elus-2015-diag21.xlsx');p.write_bytes(data)
 with zipfile.ZipFile(p) as z:
  shared=[]
  if 'xl/sharedStrings.xml' in z.namelist():
   root=ET.fromstring(z.read('xl/sharedStrings.xml'))
   for si in root.findall('m:si',NS): shared.append(''.join(t.text or '' for t in si.findall('.//m:t',NS)))
  wb=ET.fromstring(z.read('xl/workbook.xml'));rels=ET.fromstring(z.read('xl/_rels/workbook.xml.rels'));relmap={x.attrib['Id']:x.attrib['Target'] for x in rels.findall('pr:Relationship',NS)};sheet=next(s for s in wb.findall('m:sheets/m:sheet',NS) if s.attrib['name']=='données');target=relmap[sheet.attrib['{'+NS['r']+'}id']];path='xl/'+target.lstrip('/') if not target.startswith('xl/') else target;root=ET.fromstring(z.read(path));rows=[]
  for row in root.findall('m:sheetData/m:row',NS):
   vals={}
   for c in row.findall('m:c',NS):
    idx=ci(c.attrib.get('r','A1'));typ=c.attrib.get('t');v=c.find('m:v',NS);inline=c.find('m:is',NS);value=''
    if typ=='s' and v is not None:value=shared[int(v.text)]
    elif typ=='inlineStr' and inline is not None:value=''.join(t.text or '' for t in inline.findall('.//m:t',NS))
    elif v is not None:value=v.text
    vals[idx]=value
   mx=max(vals,default=-1);rows.append([vals.get(i,'') for i in range(mx+1)])
  hdr=rows[0];return [dict(zip(hdr,r+['']*(len(hdr)-len(r)))) for r in rows[1:]]
def main():
 unknown=[json.loads(line) for line in DETAIL.read_text(encoding='utf-8').splitlines() if line.strip() and json.loads(line).get('council_member_state')=='UNKNOWN']
 resp=requests.get(URL,timeout=90,headers={'User-Agent':'M26-CandidateIntel/1.0'});resp.raise_for_status();rows=parse_xlsx(resp.content);names=defaultdict(list)
 for r in rows:
  n=nar(r.get('prenomNom'))
  if n:names[n].append(r)
 out=[]
 for x in unknown:
  q=nar(x['candidate_name_ar']); ranked=[]
  for n,rs in names.items():
   sc=SequenceMatcher(None,q,n).ratio()
   if sc>=.72: ranked.append((sc,n,rs))
  ranked.sort(key=lambda z:z[0],reverse=True)
  top=[]
  for sc,n,rs in ranked[:3]:
   top.append({'score':round(sc,6),'normalized_name':n,'rows':[{k:r.get(k,'') for k in ('prenomNom','parti','commune','prefProv','role','teteDeListe')} for r in rs[:8]]})
  item={'territory_id':x['territory_id'],'candidate_name_fr':x['candidate_name_fr'],'candidate_name_ar':x['candidate_name_ar'],'source_id':x.get('source_id'),'top_candidates':top}; out.append(item)
  def fmt(t):
   if not t:return '-'
   rr=t['rows'][0] if t.get('rows') else {}
   return f"{t['normalized_name']}|{rr.get('parti','')}|{rr.get('prefProv','')}|{rr.get('commune','')}|{rr.get('role','')}|{t['score']}"
  print('DIAG21\t'+x['territory_id']+'\t'+x['candidate_name_fr']+'\t'+x['candidate_name_ar']+'\tTOP1='+fmt(top[0] if top else None)+'\tTOP2='+fmt(top[1] if len(top)>1 else None))
 OUT.write_text(json.dumps(out,ensure_ascii=False,indent=2,sort_keys=True)+'\n',encoding='utf-8');print('UNKNOWN_ROWS='+str(len(out)))
if __name__=='__main__':main()
