# Bonne Fête — Spécification produit

---

## 1. Vision

**Bonne Fête** est un calendrier iCalendar (`.ics`) public, gratuit auquel n'importe qui peut s'abonner depuis Google Calendar, Apple Calendar ou Outlook pour ne plus jamais oublier les fêtes affectives annuelles en France : Saint-Valentin, fêtes des mères, pères, grands-mères, grands-pères, et Journée mondiale des grands-parents.

Le projet a trois qualités revendiquées :

1. **Justesse** : les dates calculées suivent les règles légales ou conventionnelles documentées, y compris les exceptions (Pentecôte pour la fête des mères) ;
2. **Sanctuarisation historique** : les dates passées ne sont jamais réécrites, même si une règle change ; le calendrier est aussi un petit objet d'archive remontant à la naissance officielle de chaque fête ;
3. **Auto-maintenance** : un workflow GitHub Actions étend le calendrier d'une année chaque 1ᵉʳ janvier, sans intervention humaine, et un autre crée un rappel annuel pour vérifier que les règles n'ont pas évolué.

Le projet est délibérément francophone et français. L'audience cible est francophone, et la complexité internationale n'a pas été retenue (voir §11).

---

## 2. Périmètre fonctionnel

### 2.1 Les six fêtes

Présentées dans l'ordre chronologique de l'année.

| Clé (UID) | Nom affiché | Règle de calcul | Année de début | Source |
|---|---|---|---|---|
| `saint-valentin` | Saint-Valentin | 14 février (date fixe) | 1950 | Tradition immémoriale |
| `grands-meres` | Fête des Grands-Mères | 1ᵉʳ dimanche de mars, **sauf** 1987 (1ʳᵉ édition : samedi 28 mars, dernier samedi du mois) | **1987** | Café Grand'Mère, 1987 |
| `meres` | Fête des Mères | Dernier dimanche de mai, **sauf** si coïncidence avec la Pentecôte (= Pâques + 49 jours), auquel cas 1ᵉʳ dimanche de juin | 1950 | Loi n° 50-577 du 24 mai 1950 |
| `peres` | Fête des Pères | 3ᵉ dimanche de juin (sans exception) | 1952 | Décret de 1952 |
| `grands-parents` | Journée mondiale des grands-parents | 4ᵉ dimanche de juillet | 2021 | Pape François, 31 janvier 2021 |
| `grands-peres` | Fête des Grands-Pères | 1ᵉʳ dimanche d'octobre | 2008 | Franck Izquierdo, 2008 |

Notes :
- L'année de début est l'année à partir de laquelle la fête s'applique. Quand la **règle actuelle** (1ᵉʳ dimanche du mois, dernier dimanche, etc.) ne s'appliquait pas encore — cas de la fête des grands-mères en 1987, célébrée le samedi 28 mars (dernier samedi) — la fonction de calcul contient un cas particulier pour cette année précise.
- La Saint-Valentin est antérieure à 1950, mais 1950 fixe une borne arbitraire alignée sur la fête des mères pour cohérence du calendrier global.

### 2.2 Plage temporelle

- **Borne passée** : par fête, conforme au tableau ci-dessus. Le code itère depuis `min(année_début) = 1950`.
- **Borne future** : `année_courante + ANNEES_FUTURES`, où `ANNEES_FUTURES = 30`. Cette constante est ajustable mais 30 est le compromis recommandé (assez pour planifier une vie, pas assez pour devenir absurde).

### 2.3 Identité visible côté abonné

Métadonnées `VCALENDAR` à inclure :

- `PRODID:-//Bonne Fete//Calendrier des fetes affectives FR//FR`
- `X-WR-CALNAME:Bonne Fête (France)`
- `X-WR-CALDESC:Dates annuelles des fêtes affectives en France — Saint-Valentin, fêtes des mères, pères, grands-mères, grands-pères, et Journée mondiale des grands-parents.`
- `X-WR-TIMEZONE:Europe/Paris`
- `CALSCALE:GREGORIAN`
- `METHOD:PUBLISH`
- `VERSION:2.0`

---

## 3. Spécifications techniques iCalendar

### 3.1 Conformité RFC 5545

Le fichier doit valider en iCalendar (RFC 5545). Encodage UTF-8, fins de ligne CRLF (`\r\n`).

### 3.2 Structure d'un VEVENT

Chaque événement est un **all-day event** d'une journée (`DTSTART;VALUE=DATE` au jour J, `DTEND;VALUE=DATE` au jour J+1, comme l'exige iCalendar).

```
BEGIN:VEVENT
UID:{cle}-{annee}@bonne-fete-fr
DTSTAMP:20250101T000000Z
SEQUENCE:{n}
DTSTART;VALUE=DATE:{YYYYMMDD}
DTEND;VALUE=DATE:{YYYYMMDD+1}
SUMMARY:{nom_affiché}
DESCRIPTION:{texte_descriptif}
TRANSP:TRANSPARENT
END:VEVENT
```

`TRANSP:TRANSPARENT` signale aux clients que ce n'est pas un événement qui « bloque » le calendrier — il s'affiche en bandeau au-dessus de la journée plutôt que de fausser la disponibilité de l'utilisateur.

### 3.3 Stabilité des UID

Le format est `{cle}-{annee}@bonne-fete-fr`. Les composants `cle` et `annee` sont **immuables** (changer revient à créer des doublons chez les abonnés). 

### 3.4 DTSTAMP figé

La valeur de `DTSTAMP` est la chaîne littérale `19500101T000000Z` sur tous les événements. Pas la date du jour. Sans cela, deux régénérations successives produiraient des diffs Git parasites uniquement à cause du timestamp, déclencheraient des commits inutiles, et feraient bumper SEQUENCE sans raison.

### 3.5 SEQUENCE — propagation des révisions

Conformément à RFC 5545 §3.8.7.4, `SEQUENCE` s'incrémente quand le contenu signifiant d'un événement change.

Règle de mise à jour à appliquer à chaque (clé, année) :

1. Lire l'événement précédent depuis le `.ics` existant (s'il existe), récupérer son SEQUENCE (défaut 0 si absent).
2. Construire le nouveau VEVENT candidat selon la règle courante.
3. Comparer les **lignes signifiantes** des deux versions — c'est-à-dire toutes les lignes du bloc **sauf** `DTSTAMP` et `SEQUENCE`.
4. Décision :
   - Pas d'ancienne version → `SEQUENCE = 0` (événement nouveau).
   - Contenu signifiant identique → `SEQUENCE` inchangé (reproduction à l'identique).
   - Contenu signifiant modifié → `SEQUENCE = ancien_SEQUENCE + 1`.

### 3.6 Sanctuarisation du passé

Les événements dont la `DTSTART` est strictement antérieure à `date.today()` au moment de la régénération doivent conserver leur **date** depuis la version précédente du fichier, et non être recalculés depuis la règle courante. Le reste du contenu (`SUMMARY`, `DESCRIPTION`, etc.) suit la configuration courante — donc si vous changez un libellé, il s'applique aussi rétroactivement, et SEQUENCE bumpe en conséquence pour ces événements.

Si une loi change un jour, cette propriété garantit que la date que les Français ont effectivement célébrée en 2008 ne sera pas réécrite par la nouvelle règle.

### 3.7 Idempotence

Deux exécutions consécutives de `generate.py`, sans aucun changement de règle ni de date courante, doivent produire un fichier `.ics` **identique au bit près**. C'est ce qui permet au workflow GitHub Actions de ne committer que quand il y a un vrai changement.

---

## 4. Algorithmes de calcul

### 4.1 Date de Pâques

Algorithme **Meeus/Jones/Butcher** pour le comput grégorien. Donne une date exacte pour toute année ≥ 1583.

```
a = year mod 19
b = year div 100
c = year mod 100
d = b div 4
e = b mod 4
f = (b + 8) div 25
g = (b - f + 1) div 3
h = (19a + b - d - g + 15) mod 30
i = c div 4
k = c mod 4
l = (32 + 2e + 2i - h - k) mod 7
m = (a + 11h + 22l) div 451
month = (h + l - 7m + 114) div 31
day = ((h + l - 7m + 114) mod 31) + 1
```

### 4.2 N-ième dimanche d'un mois

Helper réutilisé par 4 des 6 fêtes :
- `n = 1, 2, 3, 4` : n-ième dimanche depuis le début du mois.
- `n = -1` : dernier dimanche du mois.

### 4.3 Règles spécifiques

- **Saint-Valentin** : `date(annee, 2, 14)`.
- **Fête des Grands-Mères** : `nième(annee, 3, 1)`, sauf pour `annee == 1987` où la valeur est `date(1987, 3, 28)`.
- **Fête des Mères** : `pentecote = paques(annee) + 49 jours`. Si `dernier_dimanche_mai(annee) == pentecote`, alors `nième(annee, 6, 1)`, sinon `nième(annee, 5, -1)`.
- **Fête des Pères** : `nième(annee, 6, 3)`.
- **Journée mondiale des grands-parents** : `nième(annee, 7, 4)`.
- **Fête des Grands-Pères** : `nième(annee, 10, 1)`.

---

## 5. Architecture du dépôt

```
bonne-fete-fr/
├── .github/
│   └── workflows/
│       ├── update-ics.yml           # régénération mensuelle + tests + validation + commit
│       └── review-rules.yml         # ouvre une issue de vérification chaque janvier
├── artefacts/
│   ├── index.html                   # page d'accueil produite (artefact, committée)
│   └── bonne-fete-fr.ics            # calendrier produit (artefact, committé)
├── src/
│   ├── generate.py                  # générateur du .ics ET de index.html
│   ├── tests.py                     # tests de non-régression des dates calculées
│   ├── validate.py                  # validation stricte RFC 5545 du .ics produit
│   └── index-template.html          # template de la page d'accueil (source à éditer)
├── pyproject.toml                   # déclaration du projet et de la dépendance `icalendar`
├── uv.lock                          # lock-file des dépendances, géré par uv
├── SPEC.md                          # ce document
├── README.md                        # présentation publique
└── LICENSE                          # licence du projet
```

**Gestion des dépendances et exécution** : le projet utilise [`uv`](https://docs.astral.sh/uv/) (Astral) à la fois comme gestionnaire de dépendances et comme lanceur de scripts. `pyproject.toml` déclare l'unique dépendance runtime (`icalendar`) et `uv.lock` la fige. Les scripts s'exécutent via `uv run <script>.py`, qui crée et synchronise au besoin un environnement virtuel local (`.venv/`) avant l'invocation — aucune installation `pip` globale n'est requise.

**Note sur le nom de fichier `.ics`** : Ce nom de fichier détermine l'URL d'abonnement et doit être fixé **avant la première publication** : tout changement ultérieur invaliderait l'URL et obligerait chaque abonné à se réinscrire.

---

## 7. Tests de non-régression — `tests.py`

### 7.1 Cas pinnés requis

Au minimum, les dates suivantes doivent être présentes comme assertions. Toutes sont vérifiées contre des sources de référence publiques.

**Saint-Valentin** (vérifie simplement que la date est fixe) :
- 2020 → 14 février 2020
- 2026 → 14 février 2026
- 2100 → 14 février 2100

**Fête des Grands-Mères** :
- 1987 → 28 mars (1ʳᵉ édition, samedi — cas particulier dans la fonction)
- 2022 → 6 mars
- 2024 → 3 mars
- 2026 → 1ᵉʳ mars
- 2027 → 7 mars
- 2028 → 5 mars

**Fête des Mères** (inclut impérativement des cas avec report Pentecôte) :
- 2008 → 25 mai (pas de conflit)
- 2012 → 3 juin (**report**, Pentecôte = 27 mai)
- 2018 → 27 mai
- 2023 → 4 juin (**report**, Pentecôte = 28 mai)
- 2025 → 25 mai
- 2026 → 31 mai
- 2034 → 4 juin (**report futur**)
- 2045 → 4 juin (**report futur**)

**Fête des Pères** :
- 2020 → 21 juin
- 2023 → 18 juin
- 2024 → 16 juin
- 2025 → 15 juin
- 2026 → 21 juin
- 2030 → 16 juin

**Journée mondiale des grands-parents** :
- 2021 → 25 juillet (1ère édition, source : Vatican News)
- 2022 → 24 juillet
- 2023 → 23 juillet
- 2024 → 28 juillet
- 2025 → 27 juillet

**Fête des Grands-Pères** :
- 2024 → 6 octobre
- 2025 → 5 octobre
- 2026 → 4 octobre
- 2027 → 3 octobre
- 2028 → 1ᵉʳ octobre

### 7.2 Comportement

`uv run tests.py` doit :
- Afficher chaque cas avec un marqueur ✓ ou ✗ ;
- Sortir avec code 0 si tous passent, code 1 sinon ;
- En cas d'échec, lister les divergences en clair.

---

## 8. Page d'accueil — `index.html`

La page d'accueil est **un artefact généré** par `generate.py` à partir d'un fichier source `index-template.html`. La séparation template/artefact garantit que les dates affichées restent toujours synchronisées avec le contenu du `.ics`, et que les boutons d'abonnement utilisent la même `URL_PUBLIQUE`.

### 8.1 Approche template

`index-template.html` est un HTML statique contenant quatre placeholders à substituer :

| Placeholder | Substitué par |
|---|---|
| `{{PROCHAINES_DATES}}` | HTML d'une liste de `<div class="date-row">…</div>` pour chaque fête, dans l'ordre chronologique des prochaines dates à partir d'aujourd'hui. La première (la plus proche) reçoit la classe additionnelle `featured` pour la mettre en valeur visuellement. Date formatée en français (« samedi 14 février 2026 »). |
| `{{URL_ICS}}` | Valeur de `URL_PUBLIQUE` |
| `{{URL_GCAL}}` | URL Google Calendar 1-clic : `https://calendar.google.com/calendar/render?cid={URL_ICS encodée}` |
| `{{URL_WEBCAL}}` | Version `webcal://` de `URL_PUBLIQUE` |
| `{{COMPTEUR_SCRIPT}}` | Bloc `<script>` du compteur (§12), ou chaîne vide si `COMPTEUR_API = None` |

### 8.2 Exigences fonctionnelles

- **Titre H1** parlant : « Calendrier des fêtes affectives en France » ou équivalent.
- **Liste des prochaines dates** : une ligne par fête, triée chronologiquement à partir d'aujourd'hui (donc affiche éventuellement des dates de l'année suivante pour les fêtes déjà passées de l'année courante).
- **Trois boutons d'abonnement** : Google Calendar (primaire), Apple/Outlook (webcal://), Téléchargement (.ics direct). Tous portent la classe CSS `subscribe-btn` pour que le compteur puisse y attacher des handlers.
- **URL brute** affichée en clair sous les boutons.
- **Compteur d'abonnements** (§12) : zone vide au chargement, remplie par JavaScript depuis l'API de compteur.
- **Brève section « Pourquoi ? »** justifiant la valeur du projet (exception Pentecôte, anomalie 1987).

### 8.3 Exigences SEO et partage

- `<title>` : « Bonne Fête — Calendrier des fêtes affectives en France ».
- `<meta name="description">` (~150 caractères).
- Balises Open Graph : `og:title`, `og:description`, `og:type=website`. **`og:image`** : recommandé (image carrée 1200×1200px déposée à la racine du dépôt, déclarée dans la balise). Élément fortement recommandé avant publication, parce que c'est ce que les visiteurs verront en aperçu lors d'un partage sur WhatsApp, Messenger ou Twitter.
- HTML sémantique (h1, sections), `lang="fr"`.

### 8.4 Design

Aesthetic libre. Le projet n'impose pas de style mais une page **personnelle, chaleureuse, lisible** sert mieux la mission qu'un design générique de SaaS. Une page d'une seule vue (pas de scroll infini), un fichier HTML monolithique avec CSS inline, polices Google Fonts pour le caractère.

### 8.5 Hébergement

Servie depuis GitHub Pages à la racine du dépôt. `index.html` ET `index-template.html` sont commités, mais seul `index.html` est servi publiquement (Pages ne fait pas de templating).

---

## 9. Automatisation

### 9.1 Workflow `update-ics.yml`

Régénération mensuelle.

- **Déclencheurs** : `schedule: cron '0 3 1 * *'` (1ᵉʳ de chaque mois, 3h UTC) + `workflow_dispatch` (déclenchement manuel).
- **Permissions** : `contents: write` pour pouvoir committer.
- **Étapes** :
  1. `actions/checkout@v4`.
  2. `astral-sh/setup-uv@v4` (installe `uv` ; active le cache des dépendances via le `uv.lock` versionné).
  3. `uv sync --frozen` (installe la dépendance `icalendar` dans un `.venv/` local, à l'identique du lock-file).
  4. Lancer `uv run tests.py`. Si échec, **arrêt** — garde-fou contre la publication d'un calcul cassé.
  5. Lancer `uv run generate.py` (régénère `bonne-fete-fr.ics` ET `index.html`).
  6. Lancer `uv run validate.py`. Si échec, **arrêt** — garde-fou contre la publication d'un `.ics` invalide.
  7. `git add bonne-fete-fr.ics index.html`. Si `git diff --staged --quiet` est vrai → rien à committer, sortir. Sinon, committer avec message `automatic calendar update` et `git push`.

**Justification du cron mensuel plutôt qu'annuel** : un run mensuel reste un no-op 11 mois sur 12 (le `.ics` ne change pas si l'année n'a pas changé). Mais si un run échoue ou est sauté (incidents GitHub, etc.), il sera rattrapé le mois suivant. Robuste sans coût.

### 9.2 Workflow `review-rules.yml`

Vérification annuelle de la pérennité des règles.

- **Déclencheurs** : `schedule: cron '0 9 15 1 *'` (15 janvier, 9h UTC) + `workflow_dispatch`.
- **Permissions** : `issues: write`.
- **Action** : crée une issue avec :
  - Titre : `Vérification annuelle {ANNEE} : les règles sont-elles toujours en vigueur ?`
  - Corps : une check-list de vérification **par fête**, chacune avec sa source de référence à consulter :
    - Saint-Valentin → tradition immémoriale (rien à vérifier sauf curiosité)
    - Fête des Mères → Légifrance, loi n° 50-577 (https://www.legifrance.gouv.fr/jorf/id/JORFTEXT000000886326) : vérifier l'absence de mention « modifié par » ou « abrogé »
    - Fête des Pères → décret de 1952, sources secondaires (Wikipédia, service-public.fr)
    - Fête des Grands-Mères → page Wikipédia + site de la marque Café Grand'Mère
    - Journée mondiale des grands-parents → Vatican News
    - Fête des Grands-Pères → page Wikipédia (création par Franck Izquierdo)
  - Instructions : si l'une des règles a changé, modifier `generate.py`, mettre à jour `tests.py` avec les nouvelles dates pinnées, relancer le workflow.

Exécutable via `gh issue create` (la CLI GitHub est préinstallée sur `ubuntu-latest`), authentifié par `GITHUB_TOKEN`.

---

## 10. Hébergement et URLs publiques

GitHub Pages, branche `main`, dossier racine.

| Ressource | URL |
|---|---|
| Page d'accueil | `https://{user}.github.io/{repo}/` |
| Fichier `.ics` | `https://{user}.github.io/{repo}/bonne-fete-fr.ics` |
| Abonnement Apple/Outlook | `webcal://{user}.github.io/{repo}/bonne-fete-fr.ics` |
| Abonnement Google Calendar | `https://calendar.google.com/calendar/render?cid={URL_ENCODÉE}` |

GitHub Pages sert nativement les `.ics` avec le `Content-Type: text/calendar` correct. Aucune configuration supplémentaire requise.

---

## 11. Validation iCalendar — `validate.py`

Vérification stricte du fichier produit, complémentaire des tests de calcul de `tests.py`.

### 11.1 Implémentation

Utilise la bibliothèque [`icalendar`](https://pypi.org/project/icalendar/) (mature, parser conforme RFC 5545). Déclarée dans `pyproject.toml`, installée via `uv sync`. Lancée par le workflow GitHub Actions après `generate.py` et avant tout commit.

### 11.2 Vérifications

1. **Parsing** : `Calendar.from_ical()` doit réussir sans exception (grammaire valide).
2. **Métadonnées VCALENDAR** : `PRODID` et `VERSION` présents.
3. **Par VEVENT** :
   - Propriétés requises : `UID`, `SUMMARY`, `DTSTART`, `DTEND`, `SEQUENCE`, `DTSTAMP`.
   - `DTEND > DTSTART`.
   - Dates dans la plage `[1900, 9999]`.
   - `SEQUENCE` est un entier ≥ 0.
4. **Unicité globale** : aucun `UID` en double dans le calendrier.

### 11.3 Comportement

`uv run validate.py` :
- Affiche les vérifications avec marqueurs ✓.
- Code de sortie 0 si tout passe, 1 sinon avec liste des problèmes (capée à 20).

---

## 12. Compteur d'abonnements

### 12.1 Approche

Compter réellement les abonnés à un `.ics` est techniquement difficile sans serveur dédié (un client calendrier rafetche typiquement le fichier 1× par jour, donc les requêtes HTTP brutes surestiment d'un facteur 50–100). Le compromis retenu : **compter les clics sur les boutons d'abonnement** depuis la page d'accueil, via une API de compteur tierce ne stockant aucune donnée individuelle.

### 12.2 Service

Par défaut, [counterapi.dev](https://counterapi.dev) v1 : gratuit, sans inscription, basé sur un couple namespace + nom de compteur servant de clé. Configuré via la constante `COMPTEUR_API` dans `generate.py`. Le service est aisément remplaçable par n'importe quel autre fournissant des endpoints `GET {URL}` (lire) et `GET {URL}/up` (incrémenter) — Cloudflare Workers, Vercel KV, etc.

### 12.3 Comportement côté navigateur

JavaScript injecté dans `index.html` par le template (via `{{COMPTEUR_SCRIPT}}`) :
- **Au chargement** : appel `GET COMPTEUR_API`, lecture du champ `count` (ou `value` selon le service), affichage dans `<p id="compteur">Déjà N ajouts au calendrier</p>` si N > 0. Échec silencieux si l'API est indisponible (la page reste lisible).
- **Au clic sur n'importe quel bouton portant la classe `subscribe-btn`** : appel `GET COMPTEUR_API/up` en fire-and-forget (pas d'attente), puis suivi normal du lien.

### 12.4 Étiquetage honnête

Le compteur affiche « ajouts au calendrier », pas « abonnés », pour ne pas mentir : un clic n'est pas une vraie souscription confirmée. Mettre `COMPTEUR_API = None` désactive entièrement la feature (aucun script JS n'est émis).

---

## 14. Critères d'acceptation

Le projet est conforme à cette spécification si **tous** les critères suivants sont satisfaits :

1. ✅ Cloner un dépôt frais, exécuter `uv run generate.py` → produit `bonne-fete-fr.ics` valide RFC 5545 avec ≥ 470 VEVENT (le nombre exact dépend de l'année courante ; 474 à mai 2026). `uv` crée automatiquement le `.venv/` et installe `icalendar` depuis le lock-file lors de la première invocation.
2. ✅ Exécuter `uv run tests.py` → 36 cas pinnés passent, code de sortie 0.
3. ✅ Toutes les valeurs de `DTSTAMP` sont strictement `19500101T000000Z`.
4. ✅ Tous les UIDs respectent le format `{cle}-{annee}@bonne-fete-fr`.
5. ✅ Tous les VEVENTs portent un `SEQUENCE:N` explicite.
6. ✅ Exécuter `uv run generate.py` deux fois de suite sans changement produit un fichier **identique au bit près** (`md5sum` identique).
7. ✅ Modifier manuellement une date passée dans le `.ics` puis relancer `uv run generate.py` → la modification est **conservée** (pas écrasée par recalcul).
8. ✅ Modifier la fonction `fete_des_meres` pour renvoyer une date différente, puis relancer → seuls les événements `fete-meres-*` futurs voient leur date changer et leur `SEQUENCE` incrémenter ; les passés et les autres fêtes restent inchangés.
9. ✅ `index.html` est régénérée automatiquement à chaque `uv run generate.py`, contient les 6 fêtes dans l'ordre chronologique à partir d'aujourd'hui, et utilise `URL_PUBLIQUE` pour construire les 3 boutons d'abonnement.
10. ✅ Exécuter `uv run validate.py` après `generate.py` → tous les contrôles passent, code de sortie 0. Modifier manuellement le `.ics` pour y introduire un UID en double → `validate.py` détecte le problème et sort en code 1.
11. ✅ `index.html` affiche un compteur d'abonnements via l'API configurée (ou pas de compteur si `COMPTEUR_API = None`), et le clic sur un bouton `.subscribe-btn` déclenche un appel `/up` à l'API.
12. ✅ Le workflow GitHub Actions de régénération exécute, dans l'ordre, tests → generate → validate → commit, et committe seulement quand au moins un des deux artefacts (`.ics` ou `index.html`) a réellement changé.
13. ✅ Le workflow de rappel annuel crée une issue avec une check-list couvrant les six règles et leurs sources respectives.
14. ✅ Les fichiers `LICENSE` et `README.md` sont présents à la racine.

---

## 15. Annexes

### A. Sources de référence

**Fête des Mères**
- Loi n° 50-577 du 24 mai 1950 : https://www.legifrance.gouv.fr/jorf/id/JORFTEXT000000886326

**Fête des Pères**
- Décret de 1952 (référence souvent citée mais texte original difficile à retrouver en ligne). Sources secondaires fiables : Wikipédia, articles spécialisés.

**Fête des Grands-Mères**
- Origine commerciale, marque Café Grand'Mère (groupe JDE)
- Wikipédia : https://fr.wikipedia.org/wiki/F%C3%AAte_des_grands-m%C3%A8res

**Fête des Grands-Pères**
- Création 2008 par Franck Izquierdo
- Wikipédia : https://fr.wikipedia.org/wiki/F%C3%AAte_des_grands-p%C3%A8res

**Journée mondiale des grands-parents et des personnes âgées**
- Annonce du pape François, 31 janvier 2021, après l'Angélus
- Vatican News : https://www.vaticannews.va/fr/pape/news/2021-01/pape-francois-angelus-annonce-journee-mondiale-grands-parents.html

**Saint-Valentin**
- Tradition pluriséculaire ; pas de référence légale française.

### B. Anomalies historiques connues

- **Fête des grands-mères 1987** : la première édition eut lieu le **samedi 28 mars 1987** (dernier samedi du mois), avant que la fête ne soit déplacée au 1ᵉʳ dimanche de mars à partir de 1988. Cette année est incluse dans le calendrier comme cas particulier de la fonction `fete_des_grands_meres()` (`annee_debut = 1987`). C'est volontairement une exception explicite plutôt qu'une exclusion, pour préserver la complétude historique du calendrier depuis la création de chaque fête.
- **Fête des mères avant 1950** : il existait une « Journée des Mères » sous Vichy depuis 1941, avec une autre cérémonie d'origine en 1918 à Lyon. La loi de 1950 instaure la version moderne et la détache de l'héritage pétainiste. Le calendrier commence en 1950 (`annee_debut = 1950`) pour des raisons à la fois techniques (règle stable) et éthiques.

---
