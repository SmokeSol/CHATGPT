#!/usr/bin/env python3
from __future__ import annotations
import json,re,unicodedata,zipfile,xml.etree.ElementTree as ET
from collections import Counter,defaultdict
from pathlib import Path
import requests

ROOT=Path(__file__).resolve().parents[2]; G=ROOT/'morocco26'/'data'/'goal100'; CI=G/'e_collect'/'candidate_intelligence_v2'
CONTRACT=G/'e_collect'/'candidate_intelligence_v2_feature_c_expansion_contract_v1.json'; BFINAL=CI/'candidate_intelligence_v2_power_gate_collision_resolved_final_v1.json'; LRES=CI/'local2015_collision_resolution_v1.json'; OUT=CI/'candidate_intelligence_v2_feature_c_power_gate_v1.json'
URL='https://open.africa/dataset/07a04224-c0ad-4861-9705-0518f5d49dbd/resource/7ae81ece-1b3d-4cdc-ac49-acd6ba37f6ea/download/communes-elus-2015-1-0.xlsx'
NS={'m':'http://schemas.openxmlformats.org/spreadsheetml/2006/main','r':'http://schemas.openxmlformats.org/officeDocument/2006/relationships','pr':'http://schemas.openxmlformats.org/package/2006/relationships'}; DIAC=re.compile(r'[\u0610-\u061a\u064b-\u065f\u0670\u06d6-\u06ed]')

def nar(x):
 s='' if x is None else str(x);s=unicodedata.normalize('NFKC',s).replace('ـ','');s=DIAC.sub('',s);s=re.sub(r'[إأآٱ]','ا',s).replace('ى','ي').replace('ؤ','و').replace('ئ','ي').replace('هللا','الله');s=re.sub(r'\bامل','الم',s);s=re.sub(r'\bاإل','ال',s);s=re.sub(r'اال','ال',s);s=re.sub(r'\s+ي\b','ي',s);s=re.sub(r'[^\u0621-\u063a\u0641-\u064a0-9]+',' ',s).strip();return re.sub(r'\s+',' ',s)
def nlat(x):
 s='' if x is None else str(x);s=unicodedata.normalize('NFKD',s);s=''.join(c for c in s if not unicodedata.combining(c));s=s.lower();s=re.sub(r'[^a-z0-9]+',' ',s).strip();return re.sub(r'\s+',' ',s)
def ci(ref):
 letters=re.match(r'[A-Z]+',ref).group(0);n=0
 for c in letters:n=n*26+ord(c)-64
 return n-1
def parse_xlsx(data):
 p=Path('/tmp/communes-elus-2015-feature-c.xlsx');p.write_bytes(data)
 with zipfile.ZipFile(p) as z:
  shared=[]
  if 'xl/sharedStrings.xml' in z.namelist():
   root=ET.fromstring(z.read('xl/sharedStrings.xml'))
   for si in root.findall('m:si',NS):shared.append(''.join(t.text or '' for t in si.findall('.//m:t',NS)))
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
def load_jsonl(p):return [json.loads(x) for x in Path(p).read_text(encoding='utf-8').splitlines() if x.strip()]

def final_b(year):
 base={r['territory_id']:r for r in load_jsonl(CI/str(year)/'pjd_local2015_collision_safe_v1.jsonl')}; label='2011_TO_2016' if year==2016 else '2016_TO_2021'
 for d in json.loads(LRES.read_text(encoding='utf-8'))['decisions']:
  if d['transition']==label and d['territory_id'] in base and base[d['territory_id']]['state']=='UNKNOWN':base[d['territory_id']]={**base[d['territory_id']],'state':d['state'],'resolution':d}
 return base

def special_rows(year,tid,index):
 if year!=2016:return None
 specs={
  'ouezzane':('عبد الحليم علاوي','PJD','ouazzane'),
  'chtouka-ait-baha':('محمد لشكر','PJD','ait amira'),
  'al-haouz':('مراد لكورش','PJD','ait sidi daoud')}
 if tid not in specs:return None
 name,party,comm=specs[tid];rows=index.get(nar(name),[]); sel=[r for r in rows if str(r.get('parti','')).upper()==party and nlat(r.get('commune'))==comm];return sel

def resolve_identity_rows(year,row,index):
 tid=row['territory_id'];sp=special_rows(year,tid,index)
 if sp is not None:return sp,'AUDITED_SPECIAL_IDENTITY'
 q=nar(row.get('resolved_name_ar') or row.get('candidate_name_ar'));rows=index.get(q,[])
 method=row.get('method','')
 if method=='UNIQUE_GLOBAL_NAME_IN_COMPLETE_UNIVERSE' and len(rows)==1:return rows,'UNIQUE_GLOBAL_NAME'
 if method=='UNIQUE_PJD_SAME_REGION_IDENTITY_AMONG_HOMONYMS':
  target=row.get('target_region');comms=set(row.get('pjd_same_region_communes') or []);sel=[r for r in rows if str(r.get('parti','')).upper()=='PJD' and nlat(r.get('region'))==target and nlat(r.get('commune')) in comms];return sel,'PJD_SAME_REGION_IDENTITY'
 # Audited aliases from the earlier identity layer often already have one exact row after resolved_name_ar substitution.
 pjd=[r for r in rows if str(r.get('parti','')).upper()=='PJD'];
 if len(rows)==1:return rows,'AUDITED_ALIAS_UNIQUE'
 if len(pjd)==1:return pjd,'AUDITED_ALIAS_UNIQUE_PJD'
 return [],'UNRESOLVED_IDENTITY_FOR_C'

def classify(year,index):
 b=final_b(year);detail=[]
 for tid,row in sorted(b.items()):
  if row['state']=='VERIFIED_FALSE':detail.append({'territory_id':tid,'B_state':'VERIFIED_FALSE','C_state':'VERIFIED_FALSE','method':'NOT_ELECTED_LOCAL_COUNCIL'});continue
  if row['state']!='VERIFIED_TRUE':detail.append({'territory_id':tid,'B_state':row['state'],'C_state':'UNKNOWN','method':'B_NOT_RESOLVED'});continue
  sel,method=resolve_identity_rows(year,row,index);vals={str(r.get('teteDeListe','')).strip() for r in sel if str(r.get('teteDeListe','')).strip() in {'0','1'}}
  if not sel or not vals:state='UNKNOWN'
  elif vals=={'1'}:state='VERIFIED_TRUE'
  elif vals=={'0'}:state='VERIFIED_FALSE'
  else:state='UNKNOWN'
  detail.append({'territory_id':tid,'B_state':'VERIFIED_TRUE','C_state':state,'method':method,'matched_identity_rows':len(sel),'teteDeListe_values':sorted(vals),'source_rows':[{'name':r.get('prenomNom'),'party':r.get('parti'),'region':r.get('region'),'prefProv':r.get('prefProv'),'commune':r.get('commune'),'role':r.get('role'),'teteDeListe':r.get('teteDeListe')} for r in sel[:6]]})
 st=Counter(x['C_state'] for x in detail);known=st['VERIFIED_TRUE']+st['VERIFIED_FALSE'];return detail,{'rows':len(detail),'states':dict(st),'known':known,'positive':st['VERIFIED_TRUE'],'coverage_gate':known>=74,'support_gate':st['VERIFIED_TRUE']>=30,'gate_pass':known>=74 and st['VERIFIED_TRUE']>=30}
def main():
 contract=json.loads(CONTRACT.read_text(encoding='utf-8'));assert json.loads(BFINAL.read_text(encoding='utf-8'))['status']=='PASS_REASONER_POWER_COLLISION_SAFE';resp=requests.get(URL,timeout=90,headers={'User-Agent':'M26-CandidateIntel/1.0'});resp.raise_for_status();rows=parse_xlsx(resp.content);idx=defaultdict(list)
 for r in rows:
  n=nar(r.get('prenomNom'))
  if n:idx[n].append(r)
 res={}
 for y in (2016,2021):
  detail,summary=classify(y,idx);(CI/str(y)/'pjd_feature_c_local_list_head_v1.jsonl').write_text('\n'.join(json.dumps(x,ensure_ascii=False,sort_keys=True) for x in detail)+'\n',encoding='utf-8');res[str(y)]=summary
 passed=all(res[y]['gate_pass'] for y in res);out={'schema_version':'1.0','result_id':'M26-CANDIDATE-INTELLIGENCE-V2-FEATURE-C-POWER-GATE-V1','contract_id':contract['contract_id'],'feature_C':contract['feature_C']['id'],'transitions':res,'status':'PASS_FEATURE_C_DATA_POWER' if passed else 'FAIL_FEATURE_C_DATA_POWER','forecast_modified':False,'predictive_scoring_performed':False};OUT.write_text(json.dumps(out,ensure_ascii=False,indent=2,sort_keys=True)+'\n',encoding='utf-8');print(json.dumps(out,ensure_ascii=False,indent=2,sort_keys=True))
if __name__=='__main__':main()
