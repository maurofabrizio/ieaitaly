#!/usr/bin/env python3
"""Genera il sito statico IEA dall'esportazione XML di WordPress.

Uso:  python3 tools/build.py percorso/export.xml

- Pagine e notizie restano agli STESSI indirizzi di WordPress.
- I testi vengono presi dall'esportazione; la presentazione (home, chi siamo, mission,
  progetti, contatti, schede progetto, sezione LIFE Alexandro) è disegnata qui.
- Immagini: se il file è in wp-content/uploads del repository si usa quello,
  altrimenti si punta al vecchio server. Elenco in tools/immagini-mancanti.txt.
"""
import base64, html, os, re, sys, urllib.parse
import xml.etree.ElementTree as ET
from datetime import date

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = "https://ieaitaly.org"
NS = {'wp': 'http://wordpress.org/export/1.2/', 'content': 'http://purl.org/rss/1.0/modules/content/'}
SKIP = {"test-gutemberg", "il-progetto-test"}
NO_IMAGES = {"life-wild-wolf-it", "life-wild-wolf-en"}
MENUS = {"Menu 1": "it", "Menu 2": "en", "Croato": "hr"}
HOME = {"it": "/", "en": "/en/iea/", "hr": "/hr/life-alexandro-4/"}
FIX_TITLES = {"LIFE WILD WOLF": "LIFE Wild Wolf", "Life Alexandro": "LIFE Alexandro", "LIFE Medwolf": "LIFE MedWolf",
              "Homeen": "Home", "Piattaforma": "Piattaforma locale dei grandi carnivori"}
PAIRS = [
    ("home", "iea", None), ("chi-siamo", "about-2", None), ("mission", "our-mission", None),
    ("progetti", "projects", None), ("contatti", "contact", None),
    ("life-medwolf", "medwolf", None), ("piattaforma", "stakeholder-platforms", None),
    ("life-alexandro", "life-alexandro-2", "life-alexandro-4"),
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
AX_KEYS = ["home", "project", "species", "news", "partners", "gallery", "webapp", "contacts"]
AX = {"it": ["life-alexandro", "il-progetto", "la-specie", "news", "il-partenariato", "galleria-fotografica", "webappalexandro", "contatti-2"],
      "en": ["life-alexandro-2", "the-project", "the-species", "news-2", "the-partnership", "galleria-immagini", "webapp-alexandro", "contacts"],
      "hr": ["life-alexandro-4", "projekt", "vrsta", "novosti", "partnerstvo", "galleria-immagini-2", None, "kontaktu"]}
AX_LABEL = {"it": ["Il progetto in breve", "Obiettivi e azioni", "La specie", "Notizie", "Partenariato", "Galleria", "WebApp", "Contatti"],
            "en": ["Overview", "Aims and actions", "The species", "News", "Partnership", "Gallery", "WebApp", "Contacts"],
            "hr": ["Ukratko", "Ciljevi i aktivnosti", "Vrsta", "Novosti", "Partnerstvo", "Galerija", "WebApp", "Kontakt"]}
MONTHS = {"it": "gennaio febbraio marzo aprile maggio giugno luglio agosto settembre ottobre novembre dicembre",
          "en": "January February March April May June July August September October November December",
          "hr": "siječnja veljače ožujka travnja svibnja lipnja srpnja kolovoza rujna listopada studenoga prosinca"}


def fdate(d, lang):
    y, m, dd = d[:10].split("-")
    mn = MONTHS[lang].split()[int(m) - 1]
    return f"{int(dd)}. {mn} {y}." if lang == "hr" else f"{int(dd)} {mn} {y}"


def sentence(t):
    """'PROTEZIONE DEI NIDI' -> 'Protezione dei nidi' (solo per titoli tutti maiuscoli)."""
    if t.upper() != t or not re.search(r"[A-Z]{4}", t):
        return t
    keep = {"LIFE", "IEA", "WEB", "APP", "P.N.", "UE", "EU", "UNIPI", "LIPU", "RNS", "M.I.R.C.O.", "IBRIWOLF", "HORIZON", "IEA-UNIPI-LIPU"}
    out = []
    for i, x in enumerate(t.lower().split()):
        if x.upper() in keep:
            out.append(x.upper())
        elif x == "alexandro":
            out.append("Alexandro")
        elif i == 0:
            out.append(x[:1].upper() + x[1:])
        else:
            out.append(x)
    s = " ".join(out)
    for n in ("italia", "croazia", "croatia", "duna feniglia", "dunafeniglia", "punta faro", "gran sasso", "kentish", "europe", "lazio",
              "gargano", "taburno-camposauro", "circeo", "marsican", "marsicano", "sibillini", "veio", "riserva naturale statale", "natural state reserve"):
        s = re.sub(rf"\b{n}\b", lambda m: m.group(0).title(), s)
    return s


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
            menus.append(dict(menu=cats.get("nav_menu"), obj=meta.get("_menu_item_object_id")))
        elif pt in ("page", "post") and g("wp:status") == "publish" and g("wp:post_name") not in SKIP:
            lang = {"Italiano": "it", "English": "en", "Hrvatski": "hr"}.get(cats.get("language"), "it")
            t = html.unescape(i.find("title").text or "")
            t = FIX_TITLES.get(t, t)
            if t.endswith("_en"):
                t = t[:-3]
            items.append(dict(id=pid, type=pt, slug=g("wp:post_name"), title=t, date=g("wp:post_date"),
                              body=g("content:encoded") or "", lang=lang,
                              path=urllib.parse.unquote(i.find("link").text.replace(SITE, "")) or "/",
                              thumb=meta.get("_thumbnail_id"), group=cats.get("post_translations")))
    return att, items, menus


# ---------------------------------------------------------------- immagini
LOCAL, MISSING = {}, set()


def index_local():
    for d, _, fs in os.walk(os.path.join(ROOT, "wp-content", "uploads")):
        for f in fs:
            rel_ = "/" + os.path.relpath(os.path.join(d, f), ROOT).replace(os.sep, "/")
            LOCAL[rel_] = rel_
            LOCAL.setdefault("stem:" + re.sub(r"(-\d+x\d+|-scaled)(?=\.\w+$)", "", rel_), rel_)


def img(path):
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


PATHS, BY_SLUG = set(), {}


def resolve(p):
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
    if slug in BY_SLUG:
        return BY_SLUG[slug]["path"] + frag
    return p + frag


def clean(body, att, slug="", lang="it", flat=False):
    """HTML pulito dai codici WPBakery/Gutenberg. flat=True toglie anche le colonne."""
    raws = []

    def keep_raw(m):
        try:
            raws.append(urllib.parse.unquote(base64.b64decode(m.group(1)).decode("utf-8")))
        except Exception:
            raws.append("")
        return f"@@RAW{len(raws) - 1}@@"
    b = re.sub(r"\[vc_raw_html[^\]]*\](.*?)\[/vc_raw_html\]", keep_raw, body, flags=re.S)
    b = re.sub(r"<!--.*?-->", "", b, flags=re.S)
    if "[vc_" in b:
        b = re.sub(r"\[vc_column_text[^\]]*\](.*?)\[/vc_column_text\]", lambda m: "\n" + autop(m.group(1)) + "\n", b, flags=re.S)
    elif "<p" not in b and "<h" not in b:
        b = autop(b)
    b = re.sub(r'\sstyle="(?!flex-basis)[^"]*"', "", b)
    b = re.sub(r"</?(span|font)\b[^>]*>", "", b)
    b = re.sub(r'\sclass="has-text-align-\w+"', "", b)

    def sc(m):
        tag, a = m.group(1), attrs(m.group(2) or "")
        if tag in ("vc_row", "vc_row_inner"):
            return "" if flat else '<div class="vr">'
        if tag in ("vc_column", "vc_column_inner"):
            if flat:
                return ""
            cls = {"1/4": "w25", "1/3": "w33", "1/2": "w50", "2/3": "w66", "3/4": "w75", "5/6": "w83", "1/6": "w17"}.get(a.get("width", ""), "")
            return f'<div class="vc {cls}">'
        if tag == "vc_single_image":
            u = att.get(a.get("image", ""))
            if not u or slug in NO_IMAGES:
                return ""
            i = f'<img src="{img(urllib.parse.urlparse(u).path)}" alt="">'
            if a.get("onclick") == "custom_link" and a.get("link"):
                i = f'<a href="{a["link"].strip()}">{i}</a>'
            return f"<figure>{i}</figure>"
        if tag == "vc_btn":
            return f'<p><a class="more" href="{vclink(a.get("link"))}">{html.escape(a.get("title", ""))} →</a></p>'
        if tag == "vc_custom_heading":
            return f'<h3>{html.escape(urllib.parse.unquote(a.get("text", "")))}</h3>'
        return ""
    b = re.sub(r"\[(?!/)([a-z_0-9\-]+)((?:\s[^\]]*)?)\]", sc, b)
    b = re.sub(r"\[/(vc_row|vc_row_inner|vc_column|vc_column_inner)\]", "" if flat else "</div>", b)
    b = re.sub(r"\[/?[A-Za-z_0-9\-]+[^\]]*\]", "", b)
    if slug in NO_IMAGES:
        b = re.sub(r"<figure[^>]*>.*?</figure>|<img[^>]*>", "", b, flags=re.S)
    b = re.sub(r'(src|href)="https?://(?:www\.)?ieaitaly\.org(/wp-content/uploads/[^"]+)"', lambda m: f'{m.group(1)}="{img(m.group(2))}"', b)
    b = re.sub(r'href="\s*https?://(?:www\.)?ieaitaly\.org(/[^"]*)?"', lambda m: f'href="{resolve(m.group(1) or "/")}"', b)
    b = re.sub(r'\s(target="_blank"|rel="[^"]*"|data-[\w-]+="[^"]*"|loading="lazy"|decoding="\w+"|width="\d+"|height="\d+"|srcset="[^"]*"|sizes="[^"]*")', "", b)
    b = b.replace("<img ", '<img loading="lazy" ')
    b = re.sub(r"<(p|h\d|strong)[^>]*>(\s|&nbsp;|<br\s*/?>)*</\1>", "", b)
    b = re.sub(r"<p>(\s|<br>)*", "<p>", b)
    b = re.sub(r"(<br>\s*)+</p>", "</p>", b)
    b = re.sub(r"<(h\d)>\s*<strong>(.*?)</strong>\s*</\1>", r"<\1>\2</\1>", b, flags=re.S)
    b = re.sub(r'<div class="vr">\s*(<div class="vc ?\w*">\s*</div>\s*)*</div>', "", b)
    b = re.sub(r"<table", '<div class="tw"><table', b).replace("</table>", "</table></div>")
    b = re.sub(r"<h([1-6])>([^<]+)</h\1>", lambda m: f"<h{m.group(1)}>{sentence(m.group(2).strip())}</h{m.group(1)}>", b)
    b = re.sub(r"\n{3,}", "\n\n", b).strip()
    for n, r in enumerate(raws):
        b = b.replace(f"@@RAW{n}@@", r)
    return b


def text(h):
    h = re.sub(r"</?(strong|b|em|i|a|span|u)\b[^>]*>", "", h)
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", h))).strip()


def excerpt(body, n=150):
    t = text(re.sub(r"<!--.*?-->", "", body, flags=re.S))
    return t if len(t) <= n else t[:n].rsplit(" ", 1)[0] + "…"


# ---------------------------------------------------------------- dati: persone, progetti
def board(c):
    out = []
    for m in re.finditer(r'<div class="vc w25">\s*<figure><img[^>]*src="([^"]+)"[^>]*></figure>\s*<p><strong>(.*?)</strong>\s*(?:<br>)?\s*(.*?)</p>\s*</div>'
                         r'<div class="vc w75">(.*?)</div></div>', c, re.S):
        out.append(dict(img=m.group(1), name=text(m.group(2)), role=text(m.group(3)), bio=m.group(4).strip()))
    return out


def people_list(c, marker_re):
    m = re.search(marker_re + r"(.*?)</div>", c, re.S)
    if not m:
        return []
    out = []
    for p in re.findall(r"<p>(.*?)</p>", m.group(1), re.S):
        a = re.search(r'<a href="([^"]+)">(.*?)</a>', p)
        name = text(a.group(2) if a else p)
        extra = text(p.replace(a.group(0), "")) if a else ""
        if not a and ":" in name:
            extra, name = name.split(":", 1)[0].strip(), name.split(":", 1)[1].strip()
            extra = f"({extra.lower()})"
        elif not a and "(" in name:
            name, extra = name.split("(", 1)[0].strip(), "(" + name.split("(", 1)[1]
        name = " ".join(w.title() for w in name.split()).replace("Bo'", "Bo’").replace("Prof.Ssa", "Prof.ssa")
        out.append(dict(name=name, link=a.group(1) if a else "", extra=extra.strip()))
    return out


def projects_rows(c):
    rows = []
    for li, meta in re.findall(r"<li>(.*?)</li>.*?</ul>\s*(?:<br>\s*)?<p>(.*?)</p>", c, re.S):
        link = re.search(r'<a href="([^"]+)"', li)
        title = re.sub(r"\s+([.,])", r"\1", text(li)).strip()
        m = re.sub(r"<br\s*/?>", "\n", meta)

        def field(*names):
            for n in names:
                r = re.search(n + r"\s*(?:</em>)?\s*:?\s*(?:</em>)?(?:<em>\s*</em>)?\s*:?(.*?)(?=\n|<em>|$)", m, re.S | re.I)
                if r:
                    return text(r.group(1)).strip(" .:")
            return ""
        years = re.sub(r"\s*[–-]\s*", "–", field("Durata", "Duration"))
        doc = re.search(r'(?:Documentazione|Documentation)[^<]*(?:</em>)?[^<]*<a href="([^"]+)">(.*?)</a>', meta, re.S)
        role = ""
        rm = re.search(r"-\s*(Beneficiario [a-z]+|[A-Z][a-z]+ beneficiary)\.?$", title)
        if rm:
            role, title = rm.group(1), title[:rm.start()].strip()
        title = re.sub(r"^Progetto\s+|^Project\s+", "", title).rstrip(".")
        title = title[:1].upper() + title[1:]
        rows.append(dict(title=title, link=link.group(1) if link else "", funds=field("Fondi", "Funds"), years=years, role=role,
                         doc=(doc.group(1), text(doc.group(2))) if doc else None))
    return rows


def ongoing(y):
    e = re.findall(r"\d{4}", y)
    return bool(e) and int(e[-1]) >= date.today().year


def is_eu(r):
    return bool(re.search(r"\b(EU|UE|European|Europea|LIFE|Horizon|Erasmus|Biodiversa)\b", r["title"] + " " + r["funds"]))


# ---------------------------------------------------------------- disegni
WOLF = ("M20 17 C30 12 50 13 64 12 C68 11 72 8 75 5 L78 -1 L80 4 L83 0 L84 6 C88 8 93 10 98 13 C98 15 96 16 93 16 L87 17 "
        "C84 19 81 21 79 24 C76 27 74 30 74 33 L76 55 L72 55 L69 36 L66 37 L64 55 L60 55 L60 36 C54 35 44 35 36 34 L33 42 L36 55 "
        "L32 55 L28 43 L27 35 L23 44 L24 55 L20 55 L19 42 C18 36 18 30 19 26 C15 30 11 36 8 44 C6 47 3 46 4 42 C6 34 11 24 20 17Z")
EYE = (85, 7)


def camtrap_svg(lang):
    """Fotogramma notturno di fototrappola: bosco all'infrarosso, lupo che attraversa, dati sovrimpressi."""
    trunks = "".join(f'<rect x="{x}" y="0" width="{w}" height="560" fill="url(#trunk)" opacity="{o}"/>'
                     for x, w, o in [(60, 34, .55), (170, 22, .35), (318, 46, .7), (520, 18, .3), (1010, 26, .4), (1180, 52, .75), (1330, 20, .3), (1450, 38, .6)])
    grass = "".join(f'<path d="M{x} 600 q{d} -{h} {d * 2} -{h + 6}" stroke="#a9b5a6" stroke-opacity=".45" stroke-width="2" fill="none"/>'
                    for x, d, h in [(40, 4, 26), (120, -3, 18), (260, 5, 30), (420, 3, 22), (610, -4, 20), (880, 4, 24), (1090, -3, 28), (1260, 5, 20), (1420, 3, 26), (1540, -4, 18)])
    stamp = {"it": "14-02-2026  02:17:43", "en": "02-14-2026  02:17:43", "hr": "14.02.2026.  02:17:43"}[lang]
    lab = "Fotogramma notturno di una fototrappola: un lupo attraversa il bosco" if lang == "it" else "Night camera-trap frame: a wolf crossing the forest"
    return f'''<svg class="cam" viewBox="0 0 1600 680" preserveAspectRatio="xMidYMid slice" role="img" aria-label="{lab}">
<defs>
 <radialGradient id="ir" cx="62%" cy="58%" r="70%"><stop offset="0" stop-color="#8f9c8c"/><stop offset=".45" stop-color="#4b5a4d"/><stop offset="1" stop-color="#121a15"/></radialGradient>
 <linearGradient id="trunk" x1="0" x2="1"><stop offset="0" stop-color="#0c120e"/><stop offset=".5" stop-color="#2b352d"/><stop offset="1" stop-color="#0c120e"/></linearGradient>
 <linearGradient id="ground" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#6d7a6a"/><stop offset="1" stop-color="#1a231c"/></linearGradient>
 <filter id="grain"><feTurbulence type="fractalNoise" baseFrequency=".9" numOctaves="2" stitchTiles="stitch"/><feColorMatrix values="0 0 0 0 .8  0 0 0 0 .85  0 0 0 0 .8  0 0 0 .22 0"/></filter>
 <radialGradient id="vig" cx="50%" cy="50%" r="75%"><stop offset=".6" stop-color="#000" stop-opacity="0"/><stop offset="1" stop-color="#000" stop-opacity=".65"/></radialGradient>
</defs>
<rect width="1600" height="680" fill="url(#ir)"/>
<path d="M0 300 C300 270 600 320 900 290 C1200 262 1400 300 1600 280 L1600 0 L0 0Z" fill="#0f1712" opacity=".55"/>
{trunks}
<path d="M0 520 C320 495 700 505 1000 515 C1250 524 1450 510 1600 505 L1600 680 L0 680Z" fill="url(#ground)"/>
<ellipse cx="1000" cy="566" rx="150" ry="14" fill="#0b120d" opacity=".55"/>
<g transform="translate(850 418) scale(3)"><path d="{WOLF}" fill="#1a221c"/><path d="{WOLF}" fill="none" stroke="#c9d3c4" stroke-opacity=".35" stroke-width=".6"/>
 <circle cx="{EYE[0]}" cy="{EYE[1]}" r="1.3" fill="#f4fff2"/><circle cx="{EYE[0]}" cy="{EYE[1]}" r="3" fill="#f4fff2" opacity=".25"/></g>
{grass}
<rect width="1600" height="680" filter="url(#grain)"/>
<rect width="1600" height="680" fill="url(#vig)"/>

<g stroke="#e9f0e6" stroke-width="3" fill="none" opacity=".8"><path d="M826 396 h-26 v26 M1172 396 h26 v26 M826 596 h-26 v-26 M1172 596 h26 v-26"/></g>
</svg>'''


ICONS = {
    "via": '<path d="M8 40h32M12 40V22l8-6 8 6v18M30 40V16l6-4 6 4v24"/><path d="M18 28h4M34 24h4M34 32h4"/>',
    "fauna": f'<g transform="translate(4 13) scale(.4)" stroke-width="5"><path d="{WOLF}"/></g>',
    "aree": '<path d="M5 40l12-20 7 10 6-8 13 18z"/><circle cx="34" cy="12" r="4"/>',
    "gis": '<path d="M6 12l12-4 12 4 12-4v28l-12 4-12-4-12 4z"/><path d="M18 8v28M30 12v28"/>',
    "edu": '<path d="M4 18l20-8 20 8-20 8z"/><path d="M12 22v10c7 5 17 5 24 0V22M44 18v12"/>',
    "inv": '<path d="M12 6h18l8 8v28H12z"/><path d="M30 6v8h8M18 22h14M18 29h14M18 36h9"/>',
}
FIELDS = {"it": [("via", "Valutazione dell’impatto ambientale"), ("fauna", "Conservazione, ecologia e gestione della fauna e degli habitat"),
                 ("aree", "Pianificazione e gestione di aree protette"), ("gis", "GIS e telerilevamento"),
                 ("edu", "Educazione ambientale"), ("inv", "Inventario, studio e gestione delle risorse naturali")],
          "en": [("via", "Environmental impact assessment"), ("fauna", "Conservation, ecology and management of wildlife and habitats"),
                 ("aree", "Planning and management of protected areas"), ("gis", "GIS and remote sensing"),
                 ("edu", "Environmental education"), ("inv", "Inventory, study and management of natural resources")]}


def icon(k):
    return f'<svg class="ico" viewBox="0 0 48 48" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linejoin="round" stroke-linecap="round" aria-hidden="true">{ICONS[k]}</svg>'


# ---------------------------------------------------------------- impaginazione comune
T = {
 "it": dict(name="Istituto di Ecologia Applicata", menu="Menu", skip="Vai al contenuto", since="Associazione senza fini di lucro, Roma, dal 1987",
            nav=[("home", "Home"), ("chi-siamo", "Chi siamo"), ("mission", "Mission"), ("progetti", "Progetti"), ("life-alexandro", "LIFE Alexandro"), ("contatti", "Contatti")],
            privacy="Privacy e cookie", photo="Foto", all_news="Tutte le notizie", news="Notizie", back="Tutte le notizie",
            office="Sede", contacts="Contatti"),
 "en": dict(name="Institute of Applied Ecology", menu="Menu", skip="Skip to content", since="Not-for-profit organisation, Rome, since 1987",
            nav=[("iea", "Home"), ("about-2", "About us"), ("our-mission", "Mission"), ("projects", "Projects"), ("life-alexandro-2", "LIFE Alexandro"), ("contact", "Contacts")],
            privacy="Privacy and cookies", photo="Photo", all_news="All news", news="News", back="All news",
            office="Office", contacts="Contacts"),
 "hr": dict(name="Istituto di Ecologia Applicata", menu="Izbornik", skip="Preskoči na sadržaj", since="Neprofitna udruga, Rim, od 1987.",
            nav=[("life-alexandro-4", "LIFE Alexandro"), ("projekt", "Projekt"), ("novosti", "Novosti"), ("kontaktu", "Kontakt")],
            privacy="Privatnost i kolačići", photo="Foto", all_news="Sve novosti", news="Novosti", back="Sve novosti",
            office="Sjedište", contacts="Kontakt"),
}


def rel(target, here):
    if not target.startswith("/") or target.startswith("//"):
        return target
    depth = len([x for x in here.strip("/").split("/") if x])
    return ("../" * depth or "./") + target.lstrip("/")


def relativize(doc, here):
    return re.sub(r'(href|src)="(/(?!/)[^"]*)"', lambda m: f'{m.group(1)}="{rel(m.group(2), here)}"', doc)


def shell(p, main, ctx, section="", theme=""):
    lang, here = p["lang"], p["path"]
    t = T[lang]
    trans = ctx["trans"].get(p["slug"], {})
    langs = "".join(f'<a href="{trans.get(l, HOME[l])}" hreflang="{l}" lang="{l}"{" aria-current=\"true\"" if l == lang else ""}>{l.upper()}</a>'
                    for l in ("it", "en", "hr"))
    alts = "".join(f'<link rel="alternate" hreflang="{l}" href="{SITE}{u}">' for l, u in trans.items())
    nav = "".join(f'<li><a href="{BY_SLUG[s]["path"]}"{" aria-current=\"page\"" if s == section else ""}{" class=\"axl\"" if "alexandro" in s else ""}>{lbl}</a></li>'
                  for s, lbl in t["nav"])
    desc = text(re.sub(r"<style.*?</style>|<script.*?</script>|<svg.*?</svg>|<nav.*?</nav>", "", main, flags=re.S))
    desc = html.escape(desc[:155].rsplit(" ", 1)[0] + "…" if len(desc) > 155 else desc)
    ttl = html.escape(p["title"])
    head_t = f"IEA – {t['name']}" if here == HOME.get(lang) else f"{ttl} – IEA"
    if lang == "hr":
        head_t = f"{ttl} – LIFE Alexandro"
    doc = f'''<!DOCTYPE html>
<html lang="{lang}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{head_t}</title>
<meta name="description" content="{desc}">
<link rel="canonical" href="{SITE}{here}">{alts}
<meta property="og:title" content="{ttl}"><meta property="og:description" content="{desc}"><meta property="og:url" content="{SITE}{here}"><meta property="og:type" content="website">
<link rel="icon" href="/assets/favicon.png">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Archivo+Narrow:wght@500;600;700&family=Archivo:ital,wght@0,400;0,500;0,600;1,400&family=Share+Tech+Mono&display=swap" rel="stylesheet">
<link rel="stylesheet" href="/assets/site.css">
</head>
<body class="{theme}">
<a class="skip" href="#main">{t["skip"]}</a>
<header class="top"><div class="bar">
 <a class="brand" href="{HOME[lang]}"><img src="/wp-content/uploads/2019/10/cropped-images-1-5.png" alt="IEA – Istituto di Ecologia Applicata" width="618" height="139"></a>
 <button class="burger" aria-expanded="false" aria-controls="menu">{t["menu"]}</button>
 <nav class="menu" id="menu" aria-label="Menu"><ul class="nav">{nav}</ul><div class="lang" role="group" aria-label="Lingua">{langs}</div></nav>
</div></header>
<main id="main">
{main}
</main>
<footer class="foot"><div class="wrap">
 <div class="fgrid">
  <div><span class="flogo"><img src="/wp-content/uploads/2019/10/cropped-images-1-5.png" alt="IEA" width="618" height="139"></span><p>{t["since"]}</p></div>
  <div><h3>{t["office"]}</h3><p>Via C. Colombo 456<br>00145 Roma</p></div>
  <div><h3>{t["contacts"]}</h3><p><a href="mailto:iea@ieaitaly.org">iea@ieaitaly.org</a><br>+39 06 4403315<br>PEC istitutoecologiaapplicata@legalmail.it</p></div>
  <div><h3>LIFE</h3><p>{ctx["foot"][lang]}</p></div>
 </div>
 <p class="legal">© {date.today().year} Istituto di Ecologia Applicata · <a href="https://www.iubenda.com/privacy-policy/35549680">{t["privacy"]}</a> · {t["photo"]}: <a href="https://www.paolafazzi.com">Paola Fazzi</a></p>
</div></footer>
<script src="/assets/site.js"></script>
</body>
</html>
'''
    return relativize(doc, here)


def write(path, doc):
    f = os.path.join(ROOT, "index.html") if path == "/" else os.path.join(ROOT, path.strip("/"), "index.html")
    os.makedirs(os.path.dirname(f), exist_ok=True)
    with open(f, "w", encoding="utf-8") as fh:
        fh.write(doc)


def pagehead(title, kicker="", lead="", pic="", crumbs=""):
    k = f'<p class="kick">{kicker}</p>' if kicker else ""
    l = f'<p class="lead">{lead}</p>' if lead else ""
    f = f'<figure class="phpic"><img src="{pic}" alt=""></figure>' if pic else ""
    return f'<section class="phead"><div class="wrap phg{" haspic" if pic else ""}"><div>{crumbs}{k}<h1>{html.escape(title)}</h1>{l}</div>{f}</div></section>'


# ---------------------------------------------------------------- blocchi riutilizzabili
def Lf(lang):
    return (lambda a, b: a) if lang == "it" else (lambda a, b: b)


def registry(rows, lang):
    L = Lf(lang)
    lis = []
    for r in rows:
        t = html.escape(r["title"])
        if r["link"]:
            t = f'<a href="{r["link"]}">{t}</a>'
        on = ongoing(r["years"])
        extra = []
        if r["role"]:
            extra.append(html.escape(r["role"]))
        if r["doc"] and not re.search(r"contatt|contact", r["doc"][1], re.I):
            extra.append(f'<a href="{r["doc"][0]}">{L("sito del progetto", "project website")} ↗</a>')
        live = f'<span class="live">{L("in corso", "ongoing")}</span>' if on else ""
        lis.append(f'<li data-k="{"on " if on else ""}{"ue" if is_eu(r) else ""}"><span class="yr">{html.escape(r["years"])}</span>'
                   f'<div><p class="rt">{t}{live}</p><p class="rf">{html.escape(r["funds"])}{" · " + " · ".join(extra) if extra else ""}</p></div></li>')
    return (f'<div class="reg"><div class="tools"><input id="pq" type="search" placeholder="{L("Cerca per titolo, ente, parco…", "Search by title, funder, park…")}" aria-label="{L("Cerca nei progetti", "Search projects")}">'
            f'<div class="chips"><button class="chip" aria-pressed="true" data-f="">{L("Tutti", "All")}</button><button class="chip" aria-pressed="false" data-f="on">{L("In corso", "Ongoing")}</button>'
            f'<button class="chip" aria-pressed="false" data-f="ue">{L("Europei", "European")}</button></div></div>'
            f'<p class="count" id="pc" data-of="{L("progetti su", "projects of")}"></p><ol class="plist" id="pl">{"".join(lis)}</ol>'
            f'<p class="count" id="pn" hidden>{L("Nessun progetto corrisponde alla ricerca.", "No project matches your search.")}</p></div>')


def news_cards(posts, lang, att):
    out = []
    for p in posts:
        ph = att.get(p["thumb"] or "")
        ph = urllib.parse.urlparse(ph).path if ph else None
        if not ph:
            m = re.search(r'<img[^>]+src="https?://(?:www\.)?ieaitaly\.org(/wp-content/uploads/[^"]+)"', p["body"])
            ph = m.group(1) if m else None
        pic = f'<img src="{img(ph)}" alt="" loading="lazy">' if ph else ""
        out.append(f'<a class="ncard" href="{p["path"]}"><div class="nph">{pic}</div><div class="nin"><time datetime="{p["date"][:10]}">{fdate(p["date"], lang)}</time>'
                   f'<h3>{html.escape(sentence(p["title"]))}</h3><p>{html.escape(excerpt(p["body"], 130))}</p></div></a>')
    return f'<div class="ngrid">{"".join(out)}</div>'


def person_cards(b, link):
    return "".join(f'<a href="{link}" class="pcard"><img src="{x["img"]}" alt="" loading="lazy"><p><b>{html.escape(x["name"])}</b>{html.escape(x["role"])}</p></a>' for x in b)


def ax_logos():
    return ('<div class="axlogos"><img src="/wp-content/uploads/2026/04/EN-V-Co-funded-by-the-EU_POS.png" alt="Co-funded by the European Union – LIFE">'
            '<img src="/wp-content/uploads/2026/04/Natura-2000-logo-in-JPG-format-2.jpeg" alt="Natura 2000"></div>')


# ---------------------------------------------------------------- pagine IEA
def home(lang, ctx):
    d = ctx["data"][lang]
    L = Lf(lang)
    s = lambda k: BY_SLUG[k]["path"]
    rows = ctx["rows"][lang]
    n_on = sum(1 for r in rows if ongoing(r["years"]))
    fields = "".join(f'<div class="field">{icon(k)}<p>{v}</p></div>' for k, v in FIELDS[lang])
    ww_svg = (f'<svg viewBox="0 0 320 130" preserveAspectRatio="xMidYMid slice" aria-hidden="true"><rect width="320" height="130" fill="#26332b"/>'
              f'<path d="M0 100 C80 88 170 96 320 86 V130 H0Z" fill="#3b4a40"/><g transform="translate(108 44) scale(1.05)"><path d="{WOLF}" fill="#0b120e"/>'
              f'<circle cx="{EYE[0]}" cy="{EYE[1]}" r="1.4" fill="#f4fff2"/></g></svg>')
    return f'''<section class="hero">{camtrap_svg(lang)}<div class="hud" aria-hidden="true"><span class="ht">IEA · CAM 03 <i></i></span><span class="hb">☾ 3°C&nbsp;&nbsp;{ {"it": "14-02-2026", "en": "02-14-2026"}[lang] }&nbsp;&nbsp;02:17:43</span></div>
<div class="htxt"><div class="wrap"><div class="hpanel">
 <p class="kick">{L("Istituto di Ecologia Applicata · dal 1987", "Institute of Applied Ecology · since 1987")}</p>
 <h1>{L("Per un ambiente migliore", "For a better environment")}</h1>
 <p>{L("Studiamo la fauna selvatica e i suoi conflitti con le attività umane, e affianchiamo enti pubblici e privati, in Italia e all’estero, nella gestione delle risorse naturali.",
       "We study wildlife and its conflicts with human activities, and support public and private bodies, in Italy and abroad, in managing natural resources.")}</p>
 <div class="row"><a class="btn" href="{s(L("progetti", "projects"))}">{L("Registro dei progetti", "Project register")}</a><a class="btn ghost" href="{s(L("chi-siamo", "about-2"))}">{L("Chi siamo", "About us")}</a></div>
</div></div></div></section>
<section class="nums"><div class="wrap ngr">
 <div><b>1987</b><span>{L("anno di fondazione", "year founded")}</span></div>
 <div><b>{len(rows)}</b><span>{L("progetti nel registro", "projects in the register")}</span></div>
 <div><b>{n_on}</b><span>{L("progetti in corso", "ongoing projects")}</span></div>
 <div><b>51</b><span>{L("siti Natura 2000 in LIFE Alexandro", "Natura 2000 sites in LIFE Alexandro")}</span></div>
</div></section>
<section class="band"><div class="wrap split">
 <div><p class="kick">{L("Chi siamo", "About us")}</p><h2>{L("Ricerca sul campo per chi gestisce il territorio", "Field research for those who manage the land")}</h2>
 <div class="prose">{d["intro"]}</div><p><a class="more" href="{s(L("chi-siamo", "about-2"))}">{L("L’Istituto, i soci e il comitato etico", "The Institute, members and ethics committee")} →</a></p></div>
 <div><p class="kick">{L("Consiglio direttivo", "Board")}</p><div class="pcards">{person_cards(d["board"], s(L("chi-siamo", "about-2")))}</div></div>
</div></section>
<section class="band dark"><div class="wrap">
 <p class="kick">Mission</p><p class="quote">{d["quote"]}</p>
 <div class="fgrid6">{fields}</div>
 <p><a class="more" href="{s(L("mission", "our-mission"))}">{L("Campi di attività e piano per la parità di genere", "Fields of activity and gender equality plan")} →</a></p>
</div></section>
<section class="band"><div class="wrap">
 <p class="kick">{L("In primo piano", "In focus")}</p><h2>{L("I progetti LIFE", "Our LIFE projects")}</h2>
 <div class="lgrid">
  <a class="lcard axc" href="{s(L("life-alexandro", "life-alexandro-2"))}"><div class="lpic"><img src="/wp-content/uploads/2026/04/1_Life-Alexandro_LOGO-DEF-4-1024x421.png" alt="LIFE Alexandro"></div>
   <div class="lin"><p class="meta">2026–2031 · {L("coordinatore IEA", "coordinated by IEA")}</p><h3>{L("Azioni concrete per la conservazione del fratino", "Concrete actions for the Kentish plover")}</h3>
   <p>{L("51 siti Natura 2000 in 10 regioni italiane e in Croazia: protezione dei nidi, ripristino delle dune, accordi con chi vive e usa la spiaggia.", "51 Natura 2000 sites in 10 Italian regions and Croatia: nest protection, dune restoration, agreements with beach users.")}</p></div></a>
  <a class="lcard wwc" href="{s(L("life-wild-wolf-it", "life-wild-wolf-en"))}"><div class="lpic">{ww_svg}</div>
   <div class="lin"><p class="meta">2023–2027 · {L("8 paesi, 18 partner", "8 countries, 18 partners")}</p><h3>LIFE Wild Wolf</h3><p>{L("Azioni concrete per scoraggiare la presenza del lupo nelle aree abitate in Europa.", "Concrete actions to deter wolves from human-dominated areas in Europe.")}</p></div></a>
  <a class="lcard" href="{s(L("life-medwolf", "medwolf"))}"><div class="lin"><p class="meta">2012–2017 · {L("coordinatore IEA", "coordinated by IEA")}</p><h3>LIFE MedWolf</h3><p>{L("Buone pratiche per la conservazione del lupo negli ecosistemi mediterranei, in Italia e Portogallo.", "Best practice for wolf conservation in Mediterranean ecosystems, in Italy and Portugal.")}</p></div></a>
  <a class="lcard" href="{s(L("piattaforma", "stakeholder-platforms"))}"><div class="lin"><p class="meta">{L("dal 2017 · Commissione Europea", "since 2017 · European Commission")}</p><h3>{L("Piattaforme locali sui grandi carnivori", "Local platforms on large carnivores")}</h3><p>{L("Spazi di dialogo tra i gruppi d’interesse coinvolti dalla presenza dei grandi carnivori.", "Spaces of dialogue among the parties concerned by the presence of large carnivores.")}</p></div></a>
 </div></div></section>
<section class="band paper"><div class="wrap">
 <p class="kick">{L("Registro", "Register")}</p><h2>{L("Tutti i progetti, dal più recente", "All projects, most recent first")}</h2>
 {registry(rows, lang)}</div></section>
<section class="band"><div class="wrap">
 <div class="hrow"><div><p class="kick">LIFE Alexandro</p><h2>{L("Dal campo", "From the field")}</h2></div><a class="more" href="{s(L("news", "news-2"))}">{T[lang]["all_news"]} →</a></div>
 {news_cards(ctx["posts"][lang][:3], lang, ctx["att"])}</div></section>'''


def plist(xs):
    out = []
    for x in xs:
        n = f'<a href="{x["link"]}">{html.escape(x["name"])}</a>' if x["link"] else html.escape(x["name"])
        e = f' <span>{html.escape(x["extra"])}</span>' if x["extra"] else ""
        out.append(f"<li>{n}{e}</li>")
    return "".join(out)


def chi_siamo(p, ctx):
    lang = p["lang"]
    d = ctx["data"][lang]
    L = Lf(lang)
    bios = "".join(f'<article class="bio"><img src="{x["img"]}" alt="" loading="lazy"><div><h3>{html.escape(x["name"])}</h3>'
                   f'<p class="meta">{html.escape(x["role"])}</p>{x["bio"]}</div></article>' for x in d["board"])
    lead = L("Associazione senza fini di lucro fondata nel 1987, nata dalla collaborazione con la Sapienza Università di Roma.",
             "A not-for-profit association founded in 1987, rooted in its collaboration with Sapienza University of Rome.")
    facts = (f'<aside class="facts"><dl><dt>{L("Fondazione", "Founded")}</dt><dd>1987, Roma</dd><dt>{L("Forma giuridica", "Legal form")}</dt><dd>{L("Associazione senza fini di lucro", "Not-for-profit association")}</dd>'
             f'<dt>{L("Università di riferimento", "University partner")}</dt><dd>Sapienza Università di Roma</dd>'
             f'<dt>{L("Sede", "Office")}</dt><dd>Via C. Colombo 456, Roma</dd></dl></aside>')
    return (pagehead(p["title"], L("L’Istituto", "The Institute"), lead)
            + f'<section class="band"><div class="wrap split"><div class="prose">{d["intro_full"]}</div>{facts}</div></section>'
            + f'<section class="band paper"><div class="wrap"><p class="kick">{L("Consiglio direttivo", "Board")}</p><div class="bios">{bios}</div></div></section>'
            + f'<section class="band"><div class="wrap two"><div><h2>{L("Soci", "Members")}</h2><ul class="names">{plist(d["members"])}</ul></div>'
              f'<div><h2>{L("Comitato etico di progetto", "Project ethics committee")}</h2><ul class="names">{plist(d["cep"])}</ul></div></div></section>')


def mission(p, ctx):
    lang = p["lang"]
    d = ctx["data"][lang]
    L = Lf(lang)
    s = lambda k: BY_SLUG[k]["path"]
    main_p = [(L("life-medwolf", "medwolf"), "LIFE MedWolf"), (L("piattaforma", "stakeholder-platforms"), L("Piattaforme sui grandi carnivori", "Large carnivore platforms")),
              (L("life-wild-wolf-it", "life-wild-wolf-en"), "LIFE Wild Wolf"), (L("orso", "brown-bear"), L("Monitoraggio dell’orso bruno marsicano", "Marsican brown bear monitoring"))]
    fields = "".join(f'<div class="field">{icon(k)}<p>{v}</p></div>' for k, v in FIELDS[lang])
    links = "".join(f'<li><a href="{s(k)}">{v}</a></li>' for k, v in main_p)
    return (f'<section class="band dark mq"><div class="wrap"><p class="kick">Mission</p><p class="quote big">{d["quote"]}</p><div class="fgrid6">{fields}</div></div></section>'
            + f'<section class="band"><div class="wrap two"><div><h2>{L("Progetti principali", "Main projects")}</h2><ul class="links">{links}</ul>'
              f'<p><a class="more" href="{s(L("progetti", "projects"))}">{L("Il registro completo", "Full register")} →</a></p></div>'
              f'<div><h2>{L("Piano per la parità di genere", "Gender equality plan")}</h2><p>{L("L’Istituto si è dotato di un Piano per la parità di genere 2024–2027. I documenti sono liberamente consultabili.", "The Institute has adopted a Gender Equality Plan 2024–2027. The documents are freely available.")}</p>'
              f'<a class="doc" href="{d["gep"]}"><b>PDF</b><span>{L("Piano di uguaglianza di genere (GEP) 2024–2027", "Gender Equality Plan (GEP) 2024–2027")}</span></a></div></div></section>')


def progetti(p, ctx):
    lang = p["lang"]
    L = Lf(lang)
    lead = L("Dal 1987 l’Istituto lavora sui conflitti tra attività umane e fauna selvatica e sul monitoraggio e la gestione dei grandi carnivori, per la Commissione Europea, i ministeri, le regioni e i parchi.",
             "Since 1987 the Institute has worked on human–wildlife conflicts and on the monitoring and management of large carnivores for the European Commission, ministries, regions and parks.")
    return pagehead(p["title"], L("Registro", "Register"), lead) + f'<section class="band"><div class="wrap">{registry(ctx["rows"][lang], lang)}</div></section>'


def contatti(p, ctx):
    lang = p["lang"]
    L = Lf(lang)
    c = clean(p["body"], ctx["att"], p["slug"], lang, flat=True)
    av = ""
    m = re.search(r"(LIFE24-NAT-IT.*)$", c, re.S)
    if m:
        body = re.sub(r"^.*?</p>", "", m.group(1), count=1, flags=re.S)
        av = (f'<section class="band paper"><div class="wrap"><p class="kick">{L("Lavora con noi", "Work with us")}</p><h2>{L("Avvisi", "Calls")}</h2>'
              f'<details class="notice"><summary><span class="closed">{L("Chiuso", "Closed")}</span> LIFE Alexandro · {L("Monitoraggio di impollinatori ed entomofauna (azione T2.6), scadenza 15 giugno 2026", "Pollinator and insect monitoring (task T2.6), deadline 15 June 2026")}</summary>'
              f'<div class="prose">{body}</div></details></div></section>')
    cards = f'''<section class="band"><div class="wrap cgrid">
 <a class="ccard" href="mailto:iea@ieaitaly.org"><span>Email</span><b>iea@ieaitaly.org</b></a>
 <div class="ccard"><span>PEC</span><b>istitutoecologiaapplicata@legalmail.it</b></div>
 <a class="ccard" href="tel:+39064403315"><span>{L("Telefono", "Phone")}</span><b>+39 06 4403315</b></a>
 <div class="ccard"><span>{L("Sede legale", "Registered office")}</span><b>Via C. Colombo 456, 00145 Roma</b></div>
 <a class="ccard" href="https://www.facebook.com/piattaformagrandicarnivori/"><span>Facebook</span><b>{L("Piattaforma locale dei grandi carnivori", "Local large carnivore platform")}</b></a>
</div></section>'''
    return pagehead(L("Contatti", "Contacts"), L("Scrivici", "Get in touch")) + cards + av


def project_page(p, ctx, row):
    lang = p["lang"]
    L = Lf(lang)
    c = clean(p["body"], ctx["att"], p["slug"], lang, flat=True)
    pic = ""
    m = re.match(r'\s*<figure>(?:<a[^>]*>)?<img[^>]*src="([^"]+)"[^>]*>(?:</a>)?</figure>', c)
    if m:
        pic, c = m.group(1), c[m.end():]
    c = re.sub(r"^\s*<h3>[^<]*</h3>", "", c)
    crumbs = f'<p class="crumbs"><a href="{BY_SLUG[L("progetti", "projects")]["path"]}">← {L("Registro dei progetti", "Project register")}</a></p>'
    facts = ""
    if row:
        live = f'<span class="live">{L("in corso", "ongoing")}</span>' if ongoing(row["years"]) else ""
        facts = (f'<aside class="facts"><dl><dt>{L("Periodo", "Period")}</dt><dd>{html.escape(row["years"])} {live}</dd>'
                 f'<dt>{L("Finanziamento", "Funding")}</dt><dd>{html.escape(row["funds"])}</dd>'
                 + (f'<dt>{L("Ruolo IEA", "IEA role")}</dt><dd>{html.escape(row["role"])}</dd>' if row["role"] else "")
                 + (f'<dt>{L("Documentazione", "Documentation")}</dt><dd><a href="{row["doc"][0]}">{html.escape(row["doc"][1])}</a></dd>' if row["doc"] else "")
                 + "</dl></aside>")
    kick = L("Progetto", "Project") + (f" · {row['years']}" if row else "")
    return pagehead(sentence(p["title"]), kick, "", pic, crumbs) + f'<section class="band"><div class="wrap split"><div class="prose">{c}</div>{facts}</div></section>'


def generic(p, ctx):
    c = clean(p["body"], ctx["att"], p["slug"], p["lang"])
    return pagehead(sentence(p["title"])) + f'<section class="band"><div class="wrap"><div class="prose wide">{c}</div></div></section>'


# ---------------------------------------------------------------- sezione LIFE Alexandro
def ax_nav(lang, cur):
    items = []
    for k, s, lbl in zip(AX_KEYS, AX[lang], AX_LABEL[lang]):
        if s and s in BY_SLUG:
            items.append(f'<a href="{BY_SLUG[s]["path"]}"{" aria-current=\"page\"" if k == cur else ""}>{lbl}</a>')
    return f'<nav class="axnav" aria-label="LIFE Alexandro"><div class="wrap">{"".join(items)}</div></nav>'


def ax_head(lang, cur, title):
    h = f'<div class="wrap axtitle"><h1>{html.escape(title)}</h1></div>' if title else ""
    return (f'<section class="axhead"><div class="wrap axhg"><a href="{BY_SLUG[AX[lang][0]]["path"]}"><img class="axlogo" src="/wp-content/uploads/2026/04/1_Life-Alexandro_LOGO-DEF-4-1024x421.png" alt="LIFE Alexandro"></a>'
            f'{ax_logos()}</div></section>{ax_nav(lang, cur)}{h}')


AX_TXT = {
 "it": dict(sum="Il progetto europeo per migliorare lo stato di conservazione del fratino (<i>Anarhynchus alexandrinus</i>), uccello simbolo delle spiagge e oggi in forte declino. Coinvolge enti pubblici, università, associazioni e istituzioni in Italia e Croazia.",
            nums=[("51", "siti Natura 2000"), ("10", "regioni italiane, più la Croazia"), ("2400 km²", "di territorio"), ("400 km", "di costa"), ("2026–2031", "durata")],
            partners="Beneficiari", app="WebApp Alexandro", app_h="Il futuro del fratino è (anche) nelle tue mani",
            app_p="Riconosci il fratino, rispetta i suoi spazi e segnala le osservazioni direttamente dal telefono.",
            news="Dal campo", coord="coordinatore Istituto di Ecologia Applicata"),
 "en": dict(sum="The European project to improve the conservation status of the Kentish plover (<i>Anarhynchus alexandrinus</i>), a symbol of our beaches and now in sharp decline. It brings together public bodies, universities, associations and institutions in Italy and Croatia.",
            nums=[("51", "Natura 2000 sites"), ("10", "Italian regions, plus Croatia"), ("2,400 km²", "of land"), ("400 km", "of coastline"), ("2026–2031", "duration")],
            partners="Beneficiaries", app="Alexandro WebApp", app_h="The plover’s future is (also) in your hands",
            app_p="Recognise the plover, respect its space and report sightings straight from your phone.",
            news="From the field", coord="coordinated by the Institute of Applied Ecology"),
 "hr": dict(sum="Europski projekt za poboljšanje stanja očuvanosti morskog kulika (<i>Anarhynchus alexandrinus</i>), simbola naših plaža, čija je populacija u snažnom padu. Okuplja javna tijela, sveučilišta, udruge i institucije u Italiji i Hrvatskoj.",
            nums=[("51", "područje Natura 2000"), ("10", "talijanskih regija i Hrvatska"), ("2400 km²", "područja"), ("400 km", "obale"), ("2026.–2031.", "trajanje")],
            partners="Korisnici", app="", app_h="", app_p="", news="S terena", coord="koordinator Istituto di Ecologia Applicata"),
}


def ax_home(p, ctx):
    lang = p["lang"]
    a = AX_TXT[lang]
    sl = dict(zip(AX_KEYS, AX[lang]))
    cards = "".join(f'<a class="axcard" href="{BY_SLUG[sl[k]]["path"]}"><b>{lbl}</b><span aria-hidden="true">→</span></a>'
                    for k, lbl in zip(AX_KEYS[1:], AX_LABEL[lang][1:]) if sl.get(k) and sl[k] in BY_SLUG)
    nums = "".join(f"<div><b>{n}</b><span>{t}</span></div>" for n, t in a["nums"])
    app = ""
    if sl.get("webapp"):
        app = (f'<section class="band axapp"><div class="wrap split"><div><p class="kick">{a["app"]}</p><h2>{a["app_h"]}</h2>'
               f'<p>{a["app_p"]}</p><p><a class="btn" href="{BY_SLUG[sl["webapp"]]["path"]}">{a["app"]} →</a></p></div>'
               f'<img class="round" src="/wp-content/uploads/2026/03/LogoLifeAlexandro-1024x1024.jpg" alt=""></div></section>')
    return f'''<section class="axhero"><div class="wrap axhg2">
 <div><img class="axbig" src="/wp-content/uploads/2026/04/1_Life-Alexandro_LOGO-DEF-4-1024x421.png" alt="LIFE Alexandro – Long live the Kentish plover">
 <p class="axsum">{a["sum"]}</p><p class="meta">LIFE24-NAT-IT 101215107 · {a["coord"]}</p></div>
 {ax_logos()}</div></section>{ax_nav(lang, "home")}
<section class="axnums"><div class="wrap">{nums}</div></section>
<section class="band"><div class="wrap"><div class="axcards">{cards}</div></div></section>
<section class="band axpaper"><div class="wrap"><div class="hrow"><div><p class="kick">LIFE Alexandro</p><h2>{a["news"]}</h2></div><a class="more" href="{BY_SLUG[sl["news"]]["path"]}">{T[lang]["all_news"]} →</a></div>
{news_cards(ctx["posts"][lang][:3], lang, ctx["att"])}</div></section>{app}
<section class="band"><div class="wrap"><p class="kick">{a["partners"]}</p><img class="partners" src="/wp-content/uploads/2026/05/LifeAlexandro-partner_loghi_web_OK-1-1024x205.png" alt="{a["partners"]}"></div></section>'''


def ax_page(p, ctx, key):
    lang = p["lang"]
    c = clean(p["body"], ctx["att"], p["slug"], lang)
    c = re.sub(r'<figure[^>]*>\s*<img[^>]*LifeAlexandro-partner_loghi[^>]*>\s*</figure>', "", c)
    c = re.sub(r"(\s*<hr[^>]*>)+\s*$", "", c.strip())
    if key == "news":
        c = re.sub(r'<div class="wp-block-query">.*?</div>', "", c, flags=re.S)
        c = re.sub(r"<hr[^>]*>", "", c)
        body = news_cards(ctx["posts"][lang], lang, ctx["att"]) + c
        title = T[lang]["news"]
    else:
        body = f'<div class="prose ax{" wide" if key in ("gallery", "partners") else ""}">{c}</div>'
        title = AX_LABEL[lang][AX_KEYS.index(key)]
    return ax_head(lang, key, title) + f'<section class="band axbody"><div class="wrap">{body}</div></section>'


def ax_post(p, ctx):
    lang = p["lang"]
    c = clean(p["body"], ctx["att"], p["slug"], lang)
    news_p = BY_SLUG[AX[lang][3]]["path"]
    return (ax_head(lang, "news", "")
            + f'<article class="band axbody"><div class="wrap"><p class="crumbs"><a href="{news_p}">← {T[lang]["back"]}</a></p>'
              f'<p class="meta">{fdate(p["date"], lang)}</p><h1 class="ptitle">{html.escape(sentence(p["title"]))}</h1><div class="prose ax">{c}</div></div></article>')


def ax_webapp(p, ctx):
    return ax_nav(p["lang"], "webapp") + f'<div class="fullbleed">{clean(p["body"], ctx["att"], p["slug"], p["lang"])}</div>'


# ---------------------------------------------------------------- main
def main(xml):
    index_local()
    att, items, menus = load(xml)
    by_id = {p["id"]: p for p in items}
    BY_SLUG.update({p["slug"]: p for p in items})
    PATHS.update(p["path"] for p in items)
    for m in menus:
        if m["obj"] in by_id and m["menu"] in MENUS:
            by_id[m["obj"]]["lang"] = MENUS[m["menu"]]
    trans, groups = {}, {}
    for p in items:
        if p["group"]:
            groups.setdefault(p["group"], {})[p["lang"]] = p["path"]
    for p in items:
        if p["group"]:
            trans[p["slug"]] = groups[p["group"]]
    for tup in PAIRS:
        d = {l: BY_SLUG[s]["path"] for l, s in zip(("it", "en", "hr"), tup) if s and s in BY_SLUG}
        for s in tup:
            if s:
                trans[s] = d
    trans["home"] = trans["iea"] = dict(HOME)
    posts = {l: sorted([p for p in items if p["type"] == "post" and p["lang"] == l], key=lambda p: p["date"], reverse=True) for l in ("it", "en", "hr")}

    data = {}
    for lang, cs, ms in (("it", "chi-siamo", "mission"), ("en", "about-2", "our-mission")):
        c = clean(BY_SLUG[cs]["body"], att)
        paras = re.findall(r"<p>.*?</p>", c.split("<h3>")[0], re.S)
        mc = clean(BY_SLUG[ms]["body"], att)
        gep = re.search(r'href="([^"]+\.pdf)"', mc)
        data[lang] = dict(intro="".join(paras[:2]), intro_full="".join(paras), board=board(c),
                          members=people_list(c, r"(?:Gli altri soci|other members)[^<]*</p>"),
                          cep=people_list(c, r"(?:Comitato Etico|Ethics Committee|ethics committee)[^<]*</p>"),
                          quote=text(re.search(r"<blockquote>(.*?)</blockquote>", mc, re.S).group(1)).rstrip(".") + ".",
                          gep=gep.group(1) if gep else "")
    rows = {"it": projects_rows(clean(BY_SLUG["progetti"]["body"], att)), "en": projects_rows(clean(BY_SLUG["projects"]["body"], att))}
    row_by_path = {r["link"]: r for l in rows for r in rows[l] if r["link"]}
    foot = {"it": '<a href="/life-alexandro/">LIFE Alexandro</a><br><a href="/life-wild-wolf-it/">LIFE Wild Wolf</a><br><a href="/progetti/life-medwolf/">LIFE MedWolf</a>',
            "en": '<a href="/en/life-alexandro-2/">LIFE Alexandro</a><br><a href="/en/life-wild-wolf-en/">LIFE Wild Wolf</a><br><a href="/en/projects/medwolf/">LIFE MedWolf</a>',
            "hr": '<a href="/hr/life-alexandro-4/">LIFE Alexandro</a>'}
    ctx = dict(trans=trans, att=att, posts=posts, data=data, rows=rows, foot=foot)
    ax_keys = {s: k for l in AX for k, s in zip(AX_KEYS, AX[l]) if s}
    proj_slugs = {"life-wild-wolf-it", "life-wild-wolf-en", "taburno", "taburno_en", "horizon_it", "brown-bear", "damage_lazio", "circeo_en", "circeo_en-2",
                  "gran-sasso_en", "ibriwolf-en", "sibillini_en", "mirco_en", "gargano_en", "veio_en", "feniglia_en"}

    sitemap = []
    for p in items:
        lang, sl = p["lang"], p["slug"]
        theme, section = "", ""
        if sl in ("home", "iea"):
            main_h, section = home(lang, ctx), sl
        elif sl in ("chi-siamo", "about-2"):
            main_h, section = chi_siamo(p, ctx), sl
        elif sl in ("mission", "our-mission"):
            main_h, section = mission(p, ctx), sl
        elif sl in ("progetti", "projects"):
            main_h, section = progetti(p, ctx), sl
        elif sl in ("contatti", "contact"):
            main_h, section = contatti(p, ctx), sl
        elif sl in ax_keys:
            k = ax_keys[sl]
            theme, section = "axt", AX[lang][0]
            main_h = ax_home(p, ctx) if k == "home" else ax_webapp(p, ctx) if k == "webapp" else ax_page(p, ctx, k)
        elif sl == "life-alexandro-3":
            theme, section, main_h = "axt", "life-alexandro", ax_home(p, ctx)
        elif p["type"] == "post":
            theme, section, main_h = "axt", AX[lang][0], ax_post(p, ctx)
        elif p["path"].startswith(("/progetti/", "/en/projects/")) or p["path"] in row_by_path or sl in proj_slugs:
            section = "progetti" if lang == "it" else "projects"
            main_h = project_page(p, ctx, row_by_path.get(p["path"]))
        else:
            main_h = generic(p, ctx)
        write(p["path"], shell(p, main_h, ctx, section, theme))
        sitemap.append(p["path"])

    for p in items:
        segs = [x for x in p["path"].strip("/").split("/") if x]
        if p["type"] == "page" and len(segs) == 2 and segs[0] == "progetti":
            short = "/" + segs[-1] + "/"
            if short not in PATHS:
                write(short, f'<!DOCTYPE html><meta charset="utf-8"><title>IEA</title><link rel="canonical" href="{SITE}{p["path"]}">'
                             f'<meta http-equiv="refresh" content="0; url={rel(p["path"], short)}"><a href="{rel(p["path"], short)}">{html.escape(p["title"])}</a>')
    p404 = dict(id="0", type="page", slug="404", title="Pagina non trovata", lang="it", path="/404/", group=None)
    doc = shell(p404, pagehead("Pagina non trovata", "404", 'La pagina che cerchi non esiste o è stata spostata. <a href="/">Torna alla home</a> · <a href="/en/iea/" lang="en">English home</a>'), ctx)
    doc = doc.replace('href="../', 'href="/').replace('src="../', 'src="/')
    open(os.path.join(ROOT, "404.html"), "w", encoding="utf-8").write(doc)
    open(os.path.join(ROOT, "sitemap.xml"), "w", encoding="utf-8").write(
        '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "".join(f"<url><loc>{SITE}{u}</loc></url>\n" for u in sorted(set(sitemap))) + "</urlset>\n")
    open(os.path.join(ROOT, "robots.txt"), "w").write(f"User-agent: *\nAllow: /\nSitemap: {SITE}/sitemap.xml\n")
    open(os.path.join(ROOT, ".nojekyll"), "w").write("")
    with open(os.path.join(ROOT, "tools", "immagini-mancanti.txt"), "w") as f:
        f.write("# Immagini usate dal sito ma non ancora nel repository.\n# Copiarle negli stessi percorsi (wp-content/uploads/...) e rilanciare build.py.\n")
        f.write("\n".join(sorted(MISSING)) + "\n")
    print(f"pagine: {len(sitemap)}  immagini mancanti: {len(MISSING)}  board it/en: {len(data['it']['board'])}/{len(data['en']['board'])}"
          f"  soci: {len(data['it']['members'])}/{len(data['en']['members'])}  cep: {len(data['it']['cep'])}  progetti: {len(rows['it'])}/{len(rows['en'])}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "tools", "export.xml"))
