#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, re, unicodedata
from datetime import date
from pathlib import Path
from urllib.request import Request, urlopen

ROOT=Path(__file__).resolve().parents[1]
HROOT=ROOT/"data"/"goal100"/"historical"
ACCESS_DATE="2026-08-19"
VALID_STATUS={"VERIFIED","AMBIGUOUS","MISSING"}

ELECTION={
  2002:{
    "date":"2002-09-27","cutoff":"2002-09-27",
    "districts_expected":91,"local_seats":295,"national_seats":30,"national_list_kind":"NATIONAL_WOMEN_CONSENSUS",
    "national_list_rule_note":"30 sièges à l’échelle nationale; accord interpartis pré-électoral visant à réserver ces candidatures aux femmes.",
    "allocation":"PROPORTIONAL_LIST_LARGEST_REMAINDER","local_threshold_pct":3.0,
    "law_refs":[
      {"source_id":"BO_5018_LO_06_02","source_class":"T0","title":"Dahir n° 1-02-187 du 3 juillet 2002 portant promulgation de la loi organique n° 06-02","publication_date":"2002-07-04","url":"https://www.sgg.gov.ma/Legislation/rechercheSommairesBO.aspx","fact":"Article 78: listes sous 3% des suffrages exprimés dans la circonscription exclues de la répartition des sièges.","status":"VERIFIED"},
      {"source_id":"BO_5030_DEC_2_02_587","source_class":"T0","title":"Décret n° 2-02-587 du 7 août 2002 créant les circonscriptions électorales et fixant leurs sièges","publication_date":"2002-08-15","url":"https://www.sgg.gov.ma/Legislation/rechercheSommairesBO.aspx","fact":"Carte électorale 2002 fixée par décret avant scrutin.","status":"VERIFIED"},
      {"source_id":"LM_NATIONAL_20020923","source_class":"T2","title":"Liste nationale des femmes","publication_date":"2002-09-23","url":"https://lematin.ma/journal/2002/Liste-nationale-des-femmes-une-contribution-a-l-amelioration-de-la-position-du-Maroc/20999.html","fact":"Source pré-électorale décrivant la composition 295+30 et l'accord entre formations politiques pour réserver la liste nationale aux candidatures féminines.","status":"VERIFIED"},
    ],
    "map_url":"https://lematin.ma/journal/2002/Fiches-techniques-des-circonscriptions-electorales/20927/amp",
    "map_title":"Fiches techniques des circonscriptions électorales",
    "map_publication_date":"2002-09-21",
  },
  2007:{
    "date":"2007-09-07","cutoff":"2007-09-07",
    "districts_expected":95,"local_seats":295,"national_seats":30,"national_list_kind":"NATIONAL_WOMEN_RESERVED",
    "national_list_rule_note":"30 sièges réservés aux listes nationales des femmes, en parallèle des 295 sièges locaux dans 95 circonscriptions.",
    "allocation":"PROPORTIONAL_LIST_LARGEST_REMAINDER","local_threshold_pct":6.0,
    "law_refs":[
      {"source_id":"BO_5514_LO_22_06","source_class":"T0","title":"Dahir n° 1-07-60 du 23 mars 2007 portant promulgation de la loi organique n° 22-06","publication_date":"2007-04-05","url":"https://www.sgg.gov.ma/Legislation/rechercheSommairesBO.aspx","fact":"Article 78: seuil local de 6% pour participer à la répartition des sièges.","status":"VERIFIED"},
      {"source_id":"DEC_2_07_160","source_class":"T0","title":"Décret n° 2-07-160 modifiant le découpage électoral avant les législatives 2007","publication_date":None,"url":"https://www.sgg.gov.ma/Legislation/rechercheSommairesBO.aspx","fact":"Le décret n° 2-07-160 est cité comme texte de modification du découpage; l'original officiel complet et sa date de publication n'ont pas été récupérés dans cette passe, donc ce fait n'est pas promu VERIFIED.","status":"AMBIGUOUS"},
    ],
    "map_url":None,
    "map_title":None,
    "map_publication_date":None,
  }
}

CURATED = {
  2002:[
    ("LM_PI_20020909","T2","https://lematin.ma/journal/2002/Istiqlal--un-programme-des-candidats-et-des-petites-phrases/20559.html","2002-09-09",None,"PI","Abbas El Fassi","head_of_list","Abbas El Fassi est tête de liste PI à Larache.","VERIFIED"),
    ("LM_PI_20020909","T2","https://lematin.ma/journal/2002/Istiqlal--un-programme-des-candidats-et-des-petites-phrases/20559.html","2002-09-09",None,"PI",None,"incumbency","26 des 32 députés sortants PI sont candidats.","VERIFIED"),
    ("LM_WOMEN_20020903","T2","https://lematin.ma/journal/2002/Legislatives-2002-rude-concurrence-autour-des-tetes-des-listes-feminines/20406.html","2002-09-03","NATIONAL","USFP","Nouzha Chekrouni","head_of_list","Nouzha Chekrouni est confirmée tête de la liste nationale USFP.","VERIFIED"),
    ("LM_WOMEN_20020903","T2","https://lematin.ma/journal/2002/Legislatives-2002-rude-concurrence-autour-des-tetes-des-listes-feminines/20406.html","2002-09-03","NATIONAL","USFP","Fettoum Koudama","candidate_rank","Fettoum Koudama est annoncée deuxième sur la liste nationale USFP.","VERIFIED"),
    ("LM_WOMEN_20020903","T2","https://lematin.ma/journal/2002/Legislatives-2002-rude-concurrence-autour-des-tetes-des-listes-feminines/20406.html","2002-09-03","Al Fida-Derb Sultan","USFP","Badiâ Skkali","head_of_list","Badiâ Skkali est annoncée tête de liste locale USFP à Al Fida-Derb Sultan.","VERIFIED"),
    ("LM_WOMEN_20020903","T2","https://lematin.ma/journal/2002/Legislatives-2002-rude-concurrence-autour-des-tetes-des-listes-feminines/20406.html","2002-09-03","Al Fahss-Bni Makada","PJD","Fatima Bellahcen","head_of_list","Fatima Bellahcen est annoncée tête de liste PJD à Tanger/Fahss-Makada.","VERIFIED"),
    ("LM_HEADS_20020826","T2","https://lematin.ma/journal/2002/Elections--la-guerre-des-tetes-de-listes/20192.html","2002-08-26","Casablanca-Anfa","USFP","Khalid Alioua","head_of_list","Khalid Alioua est choisi tête de liste USFP à Anfa.","VERIFIED"),
    ("LM_HEADS_20020826","T2","https://lematin.ma/journal/2002/Elections--la-guerre-des-tetes-de-listes/20192.html","2002-08-26","Aïn Chock-Hay Hassani","USFP","Mohamed Karam","head_of_list","Mohamed Karam doit conduire la liste USFP à Aïn Chock.","AMBIGUOUS"),
    ("LM_HEADS_20020826","T2","https://lematin.ma/journal/2002/Elections--la-guerre-des-tetes-de-listes/20192.html","2002-08-26","Marrakech-Ménara","PI","M'hamed Khalifa","head_of_list","M'hamed Khalifa reçoit la circonscription Marrakech-Ménara selon l'article.","VERIFIED"),
    ("LM_HEADS_20020826","T2","https://lematin.ma/journal/2002/Elections--la-guerre-des-tetes-de-listes/20192.html","2002-08-26","Rabat-Yacoub El Mansour","MNP","Derraji","party_switch","Derraji quitte le RNI pour le MNP après l'investiture de Mohamed Aujjar.","VERIFIED"),
    ("LM_HEADS_20020826","T2","https://lematin.ma/journal/2002/Elections--la-guerre-des-tetes-de-listes/20192.html","2002-08-26","Taza","FFD","Abdesslam Seddiki","incumbent_head","Abdesslam Seddiki, député sortant, est tête de liste FFD à Taza.","VERIFIED"),
    ("ALM_ADL_2002","T2","https://aujourdhui.ma/focus/une-liste-mi-figue-mi-raisin-20722","2002-09-17","El Jadida","ADL","Abderrahmane El Kamel","party_switch","Député sortant; parcours MDS puis RNI, investi par ADL.","VERIFIED"),
    ("ALM_ADL_2002","T2","https://aujourdhui.ma/focus/une-liste-mi-figue-mi-raisin-20722","2002-09-17","Essaouira","ADL","Saïd Berdouz","local_office","Président du conseil préfectoral UC et président de la municipalité d'Al Hanchane, investi par ADL.","VERIFIED"),
  ],
  2007:[
    ("ALM_PJD_20070424","T2","https://aujourdhui.ma/societe/le-pjd-boucle-ses-candidatures-49072","2007-04-24",None,"PJD",None,"party_coverage","Le PJD a arrêté les têtes de liste d'environ 70 des 95 circonscriptions; le reste devait suivre.","VERIFIED"),
    ("ALM_PJD_20070424","T2","https://aujourdhui.ma/societe/le-pjd-boucle-ses-candidatures-49072","2007-04-24","Hay Hassani","PJD","Abdessamad Haïker","district_change","Élu à Anfa en 2002, Abdessamad Haïker doit se présenter à Hay Hassani, séparée de Aïn Chock par le nouveau découpage.","VERIFIED"),
    ("ALM_LEFT_20070529","T2","https://aujourdhui.ma/?p=64236","2007-05-29","Rabat-Océan","PADS-PSU-CNI","Ahmed Benjelloun","head_of_list","Ahmed Benjelloun conduira la liste de l'union PADS-PSU-CNI à Rabat-Océan.","VERIFIED"),
    ("ALM_LEFT_20070529","T2","https://aujourdhui.ma/?p=64236","2007-05-29",None,"PADS-PSU-CNI",None,"alliance","Union formelle PADS-PSU-CNI avec programme et candidatures communes; 75 circonscriptions arrêtées à cette date.","VERIFIED"),
    ("LM_LAST_20070824","T2","https://lematin.ma/journal/2006/ELECTIONS_Les-reglages-de-derniere-heure/74121.html","2007-08-24","Boujdour","MP",None,"withdrawal","Le MP déclare ne pas présenter de liste à Boujdour.","VERIFIED"),
    ("LM_LAST_20070824","T2","https://lematin.ma/journal/2006/ELECTIONS_Les-reglages-de-derniere-heure/74121.html","2007-08-24","Tan-Tan","MP",None,"withdrawal","Le MP déclare ne pas présenter de liste à Tan-Tan.","VERIFIED"),
    ("LM_LAST_20070824","T2","https://lematin.ma/journal/2006/ELECTIONS_Les-reglages-de-derniere-heure/74121.html","2007-08-24","Fqih Ben Salah","SAP","Mohamed Moubdii","party_switch","Mohamed Moubdii, député sortant, quitte le giron MP et conduit une liste sans appartenance politique.","VERIFIED"),
    ("ALM_FES_20070629","T2","https://aujourdhui.ma/24-heures/mohamed-reda-slaouni-epaule-lahcen-daoudi-a-fes-50543","2007-06-29","Fès-Nord","PJD","Mohamed Réda Slaouni","incumbency","Député sortant élu en 2002 à Fès Jdid Dar Dbibagh; placé deuxième sur la liste PJD Fès-Nord.","VERIFIED"),
    ("ALM_FES_20070629","T2","https://aujourdhui.ma/24-heures/mohamed-reda-slaouni-epaule-lahcen-daoudi-a-fes-50543","2007-06-29","Fès-Nord","PJD","Lahcen Daoudi","head_of_list","Lahcen Daoudi choisi tête de liste PJD à Fès-Nord.","VERIFIED"),
    ("ALM_FES_20070629","T2","https://aujourdhui.ma/24-heures/mohamed-reda-slaouni-epaule-lahcen-daoudi-a-fes-50543","2007-06-29","Fès-Nord","PI","Hamid Chabat","local_office","Hamid Chabat, maire de Fès, dirige la liste PI à Fès-Nord.","VERIFIED"),
    ("ALM_SALE_20070815","T2","https://aujourdhui.ma/societe/benkirane-et-sentissi-saffrontent-a-sale-51354","2007-08-15","Salé-Médina","PJD","Abdelilah Benkirane","incumbent_head","Député sortant de Salé-Médina et président du conseil national PJD, candidat de nouveau.","VERIFIED"),
    ("ALM_SALE_20070815","T2","https://aujourdhui.ma/societe/benkirane-et-sentissi-saffrontent-a-sale-51354","2007-08-15","Salé-Médina","MP","Driss Sentissi","local_office","Maire de Salé, député sortant et vice-président de la Chambre, candidat de nouveau.","VERIFIED"),
    ("ALM_TAOUNATE_20070831","T2","https://aujourdhui.ma/politique/tour-du-maroc-des-circonscriptions-electorales-taounate-tissa-alaoui-et-abbou-sans-zarouf-94659","2007-08-31","Taounate-Tissa","RNI","Mohamed Abbou","incumbent_head","Député sortant et président du groupe RNI à la Chambre, candidat à Taounate-Tissa.","VERIFIED"),
    ("ALM_TAOUNATE_20070831","T2","https://aujourdhui.ma/politique/tour-du-maroc-des-circonscriptions-electorales-taounate-tissa-alaoui-et-abbou-sans-zarouf-94659","2007-08-31","Taounate-Tissa","PPS","Messaoudi Ayyachi","withdrawal_health","Député sortant ne se représente pas pour raisons de santé.","VERIFIED"),
    ("ALM_TAOUNATE_20070831","T2","https://aujourdhui.ma/politique/tour-du-maroc-des-circonscriptions-electorales-taounate-tissa-alaoui-et-abbou-sans-zarouf-94659","2007-08-31","Taounate-Tissa","PPS","Ahmed Zarouf","party_switch","Député sortant passé du MP au PPS; absent du scrutin, sa liste PT n'ayant pas été retenue pour inéligibilité du mandataire.","VERIFIED"),
    ("ALM_TEMARA_2007","T2","https://aujourdhui.ma/politique/temara-la-koutla-a-lepreuve-du-pjd-94604","2007-08-21","Skhirat-Témara","Al Ahd","Brahim Chkil","local_office","Candidat Al Ahd et président de la commune de Skhirat.","VERIFIED"),
    ("ALM_TEMARA_2007","T2","https://aujourdhui.ma/politique/temara-la-koutla-a-lepreuve-du-pjd-94604","2007-08-21","Skhirat-Témara","FFD","Brahim El Ouadeh","local_office","Candidat FFD et président de la commune d'Aïn Atik.","VERIFIED"),
    ("ALM_TEMARA_2007","T2","https://aujourdhui.ma/politique/temara-la-koutla-a-lepreuve-du-pjd-94604","2007-08-21","Skhirat-Témara","MP","Ahmed Bella","incumbency","Seul député sortant de la circonscription cherchant un nouveau mandat selon la source.","VERIFIED"),
    ("ALM_OUJDA_2007","T2","https://aujourdhui.ma/politique/tour-des-circonscriptions-electorales-oujda-un-paysage-politique-qui-se-reconfigure-94694","2007-09-06","Oujda","PRV","Mohammed Khalidi","party_switch","Député sortant, candidat PRV et ancien PJD.","VERIFIED"),
  ]
}

NATIONAL_2007=[
 ("LM_CAMPAIGN_20070824","T2","https://lematin.ma/journal/2006/Demarrage-de-la-campagne-electorale-deux-semaines-pour-convaincre_30-sieges-sont-reserves-aux-listes-nationales-des-femmes/74118.html","2007-08-24","95 circonscriptions locales; 295 sièges locaux; 30 sièges de liste nationale; scrutin proportionnel au plus fort reste; seuil annoncé 6%.","VERIFIED"),
 ("LM_INTERIOR_20070831","T2","https://lematin.ma/journal/2007/Scrutin-du-7-septembre_Journal-de-campagne--716-plaintes-pour-violation-du-code-electoral/74300.html","2007-08-31","Ministère de l'Intérieur: 33 partis + 2 unions; 1 870 listes locales; 26 listes nationales; PI et USFP 95 listes, PJD/FFD 94, PPS 92, RNI 91, MP 90, UC 80; union PADS-CNI-PSU 73, PND-Al Ahd 72; 13 listes SAP.","VERIFIED"),
 ("AJ_20070906_STATS","T2","https://www.aljazeera.net/amp/news/2007/9/6/%D8%A7%D9%84%D8%A7%D9%86%D8%AA%D8%AE%D8%A7%D8%A8%D8%A7%D8%AA-%D8%A7%D9%84%D8%AA%D8%B4%D8%B1%D9%8A%D8%B9%D9%8A%D8%A9-%D8%A7%D9%84%D9%85%D8%BA%D8%B1%D8%A8%D9%8A%D8%A9-2007-%D8%A3%D8%B1%D9%82%D8%A7%D9%85","2007-09-06","33 partis; 1 870 listes locales; 26 listes nationales; 6 691 candidats annoncés pour les législatives 2007.","VERIFIED"),
 ("LM_REGIONS_20070902","T2","https://lematin.ma/journal/2007/Legislatives-a-travers-les-regions_15-listes-locales-a-Laayoune-et-23-a-Meknes-Tafilelt/76043.html","2007-09-02","Source MAP annonce 1 862 listes locales (contradiction avec 1 870 du ministère le 31 août) et donne les comptes de listes pour plusieurs circonscriptions.","AMBIGUOUS"),
]

def sha_bytes(b:bytes)->str: return hashlib.sha256(b).hexdigest()
def sha_file(p:Path)->str:
    h=hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda:f.read(1<<20),b""): h.update(chunk)
    return h.hexdigest()
def dump(path,obj):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(obj,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8")
def norm(s):
    s=unicodedata.normalize("NFKD",str(s or ""))
    s="".join(c for c in s if not unicodedata.combining(c))
    s=s.lower().replace("’","'").replace("–","-")
    s=re.sub(r"[^a-z0-9]+"," ",s)
    return " ".join(s.split())

def fetch_text(url):
    req=Request(url,headers={"User-Agent":"Mozilla/5.0 Morocco26HistoricalReconstruction/1.0"})
    with urlopen(req,timeout=30) as r:
        b=r.read()
        return b.decode("utf-8","replace"),sha_bytes(b)

def parse_2002_map():
    cfg=ELECTION[2002]
    try:
        html,raw_sha=fetch_text(cfg["map_url"])
    except Exception as exc:
        return [],{"status":"MISSING","error":repr(exc)}
    try:
        from bs4 import BeautifulSoup
        txt=BeautifulSoup(html,"html.parser").get_text("\n")
    except Exception:
        txt=re.sub(r"<[^>]+>","\n",html)
    txt=txt.replace("\xa0"," ")
    rgx=re.compile(r"(?im)^[ \t•·*-]*Circonscription\s*:?\s*(.+?)\s*$")
    ms=list(rgx.finditer(txt))
    rows=[]
    for i,m in enumerate(ms):
        name=m.group(1).strip(" .:-")
        block=txt[m.end(): ms[i+1].start() if i+1<len(ms) else len(txt)]
        # discard bogus headings / excessively long captures
        if not name or len(name)>100: continue
        def grab(pat):
            mm=re.search(pat,block,re.I)
            return mm.group(1).strip() if mm else None
        def num(v):
            if v is None:return None
            z=re.sub(r"[^\d]","",v)
            return int(z) if z else None
        pref=grab(r"(?:Préfecture|Province)\s*:?\s*([^\n\r]+)")
        pop=num(grab(r"Population\s*:?\s*([0-9 .]+)"))
        reg=num(grab(r"Nombre\s+d['’]inscrits\s*:?\s*([0-9 .]+)"))
        seats=num(grab(r"Nombre\s+de\s+sièges\s*:?\s*([0-9 .]+)"))
        lists=num(grab(r"Nombre\s+de\s+listes\s*:?\s*([0-9 .]+)"))
        cand=num(grab(r"Nombre\s+total\s+de\s+candidats\s*:?\s*([0-9 .]+)"))
        men=num(grab(r"Hommes\s*:?\s*([0-9 .]+)"))
        women=num(grab(r"Femmes\s*:?\s*([0-9 .]+)"))
        if seats is None: continue
        status="VERIFIED"
        ambiguities=[]
        if cand is not None and men is not None and women is not None and cand!=men+women:
            status="AMBIGUOUS"; ambiguities.append(f"candidate_arithmetic:{cand}!={men}+{women}")
        rows.append({"native_id":f"M26-2002-{len(rows)+1:03d}","constituency":name,"prefprov":pref,
                     "population_reported":pop,"registered_reported":reg,"magnitude":seats,
                     "number_lists_documented":lists,"number_candidates_documented":cand,
                     "male_candidates_documented":men,"female_candidates_documented":women,
                     "status":status,"ambiguities":ambiguities,
                     "source_id":"LM_MAP_20020921"})
    return rows,{"status":"VERIFIED" if len(rows)==91 else "AMBIGUOUS","http_sha256":raw_sha,"parsed_count":len(rows)}

def source_record(source_id,source_class,url,pub,territory=None,party=None,candidate=None,fact=None,status="VERIFIED",archive_date=None):
    return {"source_id":source_id,"source_class":source_class,"url":url,"publication_date":pub,
            "archive_date":archive_date,"access_date":ACCESS_DATE,"territory":territory,"party":party,
            "candidate":candidate,"fact":fact,"status":status,"provenance":"CONTEMPORARY_PRE_ELECTION_SOURCE"}

def build(year):
    cfg=ELECTION[year]; outdir=HROOT/str(year)
    outdir.mkdir(parents=True,exist_ok=True)
    sources=[]
    for x in cfg["law_refs"]:
        sources.append(source_record(x["source_id"],x["source_class"],x["url"],x["publication_date"],fact=x["fact"],status=x["status"]))
    native_rows=[]
    map_probe={}
    if year==2002:
        native_rows,map_probe=parse_2002_map()
        if len(native_rows)!=cfg["districts_expected"]:
            raise SystemExit(f"PRE_ELECTION_2002_MAP_FAIL:{len(native_rows)} != {cfg['districts_expected']}")
        sources.append(source_record("LM_MAP_20020921","T2",cfg["map_url"],cfg["map_publication_date"],
            fact="Fiches pré-électorales des circonscriptions: noms, rattachement, inscrits, sièges, listes, candidats et sexe.",status=map_probe["status"]))
    else:
        # 2007: pre-election evidence proves the 95-district regime and selected district changes/counts,
        # but no complete pre-election machine-readable table was recovered in this pass.
        native_rows=[]
        for sid,sc,url,pub,fact,st in NATIONAL_2007:
            sources.append(source_record(sid,sc,url,pub,fact=fact,status=st))
    facts=[]
    for sid,sc,url,pub,terr,party,cand,kind,fact,st in CURATED[year]:
        facts.append({"fact_id":f"{year}-F{len(facts)+1:04d}","territory":terr,"party":party,"candidate":cand,
                      "fact_type":kind,"fact":fact,"status":st,"source_id":sid})
        if not any(s["source_id"]==sid for s in sources):
            sources.append(source_record(sid,sc,url,pub,terr,party,cand,fact,st))
    # Explicit missing fields are never coerced false/zero.
    fields=["candidate_roster","head_of_list","incumbent_mp","incumbent_party","former_mp","party_switch",
            "local_elected_office","provincial_or_regional_office","party_responsibility","former_minister_or_national_office",
            "formal_alliance","formal_endorsement","withdrawal_or_invalidation","death_or_incapacity"]
    universe=[]
    if native_rows:
        fmap={
          "head_of_list":"head_of_list","candidate_rank":"candidate_roster",
          "incumbency":"incumbent_mp","incumbent_head":"incumbent_mp",
          "party_switch":"party_switch","local_office":"local_elected_office",
          "alliance":"formal_alliance","withdrawal":"withdrawal_or_invalidation",
          "withdrawal_health":"withdrawal_or_invalidation"}
        for r in native_rows:
            fs={k:{"value":None,"status":"MISSING","evidence":[]} for k in fields}
            related=[f for f in facts if f.get("territory") and norm(f["territory"])==norm(r["constituency"])]
            for f in related:
                key=fmap.get(f["fact_type"])
                if key:
                    fs[key]["evidence"].append(f["fact_id"])
                    fs[key]["value"]=[x for x in [f.get("candidate"),f.get("party"),f.get("fact")] if x is not None]
                    fs[key]["status"]="VERIFIED" if f["status"]=="VERIFIED" else "AMBIGUOUS"
            universe.append({"native_id":r["native_id"],"territory":r["constituency"],
                "known_pre_election":{"magnitude":r["magnitude"],"registered_reported":r["registered_reported"],
                    "number_lists_documented":r["number_lists_documented"],"number_candidates_documented":r["number_candidates_documented"]},
                "fields":fs})
    snapshot={
      "schema_version":"1.0","year":year,"election_date":cfg["date"],"cutoff":cfg["cutoff"],
      "anti_leakage_assertion":"TARGET_OUTCOME_NOT_USED_IN_PRE_ELECTION_SNAPSHOT",
      "target_outcome_present":False,
      "electoral_system":{"local_constituencies":cfg["districts_expected"],"local_seats":cfg["local_seats"],
        "national_seats":cfg["national_seats"],"allocation":cfg["allocation"],"local_threshold_pct":cfg["local_threshold_pct"],
        "national_list_kind":cfg["national_list_kind"],"national_list_rule_note":cfg["national_list_rule_note"]},
      "territory_snapshot":universe,"verified_facts":facts,
      "unknown_policy":"Unknown != false != zero. Missing values remain null with status MISSING.",
      "notes":["No same-year outcome file is imported or opened by this generator.",
               "2007 full native district table remains separated from snapshot unless recovered from a pre-election legal/archive source."]
    }
    native_map={"schema_version":"1.0","year":year,"source_layer":"PRE_ELECTION_ONLY",
                "expected_local_constituencies":cfg["districts_expected"],"rows":native_rows,
                "map_probe":map_probe,
                "status":"VERIFIED" if len(native_rows)==cfg["districts_expected"] else "PARTIAL"}
    dump(outdir/"historical_native_map_pre_election.json",native_map)
    dump(outdir/"pre_election_snapshot.json",snapshot)
    dump(outdir/"source_inventory_snapshot.json",{"schema_version":"1.0","year":year,"sources":sources})
    recovery={"year":year,"phase":"PRE_ELECTION_RECOVERY","attempts":[]}
    if year==2002:
        recovery["attempts"].append({"route":"contemporary_Le_Matin_MAP_technical_sheets","result":"RECOVERED","detail":f"{len(native_rows)} parsed native constituencies from 21 Sep 2002 pre-election article."})
        recovery["attempts"].append({"route":"BO_5030_decree_2_02_587","result":"IDENTIFIED","detail":"Official pre-election decree identified; contemporary map transcription used for row-level machine data."})
    else:
        recovery["attempts"] += [
          {"route":"SGG_official_decree_2_07_160","result":"IDENTIFIED_TEXT_REFERENCE_NOT_FULL_TABLE_RECOVERED","detail":"Decree identifier and pre-election existence established; exact full 95-row table was not recovered from the accessible official search surface."},
          {"route":"elections2007_gov_ma_archive","result":"REJECTED_FOR_SNAPSHOT_WITHOUT_PRE_CUTOFF_ARCHIVE","detail":"The repo outcome workbook is an archive copy of the official result site, but it is outcome-layer material and is forbidden as a source of snapshot district names."},
          {"route":"contemporary_media_district_articles","result":"PARTIAL","detail":"Contemporary sources establish 95 districts, selected redistricting facts and many district/list counts, but not a complete 95-row native map."},
          {"route":"web_archive_pre_cutoff_probe","result":"UNRESOLVED","detail":"No complete pre-7-Sep-2007 archived official 95-district table was recovered in the research pass; no post-election geometry was backfilled."}
        ]
    dump(outdir/"recovery_log_snapshot.json",recovery)
    # Ambiguities
    amb=[f for f in facts if f["status"]=="AMBIGUOUS"]
    amb += [{"type":"native_map_row","row":r} for r in native_rows if r["status"]=="AMBIGUOUS"]
    if year==2007:
        amb.append({"type":"source_conflict","fact":"Nombre total de listes locales",
                    "values":[{"value":1870,"source_id":"LM_INTERIOR_20070831"},{"value":1862,"source_id":"LM_REGIONS_20070902"}],
                    "status":"AMBIGUOUS"})
    dump(outdir/"ambiguities_snapshot.json",{"year":year,"ambiguities":amb})
    # Coverage with explicit denominators.
    cand_names={f["candidate"] for f in facts if f.get("candidate")}
    inc=[f for f in facts if f["fact_type"] in {"incumbency","incumbent_head"}]
    sw=[f for f in facts if f["fact_type"]=="party_switch"]
    loc=[f for f in facts if f["fact_type"]=="local_office"]
    verified=sum(1 for f in facts if f["status"]=="VERIFIED")+sum(1 for r in native_rows if r["status"]=="VERIFIED")
    ambiguous=sum(1 for f in facts if f["status"]=="AMBIGUOUS")+sum(1 for r in native_rows if r["status"]=="AMBIGUOUS")
    missing=(sum(1 for u in universe for v in u["fields"].values() if v["status"]=="MISSING") if universe else cfg["districts_expected"]*len(fields))
    cov={"year":year,"phase":"PRE_ELECTION_SNAPSHOT",
         "real_constituency_count":cfg["districts_expected"],
         "native_map_pre_election_rows_recovered":len(native_rows),
         "native_map_pre_election_coverage_pct":round(100*len(native_rows)/cfg["districts_expected"],2),
         "candidate_names_verified_count":len(cand_names),
         "candidate_denominator_documented":(sum(int(r.get("number_candidates_documented") or 0) for r in native_rows) if year==2002 else 6691),
         "candidate_coverage_pct":(round(100*len(cand_names)/max(1,sum(int(r.get("number_candidates_documented") or 0) for r in native_rows)),3) if year==2002 and native_rows else (round(100*len(cand_names)/6691,3) if year==2007 else None)),
         "candidate_coverage_denominator_status":("PRE_ELECTION_TECHNICAL_SHEET_SUM" if year==2002 and native_rows else "CONTEMPORARY_NATIONAL_CANDIDATE_TOTAL" if year==2007 else "MISSING"),
         "incumbent_facts_verified_count":len(inc),
         "incumbent_coverage_pct":None,
         "party_switch_facts_verified_count":len(sw),
         "local_office_facts_verified_count":len(loc),
         "facts_VERIFIED":verified,"facts_AMBIGUOUS":ambiguous,"facts_MISSING":missing,
         "snapshot_scientific_status":"PARTIAL_PRE_ELECTION_SNAPSHOT" if len(native_rows)<cfg["districts_expected"] else "PARTIAL_PRE_ELECTION_SNAPSHOT"}
    dump(outdir/"coverage_snapshot.json",cov)
    manifest={"schema_version":"1.0","year":year,"phase":"PRE_ELECTION_SNAPSHOT",
              "cutoff":cfg["cutoff"],"generator":"historical_pre_election_2002_2007.py",
              "forbidden_same_year_outcome_dependencies":True,
              "files":[]}
    for fn in ["historical_native_map_pre_election.json","pre_election_snapshot.json","source_inventory_snapshot.json","recovery_log_snapshot.json","ambiguities_snapshot.json","coverage_snapshot.json"]:
        p=outdir/fn; manifest["files"].append({"path":str(p.relative_to(ROOT)),"sha256":sha_file(p)})
    dump(outdir/"snapshot_manifest.json",manifest)
    cert={"certificate_id":f"M26-HIST-{year}-PRE-ELECTION-FREEZE-V1","year":year,"gate":"PASS",
          "assertion":"TARGET_OUTCOME_NOT_USED_IN_PRE_ELECTION_SNAPSHOT",
          "same_year_outcome_imported":False,"same_year_raw_xlsx_opened":False,
          "cutoff":cfg["cutoff"],"manifest_sha256":sha_file(outdir/"snapshot_manifest.json")}
    dump(outdir/"anti_leakage_certificate.json",cert)
    hashes={fn:sha_file(outdir/fn) for fn in ["historical_native_map_pre_election.json","pre_election_snapshot.json","source_inventory_snapshot.json","recovery_log_snapshot.json","ambiguities_snapshot.json","coverage_snapshot.json","snapshot_manifest.json","anti_leakage_certificate.json"]}
    dump(outdir/"snapshot_hashes_sha256.json",{"year":year,"files":hashes})
    print(json.dumps({"year":year,"native_rows":len(native_rows),"facts":len(facts),"certificate":cert["assertion"]},sort_keys=True))

if __name__=="__main__":
    ap=argparse.ArgumentParser(); ap.add_argument("--year",type=int,choices=[2002,2007],required=True)
    build(ap.parse_args().year)
