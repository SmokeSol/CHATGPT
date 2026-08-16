#!/usr/bin/env python3
from io import StringIO
from urllib.parse import quote
import pandas as pd
import goal75_unseal_score as u
REG={x[0] for x in u.REGIONS}
orig=u.g.acquire

def acquire(name,seats,need21):
    if name not in REG:
        return orig(name,seats,need21)
    url='https://fr.wikipedia.org/wiki/Circonscription_de_'+quote(name.replace(' ','_'),safe="_()'-")
    html=u.g.get(url).text;tabs=[]
    for df in pd.read_html(StringIO(html)):
        cols=' '.join(map(str,df.columns))
        if 'Parti' in cols and 'Voix' in cols:tabs.append(df)
    if not tabs:raise RuntimeError(f'no regional election table: {name}')
    return {'title':name,'url':url,'2016':None,'2021':u.parse(tabs[-1])}

u.g.acquire=acquire
u.main()
