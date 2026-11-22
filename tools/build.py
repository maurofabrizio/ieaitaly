#!/usr/bin/env python3
"""Genera il sito statico IEA dall'esportazione XML di WordPress.

Uso:  python3 tools/build.py percorso/export.xml

- Ogni pagina e notizia viene scritta allo STESSO indirizzo che aveva su WordPress
  (es. /progetti/gargano/ -> progetti/gargano/index.html), quindi i vecchi link funzionano.
- Le immagini: se il file esiste in wp-content/uploads del repository si usa quello,
  altrimenti si punta al vecchio server (https://ieaitaly.org/wp-content/...).
  L'elenco delle immagini mancanti finisce in tools/immagini-mancanti.txt.
- Lo script va rilanciato solo per rigenerare tutto dall'esportazione: dopo la messa
  online le pagine HTML si modificano direttamente.
"""
import base64, html, json, os, re, sys, urllib.parse
import xml.etree.ElementTree as ET
from datetime import date

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = "https://ieaitaly.org"
NS = {'wp': 'http://wordpress.org/export/1.2/', 'content': 'http://purl.org/rss/1.0/modules/content/',
      'excerpt': 'http://wordpress.org/export/1.2/excerpt/'}
SKIP = {"test-gutemberg", "il-progetto-test"}          # pagine di prova
NO_IMAGES = {"life-wild-wolf-it", "life-wild-wolf-en"}  # da rifare: solo testo per ora
MENUS = {"Menu 1": "it", "Menu 2": "en", "Croato": "hr"}
HOME = {"it": "/", "en": "/en/iea/", "hr": "/hr/life-alexandro-4/"}

# Corrispondenze tra lingue che Polylang non ha registrato
PAIRS = [
    ("home", "iea", None), ("life-alexandro", "life-alexandro-2", "life-alexandro-4"),
    ("il-progetto", "the-project", "projekt"), ("la-specie", "the-species", "vrsta"),
    ("news", "news-2", "novosti"), ("il-partenariato", "the-partnership", "partnerstvo"),
    ("galleria-fotografica", "galleria-immagini", "galleria-immagini-2"),
    ("webappalexandro", "webapp-alexandro", None), ("contatti-2", "contacts", "kontaktu"),
    ("life-wild-wolf-it", "life-wild-wolf-en", None), ("horizon_it", "erasmus_en", None),
    ("circeo", "circeo_en", None), ("feniglia", "feniglia_en", None), ("veio", "veio_en", None),
    ("prevezione_lazio", "damage_lazio", None), ("ibriwolf", "ibriwolf-en", None),
    ("gargano", "gargano_en", None), ("sibillini", "sibillini_en", None),
    ("gran_sasso", "gran-sasso_en", None), ("mirco", "mirco_en", None), ("orso", "brown-bear", None),
    ("taburno", "taburno_en", None),
    ("kick-off-meeting", "kick-off-meeting-2", None),
    ("primo-corso-di-formazione-per-volontari", "first-training-course-for-volunonteers", None),
    ("protezione-dei-nidi-di-fratino-riserva-naturale-statale-dunafeniglia",
     "protection-of-kentish-plover-nests-duna-feniglia-natural-state-reserve", None),
    ("primo-pulcino-di-fratino-registrato-in-croazia", "this-years-first-young-kentish-plovers-hatched",
     "izlegli-se-prvi-ovogodisnji-mladi-morski-kulici"),
    ("primo-webinar-di-formazione-per-volontari-in-croazia", "first-training-webinar-for-volunteers-in-croatia",
     "prvi-edukativni-webinar-za-volontere-u-hrvatskoj"),
    ("presentazione-web-app-alexandro", "presentation-of-the-alexandro-web-app", None),
]
ALEX_HOMES = {"life-alexandro", "life-alexandro-2", "life-alexandro-4", "life-alexandro-3"}

T = {  # testi dell'interfaccia
 "it": dict(name="Istituto di Ecologia Applicata", menu="Menu", news="Notizie", all_news="Tutte le notizie",
   read="Leggi", back="Torna alle notizie", since="Associazione senza fini di lucro dal 1987",
   contacts="Contatti", projects="Progetti LIFE", privacy="Privacy e cookie", photo="Foto",
   hero="Per un ambiente migliore", go_proj="I nostri progetti", mission="La nostra mission",
   latest="Ultime notizie da LIFE Alexandro", webapp_t="WebApp Alexandro", open_app="Apri la WebApp",
   webapp_p="Dal browser dello smartphone si impara a riconoscere il fratino e si inviano le segnalazioni.",
   write="Per informazioni scrivi a", skip="Vai al contenuto", home="Home"),
 "en": dict(name="Institute of Applied Ecology", menu="Menu", news="News", all_news="All news",
   read="Read", back="Back to news", since="Not-for-profit organisation since 1987",
   contacts="Contacts", projects="LIFE projects", privacy="Privacy and cookies", photo="Photo",
   hero="For a better environment", go_proj="Our projects", mission="Our mission",
   latest="Latest news from LIFE Alexandro", webapp_t="Alexandro WebApp", open_app="Open the WebApp",
   webapp_p="From your smartphone browser, learn to recognise the Kentish plover and send sightings.",
   write="For information write to", skip="Skip to content", home="Home"),
 "hr": dict(name="Istituto di Ecologia Applicata", menu="Izbornik", news="Novosti", all_news="Sve novosti",
   read="Pročitaj", back="Natrag na novosti", since="Neprofitna udruga od 1987.",
   contacts="Kontakt", projects="LIFE projekti", privacy="Privatnost i kolačići", photo="Foto",
   hero="", go_proj="", mission="", latest="", webapp_t="", open_app="", webapp_p="",
   write="Za informacije pišite na", skip="Preskoči na sadržaj", home="Početna"),
}
MONTHS = {"it": "gennaio febbraio marzo aprile maggio giugno luglio agosto settembre ottobre novembre dicembre",
          "en": "January February March April May June July August September October November December",
          "hr": "siječnja veljače ožujka travnja svibnja lipnja srpnja kolovoza rujna listopada studenoga prosinca"}


FIX_TITLES = {"LIFE WILD WOLF": "LIFE Wild Wolf", "Life Alexandro": "LIFE Alexandro", "LIFE Medwolf": "LIFE MedWolf"}


def fdate(d, lang):
    y, m, dd = d[:10].split("-")
    mn = MONTHS[lang].split()[int(m) - 1]
    return f"{int(dd)} {mn} {y}" if lang != "hr" else f"{int(dd)}. {mn} {y}."


# ---------------------------------------------------------------- lettura XML
def load(xml):
    ch = ET.parse(xml).getroot().find("channel")
    att, items, menus = {}, [], []
    for i in ch.findall("item"):
        g = lambda k: (i.find(k, NS).text if i.find(k, NS) is not None else None)
        meta = {m.find("wp:meta_key", NS).text: m.find("wp:meta_value", NS).text for m in i.findall("wp:postmeta", NS)}
        pt, pid = g("wp:post_type"), g("wp:post_id")
        cats = {c.get("domain"): c.text for c in i.findall("category")}
        if pt == "attachment":
            att[pid] = g("wp:attachment_url")
        elif pt == "nav_menu_item":
            menus.append(dict(menu=cats.get("nav_menu"), order=int(g("wp:menu_order")), id=pid,
                              parent=meta.get("_menu_item_menu_item_parent"), obj=meta.get("_menu_item_object_id"),
                              type=meta.get("_menu_item_type"), title=i.find("title").text))
        elif pt in ("page", "post") and g("wp:status") == "publish" and g("wp:post_name") not in SKIP:
            lang = {"Italiano": "it", "English": "en", "Hrvatski": "hr"}.get(cats.get("language"), "it")
            items.append(dict(id=pid, type=pt, slug=g("wp:post_name"), title=FIX_TITLES.get(html.unescape(i.find("title").text or ""), html.unescape(i.find("title").text or "")),
                              date=g("wp:post_date"), body=g("content:encoded") or "", lang=lang,
                              path=urllib.parse.unquote(i.find("link").text.replace(SITE, "")) or "/",
                              thumb=meta.get("_thumbnail_id"), group=cats.get("post_translations")))
    return att, items, menus


# ---------------------------------------------------------------- immagini
LOCAL = {}
MISSING = set()


def index_local():
    up = os.path.join(ROOT, "wp-content", "uploads")
    for d, _, fs in os.walk(up):
        for f in fs:
            rel = "/" + os.path.relpath(os.path.join(d, f), ROOT).replace(os.sep, "/")
            LOCAL[rel] = rel
            stem = re.sub(r"(-\d+x\d+|-scaled)(?=\.\w+$)", "", rel)
            LOCAL.setdefault("stem:" + stem, rel)


def img(path):
    """path = /wp-content/uploads/... -> percorso locale se c'è, altrimenti URL del vecchio server"""
    path = path.split("?")[0]
    if path in LOCAL:
        return path
    stem = re.sub(r"(-\d+x\d+|-scaled)(?=\.\w+$)", "", path)
    if "stem:" + stem in LOCAL:
        return LOCAL["stem:" + stem]
    MISSING.add(path)
    return SITE + path


# ---------------------------------------------------------------- pulizia contenuti
def autop(t):
    out = []
    for ch in re.split(r"\n\s*\n", t.strip()):
        ch = ch.strip()
        if not ch:
            continue
        if re.match(r"<(h\d|ul|ol|blockquote|table|div|figure|hr|pre|iframe)\b", ch):
            out.append(ch)
        elif ch.startswith("<p"):
            out.append(re.sub(r"(?<!>)\n(?!<)", "<br>\n", ch))
        else:
            out.append("<p>" + re.sub(r"\n", "<br>\n", ch) + "</p>")
    return "\n".join(out)


def attrs(s):
    return dict(re.findall(r'(\w+)="([^"]*)"', s))


def vclink(v):
    v = urllib.parse.unquote(v or "")
    m = re.search(r"url:([^|]*)", v)
    return (m.group(1) if m else v).strip()


def clean(body, att, page, items_by_slug):
    raws = []

    def keep_raw(m):
        try:
            raws.append(urllib.parse.unquote(base64.b64decode(m.group(1)).decode("utf-8")))
        except Exception:
            raws.append("")
        return f"@@RAW{len(raws) - 1}@@"
    b = re.sub(r"\[vc_raw_html[^\]]*\](.*?)\[/vc_raw_html\]", keep_raw, body, flags=re.S)
    b = re.sub(r"<!--.*?-->", "", b, flags=re.S)                       # commenti Gutenberg
    # testo dei blocchi WPBakery: paragrafi automatici come faceva WordPress
    if "[vc_" in b:
        b = re.sub(r"\[vc_column_text[^\]]*\](.*?)\[/vc_column_text\]", lambda m: "\n" + autop(m.group(1)) + "\n", b, flags=re.S)
    elif "<p" not in b and "<h" not in b:
        b = autop(b)
    # stili in linea: via tutto tranne la larghezza delle colonne Gutenberg
    b = re.sub(r'\sstyle="(?!flex-basis)[^"]*"', "", b)
    b = re.sub(r"</?(span|font)\b[^>]*>", "", b)
    b = re.sub(r'\s(class)="has-text-align-(left|justify)"', "", b)
    b = b.replace('class="has-text-align-center"', 'class="c"')

    def sc(m):
        tag, a = m.group(1), attrs(m.group(2) or "")
        if tag in ("vc_row", "vc_row_inner"):
            return '<div class="vr">'
        if tag in ("vc_column", "vc_column_inner"):
            w = a.get("width", "")
            cls = {"1/4": "w25", "1/3": "w33", "1/2": "w50", "2/3": "w66", "3/4": "w75", "5/6": "w83", "1/6": "w17"}.get(w, "")
            return f'<div class="vc {cls}">'
        if tag == "vc_single_image":
            if page["slug"] in NO_IMAGES:
                return ""
            u = att.get(a.get("image", ""))
            if not u:
                return ""
            src = img(urllib.parse.urlparse(u).path)
            i = f'<img src="{src}" alt="" loading="lazy">'
            if a.get("onclick") == "custom_link" and a.get("link"):
                i = f'<a href="{a["link"].strip()}">{i}</a>'
            return f'<figure class="vimg{" c" if a.get("alignment") == "center" else ""}">{i}</figure>'
        if tag == "vc_btn":
            return f'<a class="vbtn" href="{vclink(a.get("link"))}">{html.escape(a.get("title", ""))}</a>'
        if tag == "vc_custom_heading":
            t, l = html.escape(urllib.parse.unquote(a.get("text", ""))), vclink(a.get("link"))
            return f'<h3 class="c">{f"<a href=\"{l}\">{t}</a>" if l else t}</h3>'
        if tag == "contact-form-7":
            return "@@FORM@@"
        return ""
    b = re.sub(r"\[(?!/)([a-z_0-9\-]+)((?:\s[^\]]*)?)\]", sc, b)
    b = re.sub(r"\[/(vc_row|vc_row_inner|vc_column|vc_column_inner)\]", "</div>", b)
    b = re.sub(r"\[/?[a-z_0-9\-]+[^\]]*\]", "", b)                       # codici rimasti
    if page["slug"] in NO_IMAGES:
        b = re.sub(r"<figure[^>]*>.*?</figure>|<img[^>]*>", "", b, flags=re.S)
    b = b.replace("@@FORM@@", f'<div class="mailbox">{T[page["lang"]]["write"]} '
                              f'<a href="mailto:iea@ieaitaly.org">iea@ieaitaly.org</a></div>')
    # immagini e link verso il sito stesso
    b = re.sub(r'(src|href)="https?://(?:www\.)?ieaitaly\.org(/wp-content/uploads/[^"]+)"',
               lambda m: f'{m.group(1)}="{img(m.group(2))}"', b)
    b = re.sub(r'href="\s*https?://(?:www\.)?ieaitaly\.org(/[^"]*)?"',
               lambda m: f'href="{resolve(m.group(1) or "/", items_by_slug)}"', b)
    b = re.sub(r'\s(target="_blank"|rel="[^"]*"|data-[\w-]+="[^"]*"|data-id="\d+")', "", b)
    b = re.sub(r'<img ', '<img loading="lazy" ', b).replace('loading="lazy" loading="lazy"', 'loading="lazy"')
    b = re.sub(r"<(p|h\d)[^>]*>(\s|&nbsp;|<br\s*/?>)*</\1>", "", b)
    b = re.sub(r'<div class="vr">\s*(<div class="vc ?\w*">\s*</div>\s*)*</div>', "", b)
    b = re.sub(r"<table", '<div class="tw"><table', b).replace("</table>", "</table></div>")
    b = re.sub(r"\n{3,}", "\n\n", b).strip()
    for n, r in enumerate(raws):
        b = b.replace(f"@@RAW{n}@@", r)
    return b


PATHS = set()


def resolve(p, by_slug):
    """Riporta un indirizzo interno a una pagina esistente (WordPress accettava anche /slug/ abbreviati)."""
    p = p.strip()
    frag = ""
    if "#" in p:
        p, frag = p.split("#", 1)
        frag = "#" + frag
    p = p.split("?")[0]
    if p.startswith("/wp-content/"):
        return img(p)
    if not p.endswith("/"):
        p += "/"
    if p in PATHS:
        return p + frag
    slug = p.strip("/").split("/")[-1] if p != "/" else ""
    if slug in by_slug:
        return by_slug[slug]["path"] + frag
    return p + frag


# ---------------------------------------------------------------- impaginazione
def rel(target, here):
    """Converte /a/b/ in percorso relativo rispetto alla pagina 'here' (funziona anche in sottocartella)."""
    if not target.startswith("/") or target.startswith("//"):
        return target
    depth = len([x for x in here.strip("/").split("/") if x])
    pre = "../" * depth or "./"
    return pre + target.lstrip("/")


def relativize(doc, here):
    return re.sub(r'(href|src)="(/(?!/)[^"]*)"', lambda m: f'{m.group(1)}="{rel(m.group(2), here)}"', doc)


def nav_html(menu, lang, here, by_id):
    T_ = T[lang]
    tops = sorted([m for m in menu if m["parent"] in (None, "0")], key=lambda m: m["order"])
    out = []
    for m in tops:
        if m["type"] == "custom":
            continue
        pg = by_id.get(m["obj"])
        if not pg:
            continue
        kids = sorted([k for k in menu if k["parent"] == m["id"]], key=lambda k: k["order"])
        title = FIX_TITLES.get(m["title"] or pg["title"], m["title"] or pg["title"])
        if pg["path"] == HOME.get(lang):
            title = T_["home"]
        cur = ' aria-current="page"' if pg["path"] == here or (kids and any(by_id.get(k["obj"], {}).get("path") == here for k in kids)) else ""
        cls = []
        if kids:
            cls.append("has")
        if "alexandro" in pg["slug"]:
            cls.append("life")
        li = f'<li{" class=\"" + " ".join(cls) + "\"" if cls else ""}><a href="{pg["path"]}"{cur}>{html.escape(title)}</a>'
        if kids:
            li += '<ul class="sub">' + "".join(
                f'<li><a href="{by_id[k["obj"]]["path"]}"{" aria-current=\"page\"" if by_id[k["obj"]]["path"] == here else ""}>'
                f'{html.escape(k["title"] or by_id[k["obj"]]["title"])}</a></li>' for k in kids if k["obj"] in by_id) + "</ul>"
        out.append(li + "</li>")
    return '<ul class="nav">' + "".join(out) + "</ul>"


def page_html(p, content, ctx, wide=False, before="", after="", full=False, title_h1=True, cls=""):
    lang, here = p["lang"], p["path"]
    T_ = T[lang]
    trans = ctx["trans"].get(p["slug"], {})
    langs = "".join(
        f'<a href="{trans.get(l, HOME[l])}" hreflang="{l}" lang="{l}"{" aria-current=\"true\"" if l == lang else ""}>{l.upper()}</a>'
        for l in ("it", "en", "hr"))
    alts = "".join(f'<link rel="alternate" hreflang="{l}" href="{SITE}{u}">' for l, u in trans.items())
    text = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", re.sub(r"<style.*?</style>|<script.*?</script>", "", content, flags=re.S)))).strip()
    desc = html.escape(text[:155].rsplit(" ", 1)[0] + "…" if len(text) > 155 else text)
    ttl = html.escape(p["title"])
    head_t = f'{ttl} – IEA' if here != HOME.get(lang) else f'IEA – {T_["name"]}'
    menu = nav_html(ctx["menus"][lang], lang, here, ctx["by_id"])
    main = content if full else (
        f'<div class="wrap page p-{p["slug"]} {cls}">{before}{"<h1>" + ttl + "</h1>" if title_h1 else ""}'
        f'<div class="content{" wide" if wide else ""}">{content}</div>{after}</div>')
    doc = f'''<!DOCTYPE html>
<html lang="{lang}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{head_t}</title>
<meta name="description" content="{desc}">
<link rel="canonical" href="{SITE}{here}">{alts}
<meta property="og:title" content="{ttl}"><meta property="og:description" content="{desc}">
<meta property="og:url" content="{SITE}{here}"><meta property="og:type" content="website">
<link rel="icon" href="/assets/favicon.png">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Literata:opsz,wght@7..72,600;7..72,700&family=Source+Sans+3:wght@400;600;700&display=swap" rel="stylesheet">
<link rel="stylesheet" href="/assets/site.css">
</head>
<body>
<a class="skip" href="#main">{T_["skip"]}</a>
<header class="top"><div class="bar">
 <a class="brand" href="{HOME[lang]}"><img src="/wp-content/uploads/2019/10/cropped-images-1-5.png" alt="IEA – Istituto di Ecologia Applicata" width="618" height="139"></a>
 <button class="burger" aria-expanded="false" aria-controls="menu">{T_["menu"]}</button>
 <nav class="menu" id="menu" aria-label="Menu">{menu}<div class="lang" role="group" aria-label="Lingua">{langs}</div></nav>
</div></header>
<main id="main">
{main}
</main>
<footer class="foot"><div class="wrap">
 <div class="cards">
  <div><h3>{T[lang]["name"] if lang != "hr" else "Istituto di Ecologia Applicata"}</h3><p>{T_["since"]}<br>Via C. Colombo 456, 00145 Roma</p></div>
  <div><h3>{T_["projects"]}</h3><p>{ctx["foot_links"][lang]}</p></div>
  <div><h3>{T_["contacts"]}</h3><p><a href="mailto:iea@ieaitaly.org">iea@ieaitaly.org</a><br>PEC istitutoecologiaapplicata@legalmail.it<br>+39 06 4403315</p></div>
 </div>
 <p class="legal">© {date.today().year} Istituto di Ecologia Applicata · <a href="https://www.iubenda.com/privacy-policy/35549680">{T_["privacy"]}</a> · {T_["photo"]}: <a href="https://www.paolafazzi.com">Paola Fazzi</a></p>
</div></footer>
<script src="/assets/site.js"></script>
</body>
</html>
'''
    return relativize(doc, here)


def write(path, doc):
    f = os.path.join(ROOT, path.strip("/"), "index.html") if path != "/" else os.path.join(ROOT, "index.html")
    os.makedirs(os.path.dirname(f), exist_ok=True)
    with open(f, "w", encoding="utf-8") as fh:
        fh.write(doc)


# ---------------------------------------------------------------- elenco progetti
def projects_list(c, lang):
    """Trasforma la pagina Progetti di WordPress (elenco puntato + paragrafo Fondi/Durata) in righe ordinate."""
    rows = []
    for li, meta in re.findall(r"<li>(.*?)</li>.*?</ul>\s*(?:<br>\s*)?<p>(.*?)</p>", c, re.S):
        title_link = re.search(r'<a href="([^"]+)"', li)
        title = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", li))).strip()
        title = re.sub(r"\s+([.,])", r"\1", title)
        m = re.sub(r"<br\s*/?>", "\n", meta)
        def field(*names):
            for n in names:
                r = re.search(n + r"\s*(?:</em>)?\s*:?\s*(?:</em>)?(?:<em>\s*</em>)?\s*:?(.*?)(?=\n|<em>|$)", m, re.S | re.I)
                if r:
                    return r.group(1).strip()
            return ""
        funds = html.unescape(re.sub(r"<[^>]+>", "", field("Fondi", "Funds"))).strip(" .:")
        years = re.sub(r"\s*[–-]\s*", "–", html.unescape(re.sub(r"<[^>]+>", "", field("Durata", "Duration")))).strip(" .:")
        doc = re.search(r'(?:Documentazione|Documentation)[^<]*(?:</em>)?[^<]*(<a href="([^"]+)">(.*?)</a>)', meta, re.S)
        rows.append(dict(title=title, link=title_link.group(1) if title_link else "", funds=funds, years=years,
                         doc=(doc.group(2), html.unescape(doc.group(3))) if doc else None))
    if len(rows) < 5:
        return c
    L = (lambda it, en: it) if lang == "it" else (lambda it, en: en)
    now = date.today().year
    def ongoing(y):
        e = re.findall(r"\d{4}", y)
        return bool(e) and int(e[-1]) >= now
    def isue(r):
        return bool(re.search(r"\b(EU|UE|European|Europea|LIFE|Horizon|Erasmus|Biodiversa)\b", r["title"] + " " + r["funds"]))
    lis = []
    for r in rows:
        t = html.escape(r["title"])
        if r["link"]:
            t = f'<a href="{r["link"]}">{t}</a>'
        tag = f'<span class="tag">{L("in corso", "ongoing")}</span>' if ongoing(r["years"]) else ""
        doc = ""
        if r["doc"]:
            label = r["doc"][1]
            if "contatt" in label.lower() or "contact" in label.lower():
                doc = f' · <a href="{r["doc"][0]}">{L("chiedi la documentazione", "ask for documentation")}</a>'
            else:
                doc = f' · <a href="{r["doc"][0]}">{L("sito del progetto", "project website")}</a>'
        lis.append(f'<li data-k="{"on " if ongoing(r["years"]) else ""}{"ue" if isue(r) else ""}"><span class="yr">{html.escape(r["years"])}</span>'
                   f'<div><div class="t">{t}{tag}</div><div class="f">{html.escape(r["funds"])}{doc}</div></div></li>')
    return (f'<p class="lead">{L("Dal 1987 l’Istituto lavora sui conflitti tra attività umane e fauna selvatica, sul monitoraggio e sulla gestione dei grandi carnivori, per la Commissione Europea, i ministeri, le regioni e i parchi.", "Since 1987 the Institute has worked on human–wildlife conflicts and on the monitoring and management of large carnivores for the European Commission, ministries, regions and parks.")}</p>'
            f'<div class="tools"><input id="pq" type="search" placeholder="{L("Cerca per titolo, ente, parco…", "Search by title, funder, park…")}" aria-label="{L("Cerca nei progetti", "Search projects")}">'
            f'<button class="chip" aria-pressed="true" data-f="">{L("Tutti", "All")}</button><button class="chip" aria-pressed="false" data-f="on">{L("In corso", "Ongoing")}</button>'
            f'<button class="chip" aria-pressed="false" data-f="ue">{L("Progetti europei", "EU projects")}</button></div>'
            f'<p class="count" id="pc" data-of="{L("progetti su", "projects of")}"></p><ul class="plist" id="pl">{"".join(lis)}</ul>'
            f'<p class="count" id="pn" hidden>{L("Nessun progetto corrisponde alla ricerca.", "No project matches your search.")}</p>')


# ---------------------------------------------------------------- notizie
def excerpt(body, n=150):
    t = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", re.sub(r"<!--.*?-->", "", body, flags=re.S)))).strip()
    return t if len(t) <= n else t[:n].rsplit(" ", 1)[0] + "…"


def first_img(body):
    m = re.search(r'<img[^>]+src="https?://(?:www\.)?ieaitaly\.org(/wp-content/uploads/[^"]+)"', body)
    return m.group(1) if m else None


def news_cards(posts, lang, att):
    out = []
    for p in posts:
        ph = att.get(p["thumb"] or "")
        ph = urllib.parse.urlparse(ph).path if ph else first_img(p["body"])
        pic = f'<div class="ph"><img src="{img(ph)}" alt="" loading="lazy"></div>' if ph else '<div class="ph"></div>'
        t = p["title"]
        if t.isupper():
            t = t[:1] + t[1:].lower()
        out.append(f'<a class="card" href="{p["path"]}">{pic}<div class="in"><time datetime="{p["date"][:10]}">'
                   f'{fdate(p["date"], lang)}</time><h3>{html.escape(t)}</h3><p>{html.escape(excerpt(p["body"]))}</p></div></a>')
    return '<div class="cards">' + "".join(out) + "</div>"


# ---------------------------------------------------------------- home
HERO_SVG = open(os.path.join(ROOT, "tools", "hero.svg"), encoding="utf-8").read()


def home_html(lang, ctx, posts, by_slug, att):
    T_ = T[lang]
    s = lambda k: by_slug[k]["path"]
    intro = {"it": "L’Istituto di Ecologia Applicata (IEA) è un’associazione senza fini di lucro fondata nel 1987 che fornisce supporto a istituzioni pubbliche e private, in Italia e all’estero, per interventi connessi alla gestione delle risorse naturali, in particolare della fauna e degli habitat terrestri e marini.",
             "en": "The Institute of Applied Ecology (IEA) is a not-for-profit organisation established in 1987 to support public and private organisations, in Italy and abroad, in the management of natural assets, particularly terrestrial and marine wildlife and habitats."}[lang]
    L = lambda it, en: it if lang == "it" else en
    cards = [
        (s(L("life-alexandro", "life-alexandro-2")), "/wp-content/uploads/2026/04/1_Life-Alexandro_LOGO-DEF-4-1024x421.png", "LIFE Alexandro",
         L("Azioni concrete per migliorare la conservazione del fratino in Italia e Croazia (2026–2031).",
           "Concrete actions to improve the conservation of the Kentish plover in Italy and Croatia (2026–2031).")),
        (s(L("life-wild-wolf-it", "life-wild-wolf-en")), None, "LIFE Wild Wolf",
         L("Azioni concrete per scoraggiare la presenza del lupo nelle aree abitate in Europa (2023–2027).",
           "Concrete actions to deter wolves from human-dominated areas in Europe (2023–2027).")),
        (s(L("life-medwolf", "medwolf")), "/wp-content/uploads/2020/02/icona-logo-lifemedwolf2.png", "LIFE MedWolf",
         L("Svolto in Italia e Portogallo da settembre 2012 a novembre 2017, ha coinvolto organizzazioni agricole e ambientaliste, istituzioni e centri di ricerca.",
           "The project took place in Italy and Portugal from September 2012 to November 2017, involving agricultural and environmental associations, institutions and research centres.")),
        (s(L("piattaforma", "stakeholder-platforms")), "/wp-content/uploads/2020/02/icona-logo-piattaforma-locale.png", L("Piattaforma locale", "Stakeholder platforms"),
         L("Spazi di dialogo tra i gruppi d’interesse coinvolti dalla presenza dei grandi carnivori nelle aree di intervento.",
           "Spaces of dialogue among the parties interested in the presence of large carnivores in their areas.")),
    ]
    cards_h = "".join(
        f'<a class="card" href="{u}"><div class="ph logo">{f"<img src=\"{img(i)}\" alt=\"\" loading=\"lazy\">" if i else WOLF_SVG}</div>'
        f'<div class="in"><h3>{t}</h3><p>{d}</p></div></a>' for u, i, t, d in cards)
    news_l = s(L("news", "news-2"))
    webapp = s(L("webappalexandro", "webapp-alexandro"))
    return f'''<section class="hero"><div class="txt">
<h1>{T_["hero"]}</h1><p>{intro}</p>
<div class="row"><a class="btn" href="{s(L("progetti", "projects"))}">{T_["go_proj"]}</a><a class="btn ghost" href="{s(L("chi-siamo", "about-2"))}">{L("Chi siamo", "About us")}</a></div>
</div>{HERO_SVG}</section>
<section class="band"><div class="wrap"><div class="cards">{cards_h}</div>
<p style="margin-top:22px"><a href="{s(L("progetti", "projects"))}">{L("Tutti i progetti dal 1987", "All projects since 1987")} →</a></p></div></section>
<section class="band sandband"><div class="wrap">
<h2 style="margin-top:0">{T_["latest"]}</h2>{news_cards(posts[:3], lang, att)}
<p style="margin-top:18px"><a href="{news_l}">{T_["all_news"]} →</a></p></div></section>
<section class="band"><div class="wrap feat">
<div><h2 style="margin-top:0">{T_["mission"]}</h2><p class="quote">{L("Gestire l’ambiente e i conflitti tra le attività antropiche e la fauna selvatica, valorizzare e conservare le risorse naturali utilizzando pratiche partecipative e sulla base di solide evidenze scientifiche.", "Managing the environment and the conflicts between human activities and wildlife, enhancing and conserving natural resources through participatory practices based on sound scientific evidence.")}</p>
<p><a href="{s(L("mission", "our-mission"))}">{L("Campi di attività", "Fields of activity")} →</a></p></div>
<div class="card"><div class="ph logo"><img src="{img("/wp-content/uploads/2026/03/LogoLifeAlexandro-1024x1024.jpg")}" alt="" loading="lazy"></div><div class="in"><h3>{T_["webapp_t"]}</h3><p>{T_["webapp_p"]}</p><p style="margin-top:12px"><a class="btn" href="{webapp}">{T_["open_app"]}</a></p></div></div>
</div></section>'''


WOLF_SVG = '<svg viewBox="0 0 160 100" width="100%" height="100%" aria-hidden="true"><rect width="160" height="100" fill="#1f5d68"/><path d="M0 70 L40 40 L70 58 L105 30 L160 64 V100 H0Z" fill="#245a5c"/><g transform="translate(62 50)" fill="#0c2a30"><path d="M0 14 C6 8 14 7 24 8 L40 8 C46 8 49 4 52 0 L54 -6 L57 -1 L60 -5 L60 2 C63 4 64 7 61 9 L56 10 C54 13 52 16 50 22 L48 32 L45 32 L46 22 L36 20 L30 21 L26 32 L23 32 L24 21 C18 21 13 20 9 23 L6 32 L3 32 L4 22 C1 22 -3 26 -9 28 C-6 24 -3 18 0 14Z"/></g></svg>'


# ---------------------------------------------------------------- main
def main(xml):
    index_local()
    att, items, menus = load(xml)
    by_id = {p["id"]: p for p in items}
    by_slug = {p["slug"]: p for p in items}
    PATHS.update(p["path"] for p in items)
    # lingua della pagina: quella del menu in cui compare (corregge errori di Polylang)
    for m in menus:
        if m["obj"] in by_id and m["menu"] in MENUS:
            by_id[m["obj"]]["lang"] = MENUS[m["menu"]]
    # traduzioni
    trans = {}
    groups = {}
    for p in items:
        if p["group"]:
            groups.setdefault(p["group"], {})[p["lang"]] = p["path"]
    for p in items:
        if p["group"]:
            trans[p["slug"]] = groups[p["group"]]
    for tup in PAIRS:
        d = {l: by_slug[s]["path"] for l, s in zip(("it", "en", "hr"), tup) if s and s in by_slug}
        for s in tup:
            if s:
                trans[s] = d
    trans["home"] = trans["iea"] = {"it": "/", "en": "/en/iea/", "hr": "/hr/life-alexandro-4/"}
    menus_l = {l: [m for m in menus if MENUS.get(m["menu"]) == l] for l in ("it", "en", "hr")}
    # sotto-menu del progetto Alexandro, per lingua
    alex = {}
    for l, mm in menus_l.items():
        top = [m for m in mm if by_id.get(m["obj"], {}).get("slug") in ALEX_HOMES]
        if l == "hr":
            kids = sorted([m for m in mm if m["type"] != "custom"], key=lambda m: m["order"])
        else:
            kids = [top[0]] + sorted([m for m in mm if m["parent"] == top[0]["id"]], key=lambda m: m["order"])
        alex[l] = [(by_id[m["obj"]]["path"], by_id[m["obj"]]["title"]) for m in kids if m["obj"] in by_id]
    foot = {
        "it": '<a href="/life-alexandro/">LIFE Alexandro</a><br><a href="/life-wild-wolf-it/">LIFE Wild Wolf</a><br><a href="/progetti/life-medwolf/">LIFE MedWolf</a>',
        "en": '<a href="/en/life-alexandro-2/">LIFE Alexandro</a><br><a href="/en/life-wild-wolf-en/">LIFE Wild Wolf</a><br><a href="/en/projects/medwolf/">LIFE MedWolf</a>',
        "hr": '<a href="/hr/life-alexandro-4/">LIFE Alexandro</a>'}
    ctx = dict(trans=trans, menus=menus_l, by_id=by_id, foot_links=foot)
    posts = {l: sorted([p for p in items if p["type"] == "post" and p["lang"] == l], key=lambda p: p["date"], reverse=True)
             for l in ("it", "en", "hr")}
    alex_paths = {l: {u for u, _ in v} for l, v in alex.items()}

    def subnav(lang, here):
        return '<nav class="subnav" aria-label="LIFE Alexandro">' + "".join(
            f'<a href="{u}"{" aria-current=\"page\"" if u == here else ""}>{html.escape(t if not (t.lower().startswith("life alex")) else "LIFE Alexandro")}</a>'
            for u, t in alex[lang]) + "</nav>"

    sitemap = []
    for p in items:
        lang = p["lang"]
        if p["slug"] == "home":
            write("/", page_html(p, home_html("it", ctx, posts["it"], by_slug, att), ctx, full=True)); sitemap.append("/"); continue
        if p["slug"] == "iea":
            write(p["path"], page_html(p, home_html("en", ctx, posts["en"], by_slug, att), ctx, full=True)); sitemap.append(p["path"]); continue
        c = clean(p["body"], att, p, by_slug)
        before, after, wide, full, h1, cls = "", "", False, False, True, ""
        in_alex = p["path"] in alex_paths.get(lang, set()) or p["type"] == "post" or p["slug"] == "life-alexandro-3"
        if p["type"] == "post":
            news_p = by_slug[{"it": "news", "en": "news-2", "hr": "novosti"}[lang]]["path"]
            before = subnav(lang, news_p) + f'<p class="crumbs"><a href="{news_p}">← {T[lang]["back"]}</a></p>'
            t = p["title"]
            p = dict(p, title=(t[:1] + t[1:].lower()) if t.isupper() else t)
            c = f'<p class="pmeta">{fdate(p["date"], lang)}</p>' + c
        elif in_alex:
            before = subnav(lang, p["path"])
            if p["slug"] in ("news", "news-2", "novosti"):
                c = news_cards(posts[lang], lang, att) + re.sub(r'^\s*<div class="wp-block-query">.*?</div>', "", c, flags=re.S)
                c = re.sub(r'<div class="wp-block-query">.*?</div>', "", c, flags=re.S)
                wide = True
            if p["slug"] in ALEX_HOMES:
                h1, cls = False, "alexhome"
            if p["slug"] in ALEX_HOMES or p["slug"] in ("galleria-fotografica", "galleria-immagini", "galleria-immagini-2", "il-partenariato", "the-partnership", "partnerstvo"):
                wide = True
            if p["slug"] in ("webappalexandro", "webapp-alexandro"):
                full = True
                c = f'<div class="wrap" style="padding-top:20px">{before}</div><div class="fullbleed">{c}</div>'
        if p["slug"] in ("progetti", "projects"):
            c = projects_list(c, lang)
        if p["slug"] in ("chi-siamo", "chi-siamo-2", "about-2", "mission", "our-mission", "progetti", "projects", "life-alexandro-4"):
            wide = True
        if p["slug"] in ("home", "iea") or p["path"] in ("/iea-it/",):
            wide = True
        if p["title"].endswith("_en"):
            p = dict(p, title=p["title"][:-3])
        write(p["path"], page_html(p, c, ctx, wide=wide, before=before, after=after, full=full, title_h1=h1, cls=cls))
        sitemap.append(p["path"])
    # indirizzi abbreviati che WordPress accettava (/gargano/ -> /progetti/gargano/)
    for p in items:
        segs = [x for x in p["path"].strip("/").split("/") if x]
        if p["type"] == "page" and len(segs) == 2 and segs[0] == "progetti":
            short = "/" + segs[-1] + "/"
            if short not in PATHS:
                PATHS.add(short)
                write(short, f'<!DOCTYPE html><meta charset="utf-8"><title>IEA</title><link rel="canonical" href="{SITE}{p["path"]}">'
                             f'<meta http-equiv="refresh" content="0; url={rel(p["path"], short)}"><a href="{rel(p["path"], short)}">{html.escape(p["title"])}</a>')
    # 404, sitemap, robots
    p404 = dict(id="0", type="page", slug="404", title="Pagina non trovata", lang="it", path="/404/", group=None)
    doc = page_html(p404, '<p>La pagina che cerchi non esiste o è stata spostata. <a href="/">Torna alla home</a>.</p>'
                          '<p lang="en">The page you are looking for does not exist. <a href="/en/iea/">English home</a>.</p>', ctx)
    doc = doc.replace('href="../', 'href="/').replace('src="../', 'src="/')  # il 404 viene servito da qualunque percorso
    open(os.path.join(ROOT, "404.html"), "w", encoding="utf-8").write(doc)
    open(os.path.join(ROOT, "sitemap.xml"), "w", encoding="utf-8").write(
        '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "".join(f"<url><loc>{SITE}{u}</loc></url>\n" for u in sorted(set(sitemap))) + "</urlset>\n")
    open(os.path.join(ROOT, "robots.txt"), "w").write(f"User-agent: *\nAllow: /\nSitemap: {SITE}/sitemap.xml\n")
    open(os.path.join(ROOT, ".nojekyll"), "w").write("")
    with open(os.path.join(ROOT, "tools", "immagini-mancanti.txt"), "w") as f:
        f.write("# Immagini usate dal sito ma non ancora presenti nel repository.\n"
                "# Copiarle negli stessi percorsi (wp-content/uploads/...) e rilanciare build.py.\n")
        f.write("\n".join(sorted(MISSING)) + "\n")
    print(f"pagine: {len(sitemap)}  immagini mancanti: {len(MISSING)}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "tools", "export.xml"))
