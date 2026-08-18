#!/usr/bin/env python3
from __future__ import annotations
import hashlib, json, re, zipfile, xml.etree.ElementTree as ET
from pathlib import Path
import requests

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'morocco26'/'data'/'goal100'/'e_collect'/'candidate_intelligence_v2'/'tafra_communal2015_xlsx_inspection_v1.json'
URL='https://open.africa/dataset/07a04224-c0ad-4861-9705-0518f5d49dbd/resource/7ae81ece-1b3d-4cdc-ac49-acd6ba37f6ea/download/communes-elus-2015-1-0.xlsx'
NS={'m':'http://schemas.openxmlformats.org/spreadsheetml/2006/main','r':'http://schemas.openxmlformats.org/officeDocument/2006/relationships','pr':'http://schemas.openxmlformats.org/package/2006/relationships'}

def col_index(cell_ref:str)->int:
    letters=re.match(r'[A-Z]+',cell_ref).group(0); n=0
    for c in letters:n=n*26+ord(c)-64
    return n-1

def main():
    r=requests.get(URL,timeout=60,allow_redirects=True,headers={'User-Agent':'M26-CandidateIntel/1.0'})
    r.raise_for_status(); data=r.content
    if not data.startswith(b'PK'):
        raise RuntimeError(f'not xlsx: status={r.status_code} bytes={len(data)} final={r.url}')
    sha=hashlib.sha256(data).hexdigest(); tmp=Path('/tmp/communes-elus-2015.xlsx'); tmp.write_bytes(data)
    with zipfile.ZipFile(tmp) as z:
        shared=[]
        if 'xl/sharedStrings.xml' in z.namelist():
            root=ET.fromstring(z.read('xl/sharedStrings.xml'))
            for si in root.findall('m:si',NS): shared.append(''.join(t.text or '' for t in si.findall('.//m:t',NS)))
        wb=ET.fromstring(z.read('xl/workbook.xml')); rels=ET.fromstring(z.read('xl/_rels/workbook.xml.rels'))
        relmap={x.attrib['Id']:x.attrib['Target'] for x in rels.findall('pr:Relationship',NS)}
        sheets=[]
        for s in wb.findall('m:sheets/m:sheet',NS):
            name=s.attrib['name']; rid=s.attrib['{'+NS['r']+'}id']; target=relmap[rid]
            path='xl/'+target.lstrip('/') if not target.startswith('xl/') else target
            root=ET.fromstring(z.read(path)); rows=[]
            for row in root.findall('m:sheetData/m:row',NS)[:25]:
                vals={}
                for c in row.findall('m:c',NS):
                    ref=c.attrib.get('r','A1'); idx=col_index(ref); typ=c.attrib.get('t'); v=c.find('m:v',NS); inline=c.find('m:is',NS)
                    value=''
                    if typ=='s' and v is not None: value=shared[int(v.text)]
                    elif typ=='inlineStr' and inline is not None: value=''.join(t.text or '' for t in inline.findall('.//m:t',NS))
                    elif v is not None: value=v.text
                    vals[idx]=value
                maxc=max(vals.keys(),default=-1); rows.append([vals.get(i,'') for i in range(maxc+1)])
            sheets.append({'name':name,'path':path,'preview_rows':rows})
    result={'schema_version':'1.0','source_url':URL,'final_url':r.url,'bytes':len(data),'sha256':sha,'sheets':sheets}
    OUT.parent.mkdir(parents=True,exist_ok=True); OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8'); print(json.dumps(result,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
