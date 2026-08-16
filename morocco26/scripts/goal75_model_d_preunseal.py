#!/usr/bin/env python3
import gc,hashlib,json,math,random,re,statistics
from pathlib import Path
import numpy as np
import torch
from huggingface_hub import model_info
from transformers import AutoModelForCausalLM,AutoTokenizer
R=Path(__file__).resolve().parents[1];D=R/'data';O=D/'goal75';O.mkdir(exist_ok=True)
K=['RNI','PAM','PI','PJD','USFP','MP','UC','PPS','OTHER'];ALIASES=list('ABCDEFGHI')
def load(p):return json.loads(Path(p).read_text())
def normshares(v):
 z=sum(v.values()) or 1;d={k:v.get(k,0)/z for k in K};d['OTHER']=max(d['OTHER'],0);z=sum(d.values());return {k:d[k]/z for k in K}
def turnout(x):return (x.get('expressed') or 0)/(x.get('registered') or 1)
def perm_for(seed):
 a=ALIASES[:];random.Random(seed).shuffle(a);return dict(zip(K,a))
def enc(d,m):return {m[k]:round(d[k],6) for k in K}
def anon_case(x,pred,seed,idx):
 m=perm_for(seed);base=normshares(x['2016']['votes'])
 return {'district':f'D{idx:02d}','seats':x['seats'],'baseline_2016':enc(base,m),'turnout_2016':round(turnout(x['2016']),6),'B_anchor':enc(pred['B']['shares'],m),'B_turnout':round(pred['B']['turnout'],6),'C_anchor':enc(pred['C_eval']['shares'],m),'C_turnout':round(pred['C_eval']['turnout'],6)},m
def dev_examples(dev,seed):
 good=[x for x in dev if x.get('2016',{}).get('vote_coverage',0)>=.9 and x.get('2021',{}).get('vote_coverage',0)>=.9 and x['2016'].get('registered') and x['2021'].get('registered')]
 good=sorted(good,key=lambda x:x['constituency_id']);step=max(1,len(good)//12);sel=good[::step][:12];out=[]
 for i,x in enumerate(sel):
  m=perm_for(seed+1000+i);out.append({'example':f'E{i+1:02d}','seats':x['seats'],'x2016':enc(normshares(x['2016']['votes']),m),'turnout2016':round(turnout(x['2016']),6),'y2021':enc(normshares(x['2021']['votes']),m),'turnout2021':round(turnout(x['2021']),6)})
 return out
def prompt(variant,examples,cases):
 heads=[
 'Infer the next aggregate election distribution for each opaque district using only the numeric transition examples and the two frozen anchors.',
 'Act as a bounded aggregate cognition delegate. From the anonymized numeric examples, update each district from its 2016 state to a 2021 distribution.',
 'Solve this as an out-of-sample distribution-update task. Use only supplied numbers; return calibrated aggregate predictions for every opaque district.'
 ]
 return f'''{heads[variant]}\nThe district ids, party letters and group identities are deliberately anonymized. You must not infer or mention real places, parties, voters, campaigns or political advice. B_anchor and C_anchor are frozen non-LLM baselines; you may use them as anchors but should only deviate when the training examples support it.\n\nTRAINING EXAMPLES:\n{json.dumps(examples,separators=(',',':'))}\n\nHOLDOUT INPUTS (2016 only; 2021 outcomes are not present):\n{json.dumps(cases,separators=(',',':'))}\n\nReturn ONLY valid JSON in this schema, exactly one record for every district:\n{{"predictions":[{{"district":"D01","shares":{{"A":0.1,"B":0.1,"C":0.1,"D":0.1,"E":0.1,"F":0.1,"G":0.1,"H":0.1,"I":0.2}},"turnout":0.5}}]}}\nConstraints: every share and turnout is within [0,1]; shares sum to 1 within 0.01; no prose, no markdown.'''
def parse_output(text,expected):
 try:
  a=text.find('{');b=text.rfind('}');obj=json.loads(text[a:b+1]);rows=obj['predictions']
 except Exception:return {},False
 out={}
 for r in rows:
  try:
   did=str(r['district']);s={k:float(r['shares'][k]) for k in ALIASES};t=float(r['turnout']);z=sum(s.values())
   if did not in expected or not all(0<=v<=1 for v in s.values()) or not 0<=t<=1 or not .99<=z<=1.01:continue
   out[did]={'shares':{k:v/z for k,v in s.items()},'turnout':t}
  except Exception:continue
 return out,len(out)==len(expected)
def corr(a,b):
 if len(a)<2:return 0
 x=np.array(a);y=np.array(b)
 if x.std()==0 or y.std()==0:return 0
 return float(np.corrcoef(x,y)[0,1])
def main():
 rep=load(O/'stage1_report.json');acq=load(O/'stage1_acquisition.json');fr=load(O/'bc_freeze.json');man=load(D/'model_d_goal75_manifest.json')
 assert rep['ready_to_unseal'] and not acq['holdout_2021_outcomes_accessed'];assert fr['freeze_hash']==man['parent_freeze_hash'];assert all('2021' not in x for x in acq['holdout_inputs_2016'])
 seed=int(fr['freeze_hash'][:12],16);predmap={x['constituency_id']:x for x in fr['predictions']};cases=[];maps={}
 for i,x in enumerate(acq['holdout_inputs_2016'],1):
  c,m=anon_case(x,predmap[x['constituency_id']],seed+i,i);cases.append(c);maps[c['district']]={'constituency_id':x['constituency_id'],'real_to_alias':m,'alias_to_real':{v:k for k,v in m.items()}}
 examples=dev_examples(acq['development'],seed);expected={c['district'] for c in cases};runs=[];resolved={}
 for repo in man['models']:
  info=model_info(repo);rev=info.sha;resolved[repo]=rev
  tok=AutoTokenizer.from_pretrained(repo,revision=rev);model=AutoModelForCausalLM.from_pretrained(repo,revision=rev,torch_dtype=torch.float32,low_cpu_mem_usage=True);model.eval()
  for vi in range(3):
   p=prompt(vi,examples,cases);ph=hashlib.sha256(p.encode()).hexdigest();msgs=[{'role':'user','content':p}]
   if hasattr(tok,'apply_chat_template'):txt=tok.apply_chat_template(msgs,tokenize=False,add_generation_prompt=True)
   else:txt=p
   inp=tok(txt,return_tensors='pt',truncation=True,max_length=10000)
   with torch.no_grad():out=model.generate(**inp,max_new_tokens=1800,do_sample=False,pad_token_id=tok.eos_token_id)
   raw=tok.decode(out[0][inp['input_ids'].shape[1]:],skip_special_tokens=True);parsed,complete=parse_output(raw,expected);runs.append({'model':repo,'revision':rev,'variant':vi+1,'prompt_hash':ph,'raw':raw,'parsed':parsed,'complete':complete,'records_valid':len(parsed)})
  del model,tok;gc.collect()
 # pre-unseal stability only
 total=len(runs)*len(expected);valid=sum(r['records_valid'] for r in runs);party_sds=[];turn_sds=[]
 for repo in man['models']:
  rr=[r for r in runs if r['model']==repo]
  for did in expected:
   vals=[r['parsed'][did] for r in rr if did in r['parsed']]
   if len(vals)>=2:
    for a in ALIASES:party_sds.append(statistics.pstdev(v['shares'][a] for v in vals))
    turn_sds.append(statistics.pstdev(v['turnout'] for v in vals))
 fam=[]
 for repo in man['models']:
  rr=[r for r in runs if r['model']==repo];vec=[]
  for did in sorted(expected):
   vals=[r['parsed'][did] for r in rr if did in r['parsed']]
   if vals:
    for a in ALIASES:vec.append(statistics.median(v['shares'][a] for v in vals))
  fam.append(vec)
 cm=corr(fam[0],fam[1]) if len(fam)==2 and len(fam[0])==len(fam[1]) else 0
 g=man['gates'];summary={'holdout_2021_outcomes_accessed':False,'bc_freeze_hash':fr['freeze_hash'],'models_resolved':resolved,'runs':len(runs),'delegate_records_expected':total,'delegate_records_valid':valid,'contract_validity_rate':valid/total,'mean_prompt_party_sd':statistics.mean(party_sds) if party_sds else 1,'mean_prompt_turnout_sd':statistics.mean(turn_sds) if turn_sds else 1,'cross_model_flattened_correlation':cm}
 summary['pre_unseal_gates_pass']=summary['contract_validity_rate']>=g['contract_validity_rate_min'] and summary['mean_prompt_party_sd']<=g['mean_prompt_party_sd_max'] and summary['mean_prompt_turnout_sd']<=g['mean_prompt_turnout_sd_max'] and cm>=g['cross_model_flattened_correlation_min']
 payload={'manifest':man,'anonymization_maps':maps,'development_examples':examples,'holdout_inputs':cases,'runs':runs,'summary':summary};(O/'model_d_preunseal.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2));(O/'model_d_preunseal_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2));print(json.dumps(summary,indent=2))
if __name__=='__main__':main()
