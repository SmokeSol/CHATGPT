#!/usr/bin/env python3
import json
from io import BytesIO
from pathlib import Path
import pandas as pd, requests
R=Path(__file__).resolve().parents[1];O=R/'data'/'goal75';O.mkdir(exist_ok=True)
URL='https://open.africa/dataset/595d69a4-c7fc-4e9d-beeb-5d7fc9ec78e5/resource/cf341829-cd2c-4baa-b679-2b2ee1c1e333/download/parlement-elections-2021-1-0.xlsx'
def main():
 r=requests.get(URL,timeout=60,headers={'User-Agent':'MOROCCO26 research'});r.raise_for_status();b=BytesIO(r.content);d=pd.read_excel(b,sheet_name='dictionnaire');notes=pd.read_excel(BytesIO(r.content),sheet_name='notes')
 wanted=d[d['Label'].astype(str).isin(['nInscrits','txParticipation','invalide','typeListe','nSieges'])]
 out={'source_url':URL,'definitions':wanted.fillna('').to_dict(orient='records'),'notes':notes.fillna('').to_dict(orient='records')}
 (O/'tafra_dictionary_probe.json').write_text(json.dumps(out,ensure_ascii=False,indent=2));print(json.dumps(out,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
