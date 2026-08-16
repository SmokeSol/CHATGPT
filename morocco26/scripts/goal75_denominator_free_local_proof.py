#!/usr/bin/env python3
import json,re,unicodedata
from io import BytesIO
from pathlib import Path
import pandas as pd,requests
R=Path(__file__).resolve().parents[1];O=R/'data'/'goal75';O.mkdir(exist_ok=True)
URL='https://open.africa/dataset/595d69a4-c7fc-4e9d-beeb-5d7fc9ec78e5/resource/cf341829-cd2c-4baa-b679-2b2ee1c1e333/download/parlement-elections-2021-1-0.xlsx'
META={'idRegion','idWilaya','idPrefProv','idSousPref','idCirconscription','region','wilaya','prefProv','sousPref','circonscription','typeListe','nSieges','nInscrits','txParticipation','invalide','repPctFemmes','repAge34','repAge3544','repAge4554','repAge55','repEduSans','repEdu1aire','repEdu2aire','repEduSup'}
def main():
 r=requests.get(URL,timeout=60,headers={'User-Agent':'MOROCCO26 research'});r.raise_for_status();df=pd.read_excel(BytesIO(r.content),sheet_name='donnees');party=[c for c in df.columns if c not in META];loc=df[df['typeListe'].astype(str).str.lower().eq('locale')].copy();rows=[];need=[]
 for i,row in loc.iterrows():
  votes={str(c):int(row[c]) for c in party if pd.notna(row[c]) and float(row[c])>0};s=int(row['nSieges']);valid=sum(votes.values());top=max(votes.values());threshold=valid/s;proof=top<threshold
  rec={'row_index':int(i),'idCirconscription':str(row['idCirconscription']),'region':str(row['region']),'prefProv':str(row['prefProv']),'circonscription':str(row['circonscription']),'seats':s,'valid_party_vote_sum':valid,'max_party_votes':top,'valid_votes_over_seats':threshold,'max_share_valid':top/valid,'no_direct_quota_proven_without_registered':proof,'top_winners':sorted(votes,key=lambda k:(-votes[k],k))[:s],'votes':votes}
  rows.append(rec)
  if not proof:need.append(rec)
 out={'source_url':URL,'logic':'registered >= valid party-vote sum; therefore q=registered/seats >= valid/seats. If max party votes < valid/seats, no list can reach q for any legally possible registered count. All seats then go by largest remainders, equal to raw votes, so top-N lists are the legal winners.','local_rows':len(rows),'proven_without_denominator':sum(x['no_direct_quota_proven_without_registered'] for x in rows),'needs_exact_registered':len(need),'all_92_proven':len(rows)==92 and not need,'needs_exact_registered_rows':need,'rows':rows}
 (O/'local_denominator_free_proof.json').write_text(json.dumps(out,ensure_ascii=False,indent=2));print(json.dumps({k:out[k] for k in ['local_rows','proven_without_denominator','needs_exact_registered','all_92_proven','needs_exact_registered_rows']},ensure_ascii=False,indent=2));raise SystemExit(0 if out['all_92_proven'] else 2)
if __name__=='__main__':main()
