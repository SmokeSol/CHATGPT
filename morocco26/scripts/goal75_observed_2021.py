#!/usr/bin/env python3
import json,re,unicodedata
from collections import Counter,defaultdict
from pathlib import Path
import pandas as pd
from datasets import load_dataset
R=Path(__file__).resolve().parents[1];O=R/'data'/'goal75';O.mkdir(exist_ok=True)
DATASET='electricsheepafrica/africa-membres-de-la-chambre-des-representants-du-maroc-2007-2011-2016-2021'
OFFICIAL_TOTAL={'RNI':102,'PAM':87,'PI':81,'USFP':34,'MP':28,'PPS':22,'UC':18,'PJD':13,'MDS':5,'FFD':3,'CNI':1,'PSU':1}

def norm(x):return re.sub('[^a-z0-9]+',' ',unicodedata.normalize('NFKD',str(x)).encode('ascii','ignore').decode().lower()).strip()
def canonical_party(x):
    x=str(x).strip().upper()
    aliases={'I':'PI','ISTIQLAL':'PI','RNI':'RNI','PAM':'PAM','USFP':'USFP','MP':'MP','PPS':'PPS','UC':'UC','PJD':'PJD','MDS':'MDS','FFD':'FFD','CNI':'CNI','PSU':'PSU'}
    return aliases.get(x,x)
def regional_key(circ,region):
    n=norm(circ)
    if 'circonscription regionale' in n or n.startswith('regionale '):return norm(region)
    return None

def main():
    ds=load_dataset(DATASET)
    frames=[ds[k].to_pandas() for k in ds.keys()];df=pd.concat(frames,ignore_index=True)
    q=df[df['parlement'].astype(str).eq('2021-2026')].copy()
    q=q[q['motifentree'].astype(str).str.lower().eq('elu')].copy()
    q['parti_canon']=q['parti'].map(canonical_party)
    # Some packaged datasets can duplicate a person across split/materialization; idsiege is the parliamentary seat identity.
    q=q.sort_values(['idsiege','dateentree']).drop_duplicates(subset=['idsiege'],keep='first')
    total=Counter(q['parti_canon'])
    regional=defaultdict(Counter);local=defaultdict(Counter);rows=[]
    for _,r in q.iterrows():
        circ=str(r['circonscription']);reg=str(r.get('region',''))
        rk=regional_key(circ,reg)
        rec={'idsiege':int(r['idsiege']),'idperson':int(r['idperson']),'name':str(r['prenomnom']),'party':r['parti_canon'],'circonscription':circ,'region':reg,'dateentree':str(r['dateentree']),'motifentree':str(r['motifentree'])}
        rows.append(rec)
        if rk:regional[rk][r['parti_canon']]+=1
        else:local[norm(circ)][r['parti_canon']]+=1
    total_clean={k:int(v) for k,v in sorted(total.items()) if k in OFFICIAL_TOTAL}
    out={
      'source_dataset':DATASET,
      'source_method':'TAFRA member data, 2021-2026, motifentree=Elu, first record per idsiege',
      'original_elected_rows':len(q),
      'official_party_total_observed':total_clean,
      'official_party_total_expected':OFFICIAL_TOTAL,
      'official_total_exact_match':total_clean==OFFICIAL_TOTAL,
      'regional_seats_observed':sum(sum(v.values()) for v in regional.values()),
      'regional':{k:dict(sorted(v.items())) for k,v in sorted(regional.items())},
      'local_seats_observed':sum(sum(v.values()) for v in local.values()),
      'local':{k:dict(sorted(v.items())) for k,v in sorted(local.items())},
      'rows':rows
    }
    # This gate is strict: source extraction must itself reproduce the official 395-seat party totals.
    if len(q)!=395 or not out['official_total_exact_match'] or out['regional_seats_observed']!=90 or out['local_seats_observed']!=305:
        print(json.dumps({k:out[k] for k in ['original_elected_rows','official_party_total_observed','official_party_total_expected','official_total_exact_match','regional_seats_observed','local_seats_observed']},ensure_ascii=False,indent=2))
        raise SystemExit(5)
    (O/'observed_elected_2021.json').write_text(json.dumps(out,ensure_ascii=False,indent=2))
    print(json.dumps({k:out[k] for k in ['original_elected_rows','official_party_total_observed','official_total_exact_match','regional_seats_observed','local_seats_observed']},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
