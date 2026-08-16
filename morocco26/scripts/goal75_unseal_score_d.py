#!/usr/bin/env python3
from io import StringIO
from urllib.parse import quote
import pandas as pd
import goal75_unseal_score as u
u.REG_EXPECTED={'RNI':16,'PAM':12,'PI':13,'USFP':11,'MP':8,'PPS':10,'UC':5,'PJD':9,'MDS':2,'FFD':2,'CNI':1,'PSU':1}
REG={x[0] for x in u.REGIONS};orig=u.g.acquire
SLUG={'Dakhla-Oued Eddahab':'Circonscription_de_Dakhla-Oued_Ed-Dahab','Oriental':"Circonscription_d%27Oriental"}
def acquire(name,seats,need21):
    if name not in REG:return orig(name,seats,need21)
    slug=SLUG.get(name,'Circonscription_de_'+quote(name.replace(' ','_'),safe="_()'-"));url='https://fr.wikipedia.org/wiki/'+slug
    html=u.g.get(url).text;tabs=[]
    for df in pd.read_html(StringIO(html)):
        cols=' '.join(map(str,df.columns))
        if 'Parti' in cols and 'Voix' in cols:tabs.append(df)
    if not tabs:raise RuntimeError(f'no regional election table: {name}')
    return {'title':name,'url':url,'2016':None,'2021':u.parse(tabs[-1])}
u.g.acquire=acquire
u.main()
