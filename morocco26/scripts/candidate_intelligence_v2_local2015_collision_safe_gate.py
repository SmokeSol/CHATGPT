#!/usr/bin/env python3
from __future__ import annotations
import csv, hashlib, json, re, unicodedata, zipfile, xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from difflib import SequenceMatcher
from pathlib import Path
import requests

ROOT=Path(__file__).resolve().parents[2]
CI=ROOT/'morocco26'/'data'/'goal100'/'e_collect'/'candidate_intelligence_v2'
CONST=ROOT/'morocco26'/'data'/'constituencies_goal75.csv'
URL='https://open.africa/dataset/07a04224-c0ad-4861-9705-0518f5d49dbd/resource/7ae81ece-1b3d-4cdc-ac49-acd6ba37f6ea/download/communes-elus-2015-1-0.xlsx'
OUT=CI/'candidate_intelligence_v2_local2015_collision_safe_gate_v1.json'
NS={'m':'http://schemas.openxmlformats.org/spreadsheetml/2006/main','r':'http://schemas.openxmlformats.org/officeDocument/2006/relationships','pr':'http://schemas.openxmlformats.org/package/2006/relationships'}
DIAC=re.compile(r'[\u0610-\u061a\u064b-\u065f\u0670\u06d6-\u06ed]')
MIN_KNOWN=74; MIN_POS=30; GUARD=.90

def nar(x):
 s='' if x is None else str(x); s=unicodedata.normalize('NFKC',s).replace('ـ',''); s=DIAC.sub('',s); s=re.sub(r'[إأآٱ]','ا',s).replace('ى','ي').replace('ؤ','و').replace('ئ','ي').replace('هللا','الله'); s=re.sub(r'\bامل','الم',s); s=re.sub(r'\bاإل','ال',s); s=re.sub(r'اال','ال',s); s=re.sub(r'\s+ي\b','ي',s); s=re.sub(r'[^\u0621-\u063a\u0641-\u064a0-9]+',' ',s).strip(); return re.sub(r'\s+',' ',s)
def nlat(x):
 s='' if x is None else str(x); s=unicodedata.normalize('NFKD',s); s=''.join(c for c in s if not unicodedata.combining(c)); s=s.lower(); s=re.sub(r'[^a-z0-9]+',' ',s).strip(); return re.sub(r'\s+',' ',s)
def ci(ref):
 letters=re.match(r'[A-Z]+',ref).group(0); n=0
 for c in letters:n=n*26+ord(c)-64
 return n-1
def parse_xlsx(data):
 p=Path('/tmp/communes-elus-2015-collision-safe.xlsx'); p.write_bytes(data)
 with zipfile.ZipFile(p) as z:
  shared=[]
  if 'xl/sharedStrings.xml' in z.namelist():
   root=ET.fromstring(z.read('xl/sharedStrings.xml'))
   for si in root.findall('m:si',NS):shared.append(''.join(t.text or '' for t in si.findall('.//m:t',NS)))
  wb=ET.fromstring(z.read('xl/workbook.xml')); rels=ET.fromstring(z.read('xl/_rels/workbook.xml.rels')); relmap={x.attrib['Id']:x.attrib['Target'] for x in rels.findall('pr:Relationship',NS)}; sheet=next(s for s in wb.findall('m:sheets/m:sheet',NS) if s.attrib['name']=='données'); target=relmap[sheet.attrib['{'+NS['r']+'}id']]; path='xl/'+target.lstrip('/') if not target.startswith('xl/') else target; root=ET.fromstring(z.read(path)); rows=[]
  for row in root.findall('m:sheetData/m:row',NS):
   vals={}
   for c in row.findall('m:c',NS):
    idx=ci(c.attrib.get('r','A1')); typ=c.attrib.get('t'); v=c.find('m:v',NS); inline=c.find('m:is',NS); value=''
    if typ=='s' and v is not None:value=shared[int(v.text)]
    elif typ=='inlineStr' and inline is not None:value=''.join(t.text or '' for t in inline.findall('.//m:t',NS))
    elif v is not None:value=v.text
    vals[idx]=value
   mx=max(vals,default=-1); rows.append([vals.get(i,'') for i in range(mx+1)])
  hdr=rows[0]; return [dict(zip(hdr,r+['']*(len(hdr)-len(r)))) for r in rows[1:]]
def load_regions():
 with CONST.open(encoding='utf-8',newline='') as f:return {r['constituency_id']:nlat(r['region']) for r in csv.DictReader(f)}
def load_aliases(path,year):
 doc=json.loads(path.read_text(encoding='utf-8')); decisions=doc['decisions'] if year==2021 else doc['decisions']; out={}
 for d in decisions:
  out[d['current_name']]={'status':d['status'],'closed_universe_name':d.get('closed_universe_name')}
 return out
def load_candidates(year):
 if year==2016:
  rows=json.loads((CI/'2016'/'pjd_closed_roster_v1.json').read_text(encoding='utf-8'))['rows']; alias=load_aliases(CI/'2016'/'pjd_local2015_identity_overrides_v1.json',2016)
 else:
  rows=json.loads((CI/'2021'/'pjd_arabic_identity_bridge_74_v1.json').read_text(encoding='utf-8'))['rows']; alias=load_aliases(CI/'2021'/'pjd_local2015_identity_overrides_v1.json',2021)
 return rows,alias
def uniq_rows(rows):
 seen={}
 for r in rows:
  key=(nar(r.get('prenomNom')),str(r.get('parti','')).upper(),nlat(r.get('region')),nlat(r.get('prefProv')),nlat(r.get('commune')))
  seen[key]=r
 return list(seen.values())
def classify(year,source_rows,regions):
 candidates,aliases=load_candidates(year); idx=defaultdict(list)
 for r in source_rows:
  n=nar(r.get('prenomNom'))
  if n:idx[n].append(r)
 all_names=list(idx); detail=[]
 for x in candidates:
  raw=x['candidate_name_ar']; ad=aliases.get(raw); resolved=ad.get('closed_universe_name') if ad and ad.get('status')=='SAFE_ALIAS' else raw; q=nar(resolved); rows=uniq_rows(idx.get(q,[])); target_region=regions[x['territory_id']]
  pjd_same=[r for r in rows if str(r.get('parti','')).upper()=='PJD' and nlat(r.get('region'))==target_region]
  pjd_same_communes={nlat(r.get('commune')) for r in pjd_same}
  item={'year':year,'territory_id':x['territory_id'],'candidate_name_ar':raw,'resolved_name_ar':resolved,'target_region':target_region,'raw_name_match_rows':len(rows),'pjd_same_region_rows':len(pjd_same),'pjd_same_region_communes':sorted(pjd_same_communes)}
  if len(rows)==1:
   r=rows[0]; item.update({'state':'VERIFIED_TRUE','method':'UNIQUE_GLOBAL_NAME_IN_COMPLETE_UNIVERSE','source_party':r.get('parti'),'source_region':r.get('region'),'source_prefProv':r.get('prefProv'),'source_commune':r.get('commune'),'source_role':r.get('role')})
  elif len(pjd_same_communes)==1 and pjd_same:
   r=pjd_same[0]; item.update({'state':'VERIFIED_TRUE','method':'UNIQUE_PJD_SAME_REGION_IDENTITY_AMONG_HOMONYMS','source_party':'PJD','source_region':r.get('region'),'source_prefProv':r.get('prefProv'),'source_commune':r.get('commune'),'source_role':r.get('role'),'homonym_rows_global':len(rows)})
  elif rows:
   item.update({'state':'UNKNOWN','method':'UNRESOLVED_HOMONYM_COLLISION','homonym_rows_global':len(rows),'candidate_rows':[{'party':r.get('parti'),'region':r.get('region'),'prefProv':r.get('prefProv'),'commune':r.get('commune'),'role':r.get('role')} for r in rows[:12]]})
  elif ad and ad.get('status')=='CONFIRMED_NO_ALIAS':
   item.update({'state':'VERIFIED_FALSE','method':'AUDITED_CONFIRMED_NO_ALIAS_IN_COMPLETE_UNIVERSE'})
  else:
   best=0.; bestn=None
   for n in all_names:
    sc=SequenceMatcher(None,q,n).ratio()
    if sc>best:best,bestn=sc,n
   if best>=GUARD:item.update({'state':'UNKNOWN','method':'UNRESOLVED_HIGH_SIMILARITY_NO_EXACT_IDENTITY','nearest_name':bestn,'nearest_similarity':round(best,6)})
   else:item.update({'state':'VERIFIED_FALSE','method':'NO_MATCH_IN_COMPLETE_UNIVERSE_LOW_SIMILARITY','nearest_name':bestn,'nearest_similarity':round(best,6)})
  detail.append(item)
 st=Counter(x['state'] for x in detail); known=st['VERIFIED_TRUE']+st['VERIFIED_FALSE']; return {'rows':detail,'summary':{'states':dict(st),'known':known,'positive':st['VERIFIED_TRUE'],'coverage_gate':known>=MIN_KNOWN,'support_gate':st['VERIFIED_TRUE']>=MIN_POS,'gate_pass':known>=MIN_KNOWN and st['VERIFIED_TRUE']>=MIN_POS}}
def main():
 resp=requests.get(URL,timeout=90,allow_redirects=True,headers={'User-Agent':'M26-CandidateIntel/1.0'});resp.raise_for_status();data=resp.content;source=parse_xlsx(data);regions=load_regions(); results={str(y):classify(y,source,regions) for y in (2016,2021)}
 out={'schema_version':'1.0','gate_id':'M26-CANDIDATE-INTEL-V2-LOCAL2015-COLLISION-SAFE-GATE-V1','source_sha256':hashlib.sha256(data).hexdigest(),'source_rows':len(source),'identity_rule':'TRUE requires either a globally unique normalized closed-universe name or exactly one PJD council identity in the same election region among same-name homonyms. Multi-identity collisions remain UNKNOWN.','thresholds':{'minimum_known':MIN_KNOWN,'minimum_positive':MIN_POS},'transitions':{y:results[y]['summary'] for y in results},'status':'PASS_COLLISION_SAFE_LOCAL2015_DATA_POWER' if all(results[y]['summary']['gate_pass'] for y in results) else 'FAIL_COLLISION_SAFE_LOCAL2015_DATA_POWER','forecast_modified':False,'reasoner_gate_invalidated_until_recomputed':True}
 for y in results:
  p=CI/y/'pjd_local2015_collision_safe_v1.jsonl';p.write_text('\n'.join(json.dumps(x,ensure_ascii=False,sort_keys=True) for x in results[y]['rows'])+'\n',encoding='utf-8')
 OUT.write_text(json.dumps(out,ensure_ascii=False,indent=2,sort_keys=True)+'\n',encoding='utf-8'); print(json.dumps(out,ensure_ascii=False,indent=2,sort_keys=True))
if __name__=='__main__':main()
