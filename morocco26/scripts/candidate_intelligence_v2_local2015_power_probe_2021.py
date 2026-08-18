#!/usr/bin/env python3
from __future__ import annotations
import hashlib,json,re,unicodedata,zipfile,xml.etree.ElementTree as ET
from collections import Counter,defaultdict
from difflib import SequenceMatcher
from pathlib import Path
import requests

ROOT=Path(__file__).resolve().parents[2]
G=ROOT/'morocco26'/'data'/'goal100'; CI=G/'e_collect'/'candidate_intelligence_v2'
BRIDGE=CI/'2021'/'pjd_arabic_identity_bridge_74_v1.json'; OVR=CI/'2021'/'pjd_local2015_identity_overrides_v1.json'
OUT=CI/'2021'/'pjd_local2015_power_probe_v1.json'; DETAIL=CI/'2021'/'pjd_local2015_closed_universe_v1.jsonl'
URL='https://open.africa/dataset/07a04224-c0ad-4861-9705-0518f5d49dbd/resource/7ae81ece-1b3d-4cdc-ac49-acd6ba37f6ea/download/communes-elus-2015-1-0.xlsx'
NS={'m':'http://schemas.openxmlformats.org/spreadsheetml/2006/main','r':'http://schemas.openxmlformats.org/officeDocument/2006/relationships','pr':'http://schemas.openxmlformats.org/package/2006/relationships'}
DIAC=re.compile(r'[\u0610-\u061a\u064b-\u065f\u0670\u06d6-\u06ed]')
MIN_POS=30; MIN_KNOWN=74; GUARD=.90

def nar(x):
 s='' if x is None else str(x); s=unicodedata.normalize('NFKC',s).replace('ـ',''); s=DIAC.sub('',s); s=re.sub(r'[إأآٱ]','ا',s).replace('ى','ي').replace('ؤ','و').replace('ئ','ي').replace('هللا','الله')
 s=re.sub(r'\bامل','الم',s); s=re.sub(r'\bاإل','ال',s); s=re.sub(r'اال','ال',s); s=re.sub(r'\s+ي\b','ي',s); s=re.sub(r'[^\u0621-\u063a\u0641-\u064a0-9]+',' ',s).strip(); return re.sub(r'\s+',' ',s)
def ci(ref):
 letters=re.match(r'[A-Z]+',ref).group(0); n=0
 for c in letters:n=n*26+ord(c)-64
 return n-1
def parse_xlsx(data):
 p=Path('/tmp/communes-elus-2015-2021probe.xlsx'); p.write_bytes(data)
 with zipfile.ZipFile(p) as z:
  shared=[]
  if 'xl/sharedStrings.xml' in z.namelist():
   root=ET.fromstring(z.read('xl/sharedStrings.xml'))
   for si in root.findall('m:si',NS): shared.append(''.join(t.text or '' for t in si.findall('.//m:t',NS)))
  wb=ET.fromstring(z.read('xl/workbook.xml')); rels=ET.fromstring(z.read('xl/_rels/workbook.xml.rels')); relmap={x.attrib['Id']:x.attrib['Target'] for x in rels.findall('pr:Relationship',NS)}
  sheet=next(s for s in wb.findall('m:sheets/m:sheet',NS) if s.attrib['name']=='données'); target=relmap[sheet.attrib['{'+NS['r']+'}id']]; path='xl/'+target.lstrip('/') if not target.startswith('xl/') else target
  root=ET.fromstring(z.read(path)); rows=[]
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

def main():
 resp=requests.get(URL,timeout=90,allow_redirects=True,headers={'User-Agent':'M26-CandidateIntel/1.0'}); resp.raise_for_status(); data=resp.content; source_rows=parse_xlsx(data)
 names=defaultdict(list)
 for r in source_rows:
  n=nar(r.get('prenomNom'))
  if n:names[n].append(r)
 all_norm=list(names)
 bridge=json.loads(BRIDGE.read_text(encoding='utf-8'))['rows']; decisions=json.loads(OVR.read_text(encoding='utf-8'))['decisions']; aliases={d['current_name']:d.get('closed_universe_name') for d in decisions if d['status']=='SAFE_ALIAS'}; forced_false={d['current_name'] for d in decisions if d['status']=='CONFIRMED_NO_ALIAS'}
 detail=[]
 for x in bridge:
  raw=x['candidate_name_ar']; q=nar(raw); candidates=names.get(q,[]); method='EXACT_NORMALIZED_ARABIC'
  if not candidates and raw in aliases:
   candidates=names.get(nar(aliases[raw]),[]); method='AUDITED_ALIAS'
  item={**x,'feature_family':'V2_LOCAL2015','matched_rows':len(candidates)}
  if candidates:
   roles=sorted({str(r.get('role','')).strip() for r in candidates if str(r.get('role','')).strip()}); parties=sorted({str(r.get('parti','')).strip() for r in candidates if str(r.get('parti','')).strip()}); communes=sorted({str(r.get('commune','')).strip() for r in candidates if str(r.get('commune','')).strip()})
   exec_roles=[z for z in roles if z.casefold().strip()!='conseiller']
   item.update({'identity_state':'VERIFIED_MATCH','identity_method':method,'council_member_state':'VERIFIED_TRUE','executive_state':'VERIFIED_TRUE' if exec_roles else 'VERIFIED_FALSE','roles':roles,'executive_roles':exec_roles,'2015_parties':parties,'communes':communes})
  elif raw in forced_false:
   item.update({'identity_state':'VERIFIED_NO_MATCH_CLOSED_UNIVERSE_AFTER_AUDIT','identity_method':'AUDITED_CONFIRMED_NO_ALIAS','council_member_state':'VERIFIED_FALSE','executive_state':'VERIFIED_FALSE'})
  else:
   ranked=[]
   for n in all_norm:
    sc=SequenceMatcher(None,q,n).ratio()
    if sc>=.72: ranked.append((sc,n))
   ranked.sort(reverse=True); best,bestn=(ranked[0] if ranked else (0.,None)); second=(ranked[1][0] if len(ranked)>1 else 0.)
   if best>=GUARD:
    item.update({'identity_state':'UNKNOWN_NAME_VARIANT','council_member_state':'UNKNOWN','executive_state':'UNKNOWN','nearest_similarity':round(best,6),'nearest_name':bestn,'similarity_gap':round(best-second,6)})
   else:
    item.update({'identity_state':'VERIFIED_NO_MATCH_CLOSED_UNIVERSE','council_member_state':'VERIFIED_FALSE','executive_state':'VERIFIED_FALSE','nearest_similarity':round(best,6),'nearest_name':bestn,'similarity_gap':round(best-second,6)})
  detail.append(item)
 DETAIL.parent.mkdir(parents=True,exist_ok=True); DETAIL.write_text('\n'.join(json.dumps(x,ensure_ascii=False,sort_keys=True) for x in detail)+'\n',encoding='utf-8')
 def s(key):
  st=Counter(x[key] for x in detail); known=st['VERIFIED_TRUE']+st['VERIFIED_FALSE']; return {'states':dict(st),'known':known,'known_gate':known>=MIN_KNOWN,'positive':st['VERIFIED_TRUE'],'support_gate':st['VERIFIED_TRUE']>=MIN_POS,'gate_pass':known>=MIN_KNOWN and st['VERIFIED_TRUE']>=MIN_POS}
 result={'schema_version':'1.1','transition':'2016_TO_2021','source_url':URL,'source_sha256':hashlib.sha256(data).hexdigest(),'source_rows':len(source_rows),'roster_rows':len(bridge),'thresholds':{'known':MIN_KNOWN,'positive':MIN_POS},'V2_HEAD_ELECTED_LOCAL_COUNCIL_2015':s('council_member_state'),'V2_HEAD_LOCAL_COUNCIL_EXECUTIVE_2015':s('executive_state'),'forecast_modified':False,'coefficient_authorized':False,'identity_bridge':str(BRIDGE.relative_to(ROOT)),'identity_override_artifact':str(OVR.relative_to(ROOT))}
 OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2,sort_keys=True)+'\n',encoding='utf-8'); print(json.dumps(result,ensure_ascii=False,indent=2,sort_keys=True))
if __name__=='__main__': main()
