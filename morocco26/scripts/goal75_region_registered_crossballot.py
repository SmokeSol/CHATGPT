#!/usr/bin/env python3
import json,re,unicodedata
from pathlib import Path
import requests
from bs4 import BeautifulSoup
R=Path(__file__).resolve().parents[1];O=R/'data'/'goal75';O.mkdir(exist_ok=True)
URL='https://fr.wikipedia.org/wiki/%C3%89lections_r%C3%A9gionales_marocaines_de_2021'
HCP_ROUNDED=17509000
REGIONS=['Tanger-Tétouan-Al Hoceïma','Oriental','Fès-Meknès','Rabat-Salé-Kénitra','Béni Mellal-Khénifra','Casablanca-Settat','Marrakech-Safi','Drâa-Tafilalet','Souss-Massa','Guelmim-Oued Noun','Laâyoune-Sakia El Hamra','Dakhla-Oued Ed-Dahab']
def norm(x):return re.sub('[^a-z0-9]+',' ',unicodedata.normalize('NFKD',str(x)).encode('ascii','ignore').decode().lower()).strip()
def nint(s):
 x=re.sub('[^0-9]','',str(s));return int(x) if x else None
def main():
 r=requests.get(URL,timeout=45,headers={'User-Agent':'MOROCCO26 research'});r.raise_for_status();soup=BeautifulSoup(r.text,'html.parser');targets={norm(x):x for x in REGIONS};found={};details=[]
 for tbl in soup.find_all('table'):
  heading=tbl.find_previous(['h2','h3','h4'])
  h=heading.get_text(' ',strip=True) if heading else ''
  hk=norm(h)
  match=None
  for k,name in targets.items():
   if k in hk or hk in k:
    match=name;break
  if not match:continue
  rows=[]
  for tr in tbl.find_all('tr'):
   cells=[c.get_text(' ',strip=True) for c in tr.find_all(['th','td'])]
   if cells:rows.append(cells)
  reg=None;particip=None
  for cells in rows:
   txt=' '.join(cells).lower()
   if 'inscrits' in txt and 'particip' in txt:
    nums=[nint(c) for c in cells[1:] if nint(c) is not None]
    if nums:reg=max(nums)
   if 'abstentions' in txt:pass
  if reg and match not in found:
   found[match]=reg;details.append({'region':match,'registered':reg,'heading':h})
 total=sum(found.values());missing=[x for x in REGIONS if x not in found]
 out={'source_url':URL,'same_day_roll_logic':'The 8 September 2021 municipal, regional-council and House elections used the same general electoral lists. Region-level registered-voter counts from the regional-council ballot therefore provide an external denominator for the House regional constituency covering the same region.','regions_found':len(found),'missing':missing,'registered_by_region':found,'sum_registered':total,'hcp_31_july_rounded':HCP_ROUNDED,'delta_vs_hcp_rounded':total-HCP_ROUNDED,'relative_delta':abs(total-HCP_ROUNDED)/HCP_ROUNDED,'crossballot_gate_pass':len(found)==12 and abs(total-HCP_ROUNDED)<=5000,'details':details}
 (O/'regional_registered_crossballot.json').write_text(json.dumps(out,ensure_ascii=False,indent=2));print(json.dumps(out,ensure_ascii=False,indent=2));raise SystemExit(0 if out['crossballot_gate_pass'] else 4)
if __name__=='__main__':main()
