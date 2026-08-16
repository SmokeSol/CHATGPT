#!/usr/bin/env python3
import json,re
from pathlib import Path
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup
R=Path(__file__).resolve().parents[1];O=R/'data'/'goal75';O.mkdir(exist_ok=True)
URL='https://www.elections.ma/elections/legislatives/resultats.aspx?IE=1&Id=T1uzm+f7U%2FWFF+rn+x03Zg%3D%3D'
S=requests.Session();S.headers.update({'User-Agent':'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/125 Safari/537.36','Accept-Language':'fr-FR,fr;q=0.9,ar;q=0.8'})
def main():
 r=S.get(URL,timeout=40,allow_redirects=True);out={'url':URL,'status':r.status_code,'final_url':r.url,'headers':{k:v for k,v in r.headers.items() if k.lower() in ('content-type','server','x-powered-by')},'bytes':len(r.content)}
 text=r.text
 if r.status_code==200:
  soup=BeautifulSoup(text,'html.parser');out['title']=soup.title.get_text(' ',strip=True) if soup.title else None
  out['forms']=[{'action':f.get('action'),'method':f.get('method'),'id':f.get('id')} for f in soup.find_all('form')]
  out['hidden_inputs']=[{'name':x.get('name'),'id':x.get('id'),'value':(x.get('value') or '')[:250]} for x in soup.find_all('input',{'type':'hidden'})]
  scripts=[]
  for s in soup.find_all('script'):
   if s.get('src'):scripts.append({'src':urljoin(r.url,s['src'])})
   elif s.string and any(k in s.string.lower() for k in ('ajax','region','resultat','webmethod','circonscription','service')):scripts.append({'inline':s.string[:8000]})
  out['scripts']=scripts
  urls=sorted(set(re.findall(r'''(?i)(?:https?:)?//[^"'\s<>]+|[A-Za-z0-9_./-]+\.(?:asmx|ashx|aspx)(?:\?[^"'\s<>]*)?''',text)))
  out['candidate_urls']=urls[:300]
  out['keywords']={k:len(re.findall(k,text,re.I)) for k in ['Marrakech','Safi','region','circonscription','Get','WebMethod','ajax','resultat','participation','inscrit']}
  # Fetch same-origin JS to find service endpoints.
  js=[]
  for item in scripts:
   src=item.get('src')
   if not src or 'elections.ma' not in src:continue
   try:
    q=S.get(src,timeout=25);body=q.text
    if q.status_code==200 and any(k in body.lower() for k in ('ajax','asmx','resultat','circonscription','region','inscrit')):
     js.append({'src':src,'status':q.status_code,'bytes':len(body),'snippets':[m.group(0) for m in re.finditer(r'.{0,180}(?:ajax|asmx|resultat|circonscription|region|inscrit).{0,300}',body,re.I)][:30]})
   except Exception as e:js.append({'src':src,'error':repr(e)})
  out['interesting_js']=js
 (O/'elections_ma_probe.json').write_text(json.dumps(out,ensure_ascii=False,indent=2));print(json.dumps(out,ensure_ascii=False,indent=2));raise SystemExit(0 if r.status_code==200 else 4)
if __name__=='__main__':main()
