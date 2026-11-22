# ieaitaly.org

Sito statico dell'Istituto di Ecologia Applicata, generato dall'esportazione di WordPress (22 novembre 2026). È HTML puro: niente database, niente plugin, niente CMS.

## Cosa c'è

- **Pagine e notizie agli stessi indirizzi di WordPress** (`/chi-siamo/`, `/progetti/gargano/`, `/en/iea/`, `/2026/11/11/...`). I link esterni e quelli dei motori di ricerca continuano a funzionare senza reindirizzamenti.
- **Tre lingue** (IT, EN, HR), con il selettore che porta alla pagina tradotta quando esiste.
- **LIFE Alexandro**: sezione con il proprio sotto-menu. La WebApp resta in `/AlexandroWebApp/`, che **non fa parte** di questo repository.
- **Progetti**: elenco con ricerca e filtri (in corso / europei).
- `404.html`, `sitemap.xml`, `robots.txt`.

## Struttura

```
index.html, chi-siamo/, progetti/, en/, hr/, 2026/ …   pagine generate
assets/site.css, assets/site.js                          grafica e script comuni
wp-content/uploads/                                      immagini (stessi percorsi di WordPress)
tools/build.py                                           generatore dall'XML di WordPress
tools/immagini-mancanti.txt                              immagini usate ma non ancora nel repository
```

## Immagini

Le immagini già presenti in `wp-content/uploads/` vengono usate dal repository. Le altre, per ora, si caricano **dal vecchio server** (`https://ieaitaly.org/wp-content/...`), così l'anteprima è completa.

**Prima di spostare il dominio** bisogna copiare la cartella `wp-content/uploads` del vecchio sito (almeno i file elencati in `tools/immagini-mancanti.txt`) e rilanciare il generatore. Altrimenti, spento WordPress, quelle immagini spariscono.

Serve anche la cartella `wp-content/assets_landingPWA`, usata dalla pagina della WebApp.

## Rigenerare da WordPress

```
python3 tools/build.py percorso/WordPress.xml
```

Serve solo finché WordPress resta la fonte. Dopo il passaggio, le pagine si modificano direttamente in HTML.

## Da fare prima di andare online

- [ ] Copiare `wp-content/uploads` e `wp-content/assets_landingPWA`, poi rigenerare
- [ ] Decidere dove ospitare la WebApp `/AlexandroWebApp/` (backend e login operatori)
- [ ] Modulo contatti: ora è un link email. Eventualmente collegare Formspree o simili
- [ ] LIFE Wild Wolf: pagina da rifare (ora contiene solo il testo)
- [ ] DNS: copiare i record della posta (MX, SPF) prima di cambiare i record del sito
- [ ] Pagine duplicate o di prova rimaste online su WordPress: `chi-siamo-2`, `iea-it`, `life-alexandro-3`, `ultime-attivita` (generate per non rompere eventuali link, ma fuori dai menu)
