#!/usr/bin/env python3
from __future__ import annotations
import argparse,json
from pathlib import Path
from agent_society_v2_rich_score_common import *
from agent_society_v2_rich_score_model import *
PASS='ASV2_RICH_HISTORICAL_SANITY_PASS_READY_FOR_2026_FREEZE';FAIL='ASV2_RICH_KILL_BEFORE_2026'
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--opuszip',required=True);ap.add_argument('--privatejson',required=True);ap.add_argument('--contract',required=True);ap.add_argument('--outdir',required=True);ap.add_argument('--publiczip');ap.add_argument('--workmanifest');ap.add_argument('--outcome2016');ap.add_argument('--outcome2021');ap.add_argument('--recon2016');ap.add_argument('--map2021');ap.add_argument('--pop2021');ap.add_argument('--contract-only',action='store_true');a=ap.parse_args();out=Path(a.outdir);out.mkdir(parents=True,exist_ok=True)
 if sha_file(a.privatejson)!=REQUIRED_PRIVATE_MANIFEST_SHA:raise RuntimeError('private manifest SHA mismatch')
 if sha_file(a.contract)!=REQUIRED_CONTRACT_SHA:raise RuntimeError('contract SHA mismatch')
 priv=readj(a.privatejson);_,_,expected,_=load_contract(a.publiczip,a.workmanifest,priv);validity,valid=validate_outputs(a.opuszip,expected);res={'schema_version':'1.0','result_id':'M26-ASV2-RICH-HISTORICAL-SCORE-V1','experiment_id':'M26-AGENT-SOCIETY-V2-001','contract_validity':validity,'historical_role':'RETROSPECTIVE_SANITY_FILTER_ONLY_NOT_PRISTINE_PROOF','severe_2016_warning':'2016 context remains weakly cross-party discriminative.'}
 if not validity['full_contract_pass']:
  res['gates']={'contract':False};res['terminal_state']=FAIL;writej(out/'rich_historical_score_v1.json',res);print(json.dumps(res,indent=2));return
 pred=aggregate(valid,priv);res['aggregation_pass']=True
 if a.contract_only:
  res['terminal_state']='PASS_RICH_SCORER_CONTRACT_AND_AGGREGATION_DRYRUN';writej(out/'rich_historical_score_v1.json',res);print(json.dumps(res,indent=2));return
 for x in ['outcome2016','outcome2021','recon2016','map2021','pop2021']:
  if not getattr(a,x):raise RuntimeError('missing '+x)
 obs=outcome_maps(readj(a.outcome2016),readj(a.outcome2021),readj(a.recon2016),readj(a.map2021),readj(a.pop2021),priv);metrics={'ALL_92':{},'DIRECT_58':{}};boots={}
 for panel,direct in [('ALL_92',False),('DIRECT_58',True)]:
  for y in [2016,2021]:
   ks=keys_for(priv,y,direct);assert len(ks)==(58 if direct else 92);detail={};metrics[panel][str(y)]={}
   for arm in ['C0','R3_TRUE','R3_SHUFFLED']:
    m=metric(pred[arm],obs,ks);detail[arm]=m;metrics[panel][str(y)][arm]={k:v for k,v in m.items() if k!='territory_mse'}
   for tr,co in [('R3_TRUE','C0'),('R3_TRUE','R3_SHUFFLED')]:boots[f'{panel}:{y}:{tr}_VS_{co}']=bootstrap(detail[tr]['territory_mse'],detail[co]['territory_mse'])
 imp={p:{str(y):(metrics[p][str(y)]['C0']['macro_party_share_RMSE']-metrics[p][str(y)]['R3_TRUE']['macro_party_share_RMSE'])/metrics[p][str(y)]['C0']['macro_party_share_RMSE'] for y in [2016,2021]} for p in metrics};g={'contract':True}
 for y in ['2016','2021']:
  g[f'all92_not_worse_{y}']=metrics['ALL_92'][y]['R3_TRUE']['macro_party_share_RMSE']<=1.01*metrics['ALL_92'][y]['C0']['macro_party_share_RMSE'];g[f'all92_negative_control_{y}']=metrics['ALL_92'][y]['R3_TRUE']['macro_party_share_RMSE']<=metrics['ALL_92'][y]['R3_SHUFFLED']['macro_party_share_RMSE'];g[f'direct_not_worse_{y}']=metrics['DIRECT_58'][y]['R3_TRUE']['macro_party_share_RMSE']<=1.01*metrics['DIRECT_58'][y]['C0']['macro_party_share_RMSE'];g[f'direct_negative_control_{y}']=metrics['DIRECT_58'][y]['R3_TRUE']['macro_party_share_RMSE']<=metrics['DIRECT_58'][y]['R3_SHUFFLED']['macro_party_share_RMSE']
 g['all92_positive_signal']=max(imp['ALL_92'].values())>=.01;py=[y for y in ['2016','2021'] if imp['ALL_92'][y]>=.01];g['positive_signal_not_proxy_confined']=any(imp['DIRECT_58'][y]>=0 for y in py);res.update({'metrics':metrics,'relative_improvement_TRUE_vs_C0':imp,'paired_bootstrap':boots,'gates':g,'all_gates_pass':all(g.values()),'terminal_state':PASS if all(g.values()) else FAIL});writej(out/'rich_historical_score_v1.json',res);print(json.dumps(res,indent=2))
if __name__=='__main__':main()
