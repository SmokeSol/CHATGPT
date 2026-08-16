#!/usr/bin/env python3
import json,re,unicodedata
from io import BytesIO
from pathlib import Path
import pandas as pd, requests
R=Path(__file__).resolve().parents[1];O=R/'data'/'goal75';O.mkdir(exist_ok=True)
URL='https://open.africa/dataset/595d69a4-c7fc-4e9d-beeb-5d7fc9ec78e5/resource/cf341829-cd2c-4baa-b679-2b2ee1c1e333/download/parlement-elections-2021-1-0.xlsx'
def norm(x):return re.sub('[^a-z0-9]+',' ',unicodedata.normalize('NFKD',str(x)).encode('ascii','ignore').decode().lower()).strip()
def main():
 r=requests.get(URL,timeout=60,headers={'User-Agent':'MOROCCO26 research'});r.raise_for_status();book=pd.ExcelFile(BytesIO(r.content));summary={'source_url':URL,'bytes':len(r.content),'sheets':book.sheet_names,'sheet_profiles':[],'marrakech_matches':[]}
 for s in book.sheet_names:
  df=pd.read_excel(book,sheet_name=s);profile={'sheet':s,'rows':len(df),'columns':[str(c) for c in df.columns]};summary['sheet_profiles'].append(profile)
  for i,row in df.iterrows():
   txt=' | '.join(str(v) for v in row.tolist())
   n=norm(txt)
   if ('marrakech' in n and 'safi' in n) or 'rmili' in n or 'lemssaki' in n or 'الرميلي' in txt or 'المسكي' in txt:
    summary['marrakech_matches'].append({'sheet':s,'row_index':int(i),'row':{str(c):None if pd.isna(row[c]) else str(row[c]) for c in df.columns}})
 (O/'tafra_legislative_workbook_audit.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2));print(json.dumps(summary,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
