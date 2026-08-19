import json,re,sys
from pathlib import Path
R=Path(__file__).resolve().parents[1]/'web'
out=Path(sys.argv[1])
html=(R/'index.html').read_text(encoding='utf-8')
css=(R/'styles.css').read_text(encoding='utf-8')+(R/'reader-final.css').read_text(encoding='utf-8')
app=(R/'app.js').read_text(encoding='utf-8')
reader=(R/'reader.js').read_text(encoding='utf-8')
body=html[html.index('<body>')+6:html.index('</body>')]
body=body.replace('<script src="app.js"></script>','').replace('<script src="reader.js"></script>','')
def payload(name):
    d=json.loads((R/'data'/name).read_text(encoding='utf-8'))
    return json.dumps(d,ensure_ascii=False,separators=(',',':')).replace('</','<\\/')
page='''<!doctype html><html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>ATLAS // Société artificielle du Maroc</title><style>'''+css+'''</style></head><body>'''+body+'''\n<script type="application/json" id="d-societe">'''+payload('societe.json')+'''</script>\n<script type="application/json" id="d-portraits">'''+payload('portraits.json')+'''</script>\n<script type="application/json" id="d-simulateur">'''+payload('simulateur.json')+'''</script>\n<script type="application/json" id="d-maroc">'''+payload('maroc.json')+'''</script>\n<script>'''+app+'''</script>\n<script>'''+reader+'''</script>\n</body></html>'''
out.write_text(page,encoding='utf-8')
print(out, out.stat().st_size)
