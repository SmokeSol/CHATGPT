#!/usr/bin/env python3
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path

def sha(p):
 h=hashlib.sha256()
 with open(p,'rb') as f:
  for b in iter(lambda:f.read(1<<20),b''):h.update(b)
 return h.hexdigest()
def writej(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,sort_keys=True,indent=2)+'\n',encoding='utf-8')
def order(xs,*salt):return sorted(xs,key=lambda x:hashlib.sha256(('|'.join(map(str,salt))+'|'+str(x)).encode()).hexdigest())
def tmap(pop,eid,oldpriv):
 sig={tuple(round(float(w[f'A{i:03d}']),15) for i in range(1,129)):tid for tid,w in oldpriv['weights_by_election_territory_archetype'][eid].items()};out={}
 for t in pop['territories']:
  v=tuple(round(float(a['weight']),15) for a in sorted(t['archetypes'],key=lambda a:a['archetype_id']))
  if v not in sig:raise RuntimeError('unmatched territory '+t['constituency_id'])
  out[t['constituency_id']]=sig[v]
 if len(out)!=92 or len(set(out.values()))!=92:raise RuntimeError('territory map not bijective')
 return out
def local_maps(eid,tid,globals_):
 o=order(globals_,'LOCALPARTY',eid,tid);g2l={g:f'Q_{i+1:02d}' for i,g in enumerate(o)};return g2l,{v:k for k,v in g2l.items()}
def main():
 ap=argparse.ArgumentParser()
 for x in ['min16','min21','rich16','rich21','oldpublicdir','oldprivatejson','outdir']:ap.add_argument('--'+x,required=True)
 a=ap.parse_args();out=Path(a.outdir);out.mkdir(parents=True,exist_ok=True)
 oldpriv=json.load(open(a.oldprivatejson));m16=tmap(json.load(open(a.min16)),'E_563101AA29400273',oldpriv);m21=tmap(json.load(open(a.min21)),'E_0BB34DC2900A7390',oldpriv)
 private={'schema_version':'1.0','private_manifest_id':'M26-ASV2-RICH-HISTORICAL-PRIVATE-ORCHESTRATOR-V1','experiment_id':'M26-AGENT-SOCIETY-V2-001','year_by_anonymous_election_id':{'E_563101AA29400273':2016,'E_0BB34DC2900A7390':2021},'condition_role_by_id':oldpriv['condition_role_by_id'],'weights_by_election_territory_archetype':{},'local_party_to_global_by_election_territory':{},'global_party_to_local_by_election_territory':{},'geography_confidence_by_election_territory':{},'real_constituency_slug_by_election_territory':{},'baseline_vote_share_global_by_election_territory':oldpriv['baseline_vote_share_by_election_territory'],'seat_magnitude_by_election_territory':oldpriv['seat_magnitude_by_election_territory'],'source_minimal_private_manifest_sha256':sha(a.oldprivatejson)}
 work=[]
 for year,popfile,mp,eid in [(2021,a.rich21,m21,'E_0BB34DC2900A7390'),(2016,a.rich16,m16,'E_563101AA29400273')]:
  pop=json.load(open(popfile));private['weights_by_election_territory_archetype'][eid]={};private['local_party_to_global_by_election_territory'][eid]={};private['global_party_to_local_by_election_territory'][eid]={};private['geography_confidence_by_election_territory'][eid]={};private['real_constituency_slug_by_election_territory'][eid]={}
  for t in pop['territories']:
   cid=t['constituency_id'];tid=mp[cid];p=Path(a.oldpublicdir)/'packets'/eid/'C_4F91A2D7'/tid/'B01.json';globals_=json.load(open(p))['available_party_ids'];g2l,l2g=local_maps(eid,tid,globals_);private['global_party_to_local_by_election_territory'][eid][tid]=g2l;private['local_party_to_global_by_election_territory'][eid][tid]=l2g;private['geography_confidence_by_election_territory'][eid][tid]=t['geography_confidence'];private['real_constituency_slug_by_election_territory'][eid][tid]=cid;private['weights_by_election_territory_archetype'][eid][tid]={f'A{i:03d}':float(x['weight']) for i,x in enumerate(sorted(t['archetypes'],key=lambda x:x['archetype_id']),1)}
  del pop
  for tid in sorted(private['weights_by_election_territory_archetype'][eid]):
   for cond in ['C_4F91A2D7','C_B73C08E1']:
    for bi in range(1,9):work.append({'anonymous_election_id':eid,'anonymous_territory_id':tid,'condition_id':cond,'batch_id':f'B{bi:02d}','voter_batch_path':f'voter_batches/{eid}/{tid}/B{bi:02d}.json','context_path':f'contexts/{eid}/{cond}/{tid}.json','output_path':f'outputs/{eid}/{cond}/{tid}/B{bi:02d}.jsonl'})
 w={'schema_version':'1.0','manifest_id':'M26-ASV2-RICH-WORK-MANIFEST-V1','experiment_id':'M26-AGENT-SOCIETY-V2-001','work_items':work,'counts':{'work_items':2944,'voter_batch_files':1472,'context_files':368,'rows':94208}}
 writej(out/'work_manifest.json',w);writej(out/'private_orchestrator_manifest.json',private)
 print(json.dumps({'work_sha':sha(out/'work_manifest.json'),'private_sha':sha(out/'private_orchestrator_manifest.json'),'work_items':len(work)},indent=2))
if __name__=='__main__':main()
