#!/usr/bin/env python3
from __future__ import annotations
import csv, json, re, unicodedata
from collections import Counter, defaultdict
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any
import pandas as pd
import requests

ROOT=Path(__file__).resolve().parents[2]
M=ROOT/'morocco26'; G=M/'data'/'goal100'; CI=G/'e_collect'/'candidate_intelligence_v2'
CONTRACT=G/'e_collect'/'candidate_intelligence_v2_multipart_head_contract_v1.json'
PJD16=CI/'2016'/'pjd_closed_roster_v1.json'
PJD16_ALIAS=CI/'identity_overrides_v1.json'
HEAD21=G/'e_reason'/'evidence'/'2021_head_list_rank_enrichment'/'enriched_candidate_roster.json'
RAW=G/'b2_raw_acquisition'/'HF_CHAMBER_MEMBERS_MULTIYEAR'/'data'
CONST=M/'data'/'constituencies_goal75.csv'
OUT=CI/'candidate_intelligence_v2_multipart_head_power_gate_v1.json'
DETAIL16=CI/'multipart'/'2016_head_prior_mp_features_v1.jsonl'
DETAIL21=CI/'multipart'/'2021_head_prior_mp_features_v1.jsonl'
RNI16_URL='https://raw.githubusercontent.com/SmokeSol/CHATGPT/morocco26-agent-society-v2/morocco26/data/goal100/agent_society_v2/acquisition/2016_candidate_party_augmented_wave2.json'
FEATURES=['M1_HEAD_PRIOR_MP_SAME_PARTY_SAME_DISTRICT','M2_HEAD_PRIOR_MP_SAME_PARTY_OTHER_SEAT','M3_HEAD_PRIOR_MP_SWITCH_IN']
LAT_GUARD=.86; AR_GUARD=.88; CORROBORATED_GUARD=.78; MARGIN=.06
AR_DIAC=re.compile(r'[\u0610-\u061a\u064b-\u065f\u0670\u06d6-\u06ed]')

def nar(v:Any)->str:
 s='' if v is None else str(v);s=unicodedata.normalize('NFKC',s).replace('ـ','');s=AR_DIAC.sub('',s);s=re.sub(r'[إأآٱ]','ا',s).replace('ى','ي').replace('ؤ','و').replace('ئ','ي').replace('هللا','الله');s=re.sub(r'\bامل','الم',s);s=re.sub(r'\bاإل','ال',s);s=re.sub(r'اال','ال',s);s=re.sub(r'\s+ي\b','ي',s);s=re.sub(r'[^\u0621-\u063a\u0641-\u064a0-9]+',' ',s).strip();return re.sub(r'\s+',' ',s)
def nlat(v:Any)->str:
 s='' if v is None else str(v);s=unicodedata.normalize('NFKD',s);s=''.join(c for c in s if not unicodedata.combining(c));s=s.casefold().replace('’',"'");s=re.sub(r'\bmohamm?ed\b|\bmohamad\b','mohamed',s);s=re.sub(r'\babdellah\b|\babdallah\b|\babdullah\b','abdallah',s);s=re.sub(r'[^a-z0-9]+',' ',s).strip();return re.sub(r'\s+',' ',s)
def first_col(df,*names):
 low={str(c).lower():str(c) for c in df.columns}
 for n in names:
  if n.lower() in low:return low[n.lower()]
 raise KeyError(f'{names} not in {list(df.columns)}')
def load_universe(parliament):
 df=pd.concat([pd.read_parquet(p) for p in sorted(RAW.glob('*.parquet'))],ignore_index=True)
 pc=first_col(df,'parlement');rc=first_col(df,'motifentree','motif_entree');lc=first_col(df,'prenomnom','prenom_nom');ac=first_col(df,'prenomnomar','prenom_nom_ar');tc=first_col(df,'circonscription')
 party=None
 for c in ('parti','partipolitique','appartenancepolitique','formationpolitique'):
  try:party=first_col(df,c);break
  except KeyError:pass
 if not party:raise KeyError('party column absent')
 u=df[df[pc].astype(str).str.strip().eq(parliament)].copy();u=u[u[rc].astype(str).str.casefold().str.strip().eq('elu')].copy()
 if len(u)!=395:raise RuntimeError(f'{parliament} universe !=395: {len(u)}')
 rows=[]
 for _,r in u.iterrows():rows.append({'name_lat':str(r.get(lc,'') or ''),'name_ar':str(r.get(ac,'') or ''),'party':str(r.get(party,'') or '').strip().upper(),'territory_source':str(r.get(tc,'') or '')})
 return rows
def load_constituencies():
 with CONST.open(encoding='utf-8',newline='') as f:return list(csv.DictReader(f))
def territory_resolver():
 const=load_constituencies(); names={nlat(r['name']):r['constituency_id'] for r in const}; arr=list(names)
 def resolve(src):
  n=nlat(src)
  if not n:return None,'EMPTY'
  if 'liste nationale' in n or n=='national':return 'NATIONAL_LIST','NATIONAL_LIST'
  if n in names:return names[n],'EXACT'
  ranked=sorted(((SequenceMatcher(None,n,x).ratio(),x) for x in arr),reverse=True)
  if ranked and ranked[0][0]>=.86 and (len(ranked)==1 or ranked[0][0]-ranked[1][0]>=.05):return names[ranked[0][1]],'FUZZY_CANONICAL'
  return None,'UNRESOLVED'
 return resolve
def pjd16_aliases():
 d=json.loads(PJD16_ALIAS.read_text(encoding='utf-8'));return {nar(x['current_name']):nar(x['prior_name']) for x in d.get('2016',[]) if x.get('status')=='SAFE_ALIAS' and x.get('prior_name')}
def load_candidates16():
 pjd=[]
 for r in json.loads(PJD16.read_text(encoding='utf-8'))['rows']:pjd.append({'transition':'2011_TO_2016','year':2016,'party':'PJD','territory_id':r['territory_id'],'candidate_name_ar':r['candidate_name_ar'],'candidate_name_lat':None,'source_class':'PJD_OFFICIAL_CLOSED_HEAD_ROSTER','prior_link_corroborated':False})
 resp=requests.get(RNI16_URL,timeout=90,headers={'User-Agent':'M26-CandidateIntel/1.0'});resp.raise_for_status();d=resp.json();rni=[r for r in d['records'] if r.get('party')=='RNI' and r.get('source_url')=='https://al3omk.com/94402.html']
 if len(rni)!=81:raise RuntimeError(f'expected 81 RNI head rows, got {len(rni)}')
 seen=set();out=pjd[:]
 for r in rni:
  key=('RNI',r['constituency_id'])
  if key in seen:raise RuntimeError(f'duplicate RNI head {key}')
  seen.add(key);out.append({'transition':'2011_TO_2016','year':2016,'party':'RNI','territory_id':r['constituency_id'],'candidate_name_ar':r['candidate'],'candidate_name_lat':None,'source_class':'RNI_NATIONAL_81_HEAD_LIST_PUBLICATION','prior_link_corroborated':False})
 return out
def load_candidates21():
 rows=json.loads(HEAD21.read_text(encoding='utf-8'));out=[];seen=set()
 for r in rows:
  if r.get('party_bucket') not in {'PJD','RNI'}:continue
  if int(r.get('CANDIDATE_REGISTERED_RANK') or 0)!=1 or r.get('rank_evidence_status')!='EXPLICIT_CANDIDATS_TETES_DE_LISTE':continue
  key=(r['party_bucket'],r['territory_id'])
  if key in seen:raise RuntimeError(f'duplicate certified 2021 head {key}')
  seen.add(key);out.append({'transition':'2016_TO_2021','year':2021,'party':r['party_bucket'],'territory_id':r['territory_id'],'candidate_name_lat':r['candidate_name_source'],'candidate_name_ar':None,'source_class':'CERTIFIED_EXPLICIT_HEAD_ROSTER','prior_link_corroborated':bool(r.get('prior_elected_person_id')),'existing_same_party_same_district':bool(r.get('INCUMBENT_SAME_PARTY_SAME_DISTRICT')),'existing_switch_in':bool(r.get('PARTY_SWITCH_IN')),'incumbent_match_score':r.get('incumbent_match_score')})
 return out
def best(name,universe,key,norm):
 q=norm(name);ranked=[]
 for i,r in enumerate(universe):
  v=norm(r[key]);
  if not v:continue
  ranked.append((SequenceMatcher(None,q,v).ratio(),i))
 ranked.sort(reverse=True);return ranked[:3]
def classify(cands,universe,script):
 norm=nar if script=='ar' else nlat; key='name_ar' if script=='ar' else 'name_lat';idx=defaultdict(list)
 for i,r in enumerate(universe):
  n=norm(r[key]);
  if n:idx[n].append(i)
 alias=pjd16_aliases() if script=='ar' else {};resolve_territory=territory_resolver();out=[]
 for c in cands:
  raw=c['candidate_name_ar'] if script=='ar' else c['candidate_name_lat'];q=norm(raw);q_lookup=alias.get(q,q) if c['party']=='PJD' else q;hits=idx.get(q_lookup,[]);method=None;chosen=None;ranked=[]
  if len(hits)==1:chosen=universe[hits[0]];method='EXACT_NORMALIZED_UNIQUE'
  elif len(hits)>1:
   contextual=[]
   for i in hits:
    r=universe[i];tid,_=resolve_territory(r['territory_source'])
    if tid==c['territory_id']:contextual.append(i)
   if len(contextual)==1:chosen=universe[contextual[0]];method='EXACT_COLLISION_UNIQUE_SAME_TERRITORY'
   else:method='EXACT_COLLISION_UNKNOWN'
  else:
   ranked=best(raw,universe,key,norm);top=ranked[0][0] if ranked else 0.;second=ranked[1][0] if len(ranked)>1 else 0.;guard=AR_GUARD if script=='ar' else LAT_GUARD
   if c.get('prior_link_corroborated') and ranked and top>=CORROBORATED_GUARD and top-second>=MARGIN:chosen=universe[ranked[0][1]];method='CORROBORATED_PRIOR_LINK_PLUS_UNIQUE_NAME_VARIANT'
   elif top>=guard:method='HIGH_SIMILARITY_UNKNOWN'
   else:method='VERIFIED_NO_PRIOR_MP_COMPLETE_UNIVERSE'
  item={**c,'identity_method':method,'prior_member':chosen,'nearest':[{'score':round(s,6),'name':universe[i][key],'party':universe[i]['party'],'territory_source':universe[i]['territory_source']} for s,i in ranked[:3]]}
  states={f:'UNKNOWN' for f in FEATURES}
  if method=='VERIFIED_NO_PRIOR_MP_COMPLETE_UNIVERSE':states={f:'VERIFIED_FALSE' for f in FEATURES}
  elif chosen is not None:
   prior_party=chosen['party'];prior_tid,tmethod=resolve_territory(chosen['territory_source']);item['prior_territory_id']=prior_tid;item['prior_territory_method']=tmethod
   if prior_party!=c['party']:
    states[FEATURES[0]]='VERIFIED_FALSE';states[FEATURES[1]]='VERIFIED_FALSE';states[FEATURES[2]]='VERIFIED_TRUE'
   elif prior_tid==c['territory_id']:
    states[FEATURES[0]]='VERIFIED_TRUE';states[FEATURES[1]]='VERIFIED_FALSE';states[FEATURES[2]]='VERIFIED_FALSE'
   elif prior_tid is not None:
    states[FEATURES[0]]='VERIFIED_FALSE';states[FEATURES[1]]='VERIFIED_TRUE';states[FEATURES[2]]='VERIFIED_FALSE'
   else:
    states[FEATURES[2]]='VERIFIED_FALSE'
  item['feature_states']=states;out.append(item)
 return out
def summarize(rows,contract):
 parties=contract['parties'];pg=contract['power_gate'];known_head={};
 for p in parties:
  pr=[r for r in rows if r['party']==p]; known=sum(all(v in {'VERIFIED_TRUE','VERIFIED_FALSE'} for v in r['feature_states'].values()) for r in pr);known_head[p]={'rows':len(pr),'fully_known_all_features':known,'per_party_gate':known>=pg['minimum_known_head_cells_per_party_each_transition']}
 total_fully=sum(all(v in {'VERIFIED_TRUE','VERIFIED_FALSE'} for v in r['feature_states'].values()) for r in rows)
 features={}
 for f in FEATURES:
  st=Counter(r['feature_states'][f] for r in rows);features[f]={'states':dict(st),'known':st['VERIFIED_TRUE']+st['VERIFIED_FALSE'],'positive':st['VERIFIED_TRUE'],'support_gate':st['VERIFIED_TRUE']>=pg['minimum_positive_instances_per_binary_feature_each_transition']}
 return {'rows':len(rows),'fully_known_all_features':total_fully,'total_known_gate':total_fully>=pg['minimum_known_head_cells_each_transition'],'parties':known_head,'features':features,'unknown_rows':[{'party':r['party'],'territory_id':r['territory_id'],'candidate_name':r.get('candidate_name_ar') or r.get('candidate_name_lat'),'identity_method':r['identity_method'],'feature_states':r['feature_states'],'nearest':r['nearest']} for r in rows if not all(v in {'VERIFIED_TRUE','VERIFIED_FALSE'} for v in r['feature_states'].values())]}
def main():
 c=json.loads(CONTRACT.read_text(encoding='utf-8'));u11=load_universe('2011-2016');u16=load_universe('2016-2021');r16=classify(load_candidates16(),u11,'ar');r21=classify(load_candidates21(),u16,'lat');DETAIL16.parent.mkdir(parents=True,exist_ok=True);DETAIL16.write_text('\n'.join(json.dumps(x,ensure_ascii=False,sort_keys=True) for x in r16)+'\n',encoding='utf-8');DETAIL21.write_text('\n'.join(json.dumps(x,ensure_ascii=False,sort_keys=True) for x in r21)+'\n',encoding='utf-8');s16=summarize(r16,c);s21=summarize(r21,c);eligible=[f for f in FEATURES if s16['features'][f]['support_gate'] and s21['features'][f]['support_gate']];coverage=s16['total_known_gate'] and s21['total_known_gate'] and all(v['per_party_gate'] for v in s16['parties'].values()) and all(v['per_party_gate'] for v in s21['parties'].values());out={'schema_version':'1.0','result_id':'M26-CANDIDATE-INTELLIGENCE-V2-MULTIPART-HEAD-POWER-GATE-V1','contract_id':c['contract_id'],'2011_TO_2016':s16,'2016_TO_2021':s21,'eligible_features':eligible,'failed_features_forced_zero':[f for f in FEATURES if f not in eligible],'coverage_gate':coverage,'status':'PASS_MULTIPART_HEAD_POWER' if coverage and eligible else 'FAIL_MULTIPART_HEAD_POWER','forecast_modified':False,'outcomes_used':False};OUT.write_text(json.dumps(out,ensure_ascii=False,indent=2,sort_keys=True)+'\n',encoding='utf-8');print(json.dumps({'status':out['status'],'rows16':len(r16),'rows21':len(r21),'fully_known16':s16['fully_known_all_features'],'fully_known21':s21['fully_known_all_features'],'eligible_features':eligible,'positive16':{f:s16['features'][f]['positive'] for f in FEATURES},'positive21':{f:s21['features'][f]['positive'] for f in FEATURES},'unknown16':len(s16['unknown_rows']),'unknown21':len(s21['unknown_rows'])},sort_keys=True))
if __name__=='__main__':main()
