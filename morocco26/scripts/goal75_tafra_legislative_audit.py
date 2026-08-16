#!/usr/bin/env python3
import json,re,unicodedata
from collections import Counter
from io import BytesIO
from pathlib import Path
import pandas as pd, requests
R=Path(__file__).resolve().parents[1];O=R/'data'/'goal75';O.mkdir(exist_ok=True)
URL='https://open.africa/dataset/595d69a4-c7fc-4e9d-beeb-5d7fc9ec78e5/resource/cf341829-cd2c-4baa-b679-2b2ee1c1e333/download/parlement-elections-2021-1-0.xlsx'
META={'idRegion','idWilaya','idPrefProv','idSousPref','idCirconscription','region','wilaya','prefProv','sousPref','circonscription','typeListe','nSieges','nInscrits','txParticipation','invalide','repPctFemmes','repAge34','repAge3544','repAge4554','repAge55','repEduSans','repEdu1aire','repEdu2aire','repEduSup'}
EXPECTED_RNI_LEGISLATIVE_LOCAL=2099036

def norm(x):return re.sub('[^a-z0-9]+',' ',unicodedata.normalize('NFKD',str(x)).encode('ascii','ignore').decode().lower()).strip()
def main():
 r=requests.get(URL,timeout=60,headers={'User-Agent':'MOROCCO26 research'});r.raise_for_status();book=pd.ExcelFile(BytesIO(r.content));summary={'source_url':URL,'bytes':len(r.content),'sheets':book.sheet_names,'sheet_profiles':[],'marrakech_matches':[],'regional_rows':[],'provenance_note':'typeListe=regionale here means the 90 House regional-list seats; it must not be conflated with the separate 2021 elections of regional councils.'}
 for s in book.sheet_names:
  df=pd.read_excel(book,sheet_name=s);profile={'sheet':s,'rows':len(df),'columns':[str(c) for c in df.columns]};summary['sheet_profiles'].append(profile)
  if s=='donnees':
   party_cols=[c for c in df.columns if c not in META]
   reg=df[df['typeListe'].astype(str).str.lower().eq('regionale')].copy();loc=df[df['typeListe'].astype(str).str.lower().eq('locale')].copy()
   for i,row in reg.iterrows():
    votes={str(c):int(row[c]) for c in party_cols if pd.notna(row[c]) and float(row[c])!=0}
    summary['regional_rows'].append({'row_index':int(i),'idRegion':None if pd.isna(row['idRegion']) else str(row['idRegion']),'region':str(row['region']),'circonscription':str(row['circonscription']),'nSieges':int(row['nSieges']),'nInscrits':None if pd.isna(row['nInscrits']) else int(row['nInscrits']),'txParticipation':None if pd.isna(row['txParticipation']) else float(row['txParticipation']),'votes':votes,'vote_sum':sum(votes.values())})
   regional_totals=Counter();local_totals=Counter()
   for rr in summary['regional_rows']:regional_totals.update(rr['votes'])
   for _,row in loc.iterrows():
    for c in party_cols:
     if pd.notna(row[c]) and float(row[c])!=0:local_totals[str(c)]+=int(row[c])
   summary['regional_party_vote_totals']={k:int(v) for k,v in sorted(regional_totals.items())};summary['local_party_vote_totals']={k:int(v) for k,v in sorted(local_totals.items())}
   summary['regional_row_count']=len(summary['regional_rows']);summary['regional_seat_sum']=sum(x['nSieges'] for x in summary['regional_rows'])
   summary['RNI_legislative_local_ministry_expected']=EXPECTED_RNI_LEGISLATIVE_LOCAL;summary['RNI_legislative_local_tafra_sum']=int(local_totals['RNI']);summary['RNI_legislative_local_exact_match']=int(local_totals['RNI'])==EXPECTED_RNI_LEGISLATIVE_LOCAL
  for i,row in df.iterrows():
   txt=' | '.join(str(v) for v in row.tolist());n=norm(txt)
   if ('marrakech' in n and 'safi' in n) or 'rmili' in n or 'lemssaki' in n or 'الرميلي' in txt or 'المسكي' in txt:
    summary['marrakech_matches'].append({'sheet':s,'row_index':int(i),'row':{str(c):None if pd.isna(row[c]) else str(row[c]) for c in df.columns}})
 summary['regional_source_gate_pass']=summary.get('regional_row_count')==12 and summary.get('regional_seat_sum')==90 and summary.get('RNI_legislative_local_exact_match') is True
 (O/'tafra_legislative_workbook_audit.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2));print(json.dumps({'regional_row_count':summary.get('regional_row_count'),'regional_seat_sum':summary.get('regional_seat_sum'),'RNI_legislative_local_tafra_sum':summary.get('RNI_legislative_local_tafra_sum'),'RNI_legislative_local_ministry_expected':EXPECTED_RNI_LEGISLATIVE_LOCAL,'RNI_legislative_local_exact_match':summary.get('RNI_legislative_local_exact_match'),'gate':summary['regional_source_gate_pass'],'regional_rows':summary['regional_rows']},ensure_ascii=False,indent=2));raise SystemExit(0 if summary['regional_source_gate_pass'] else 8)
if __name__=='__main__':main()
