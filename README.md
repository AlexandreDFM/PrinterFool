# HZTZPrinter — ZJ-8360 Thermal Ticket Printer

Interface Python complète pour l'imprimante à tickets thermique **ZJ-8360** via USB.
CLI unifiée, serveur HTTP REST, système de templates, et génération de codes QR.

---

## ⚡ Démarrage rapide

```bash
# 1. Setup (une seule fois)
./run.sh setup

# 2. Activer l'environnement
source run.sh

# 3. Tester l'installation (aucune imprimante requise)
./run.sh test

# 4. Aperçu d'un ticket dans le terminal
./run.sh preview -j templates/sample_event_ticket.json

# 5. Lancer le serveur API
./run.sh serve
```

Le serveur écoute sur `http://localhost:8360/api/` (port configurable via `.env`).

---

## 📋 Spécifications de l'imprimante

| Propriété   | Valeur     |
|-------------|------------|
| Modèle      | ZJ-8360    |
| Interface   | USB        |
| Vendor ID   | `0x0416`   |
| Product ID  | `0x5011`   |
| Largeur     | 80mm / 96mm |

---

## 🔧 Installation

### Prérequis

- **Python** 3.9+ (`python3 --version`)
- **pip** (inclus avec Python 3.9+)
- **libusb** sur macOS : `brew install libusb`
- Imprimante ZJ-8360 connectée en USB et allumée

### Setup automatique

```bash
./run.sh setup
```

Ce script crée le `venv`, installe les dépendances, et configure `libusb` sur macOS.

### Setup manuel

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

### Dépendances

| Package        | Version | Rôle                                    |
|----------------|---------|-----------------------------------------|
| `pyusb`        | ≥ 1.2.1 | Communication USB avec l'imprimante    |
| `qrcode`       | ≥ 8.1   | Génération de codes QR                 |
| `pillow`       | ≥ 11.0  | Traitement d'image pour les QR codes   |
| `flask`        | ≥ 3.0   | Serveur HTTP pour le mode `serve`      |
| `flask-cors`   | ≥ 4.0   | Support CORS pour le serveur           |
| `python-dotenv`| ≥ 1.0   | Chargement de la configuration `.env`  |
| `black`        | ≥ 24.1.1| Formateur de code (développement)      |

### Vérifier l'installation

```bash
# Tests intégrés (13 tests, aucune imprimante requise)
./run.sh test

# Vérifier que l'imprimante est détectée
./run.sh list-usb
```

---

## 🖥️ Deux modes d'utilisation

| Mode            | Lancement                       | Usage                                      |
|-----------------|---------------------------------|--------------------------------------------|
| **CLI**         | `./run.sh <commande> [options]` | Commandes directes depuis le terminal      |
| **Serveur API** | `./run.sh serve`                | API REST HTTP pour accès réseau/programmatique |

---

## 🔤 Mode CLI

Toutes les commandes passent par `fool_printer.py` (ou le raccourci `./run.sh`) :

```bash
# Équivalents :
./run.sh preview -j templates/sample_event_ticket.json
python fool_printer.py preview -j templates/sample_event_ticket.json
```

### Commandes disponibles

| Commande   | Description                                              | Imprimante requise |
|------------|----------------------------------------------------------|--------------------|
| `preview`  | Rendu texte d'un ticket dans le terminal                 | ❌ Non             |
| `print`    | Imprimer un ou plusieurs tickets                         | ✅ Oui             |
| `qr`       | Générer un code QR (ASCII art ou PNG)                    | ❌ Non             |
| `list-usb` | Lister les périphériques USB connectés                   | ❌ Non             |
| `test`     | Lancer la suite de 13 tests intégrés                     | ❌ Non             |
| `serve`    | Démarrer le serveur HTTP REST                            | ❌ Non             |

### Aperçu d'un ticket (sans imprimante)

```bash
# Ticket d'événement
./run.sh preview -j templates/sample_event_ticket.json

# Reçu (auto-détecté grâce aux clés merchant/items/totals)
./run.sh preview -j templates/sample_receipt.json

# Plusieurs tickets d'un coup
./run.sh preview -j templates/sample_multiple_tickets.json

# Forcer un template + largeur papier
./run.sh preview -j data.json -t receipt --paper-width 32
```

### Imprimer vers l'imprimante

```bash
# Impression simple
./run.sh print -j templates/sample_event_ticket.json

# Avec options
./run.sh print -j data.json -t event --paper-width 48 --no-cut --feed-lines 5
```

### Générer un code QR

```bash
# ASCII art dans le terminal
./run.sh qr -d "https://example.com"

# Format printer-safe (caractères #)
./run.sh qr -d "TICKET-42" --format printer --ec-level H

# Sauvegarder en PNG
./run.sh qr -d "https://example.com" -o qr.png --size large

# Depuis un fichier JSON
./run.sh qr -j templates/sample_qr.json
```

### Options globales

```bash
./run.sh -v preview -j data.json    # Mode verbose (debug)
./run.sh -q print -j data.json      # Mode silencieux
./run.sh -V                          # Afficher la version
./run.sh --help                      # Aide générale
./run.sh preview --help              # Aide d'une commande
```

→ Référence complète : [`docs/cli.md`](docs/cli.md)

---

## 🌐 Mode Serveur API

Lancer le serveur HTTP qui expose toutes les fonctionnalités via REST :

```bash
# Port par défaut (8360, depuis .env)
./run.sh serve

# Port personnalisé
./run.sh serve --port 9000

# Mode debug (auto-reload)
./run.sh serve --port 8080 --debug
```

### Configuration du port

Le port est résolu dans cet ordre :
1. Flag `--port` en ligne de commande
2. Variable `HZTZ_PORT` dans `.env`
3. Valeur par défaut : **8360** (en référence au modèle ZJ-8360)

```bash
cp .env.example .env
# Modifier HZTZ_PORT=8360 si besoin
```

### Endpoints disponibles

Base URL : `http://localhost:8360/api/`

| Méthode | Endpoint          | Description                              |
|---------|-------------------|------------------------------------------|
| GET     | `/api/health`     | Vérification de santé du serveur         |
| GET     | `/api/templates`  | Liste des templates et options acceptées |
| POST    | `/api/preview`    | Rendu texte de ticket(s) sans imprimante |
| POST    | `/api/print`      | Envoi de ticket(s) à l'imprimante       |
| POST    | `/api/qr`         | Génération de code QR (ASCII ou PNG)     |
| GET     | `/api/usb`        | Liste des périphériques USB              |
| GET     | `/api/test`       | Exécution de la suite de tests           |

### Format de réponse

Toutes les réponses JSON suivent le même format :

```json
{ "ok": true,  "...données..." : "..." }
{ "ok": false, "error": "message d'erreur" }
```

### Exemples rapides

```bash
# Santé du serveur
curl http://localhost:8360/api/health

# Aperçu d'un ticket
curl -X POST http://localhost:8360/api/preview \
  -H "Content-Type: application/json" \
  -d '{
    "data": {
      "event": { "name": "Concert", "date": "15 juillet 2026", "time": "20:00" },
      "venue": { "name": "Amphithéâtre Central", "address": "123 Parc Central" },
      "seat":  { "section": "A", "row": "5", "seat": "12", "gate": "Nord" },
      "barcode": { "value": "EVT00012345" },
      "holder": { "name": "Jean Dupont" }
    },
    "paper_width": 48
  }'

# Générer un QR code en PNG
curl -X POST http://localhost:8360/api/qr \
  -H "Content-Type: application/json" \
  -d '{"data": "https://example.com", "format": "png", "size": "large"}' \
  --output qr.png
```

→ Référence complète : [`docs/api.md`](docs/api.md)

---

## 🎫 Système de Templates

Le moteur de templates sépare la présentation des données, inspiré des [Google Wallet Event Ticket Templates](https://developers.google.com/wallet/tickets/events/resources/template).

### Templates intégrés

| Template  | Clés déclencheurs (auto-détection)        | Factory                                      |
|-----------|-------------------------------------------|----------------------------------------------|
| `event`   | `event`, `seat`, `holder`                 | `TemplateBuilder.create_event_template()`    |
| `receipt` | `merchant`, `order`, `items`, `totals`    | `TemplateBuilder.create_receipt_template()`  |

L'auto-détection inspecte les clés de premier niveau du JSON. Il n'est pas nécessaire de spécifier `-t` dans la plupart des cas.

### Structure d'un ticket rendu

```
┌──────────────────────────────────────────────────┐
│  ================================================ │  Titre (= x largeur)
│                  Event Ticket                     │  Centré
│  ================================================ │
│                                                   │
│              Concert d'été 2026                   │  En-tête champ 1
│            Amphithéâtre Central                   │  En-tête champ 2
│                                                   │
│  ------------------------------------------------ │  Bordure carte
│  DATE: 15 juil / TIME: 20:00 / SECTION: A        │  Ligne carte 1
│  ROW: 5 / SEAT: 12 / GATE: Nord                  │  Ligne carte 2
│  ------------------------------------------------ │
│                                                   │
│                   TICKET #                        │  Label QR
│              █████████████████                    │  Code QR
│              █████████████████                    │
│                                                   │
│  Jean Dupont                                      │  Détails
│  123 Parc Central, NY 10001                       │
└──────────────────────────────────────────────────┘
```

### Utilisation via Python

```python
from src.template_system import TemplateBuilder
from src.ticket_renderer import TicketRenderer, PrinterConfig

# Créer un template et un renderer
template = TemplateBuilder.create_event_template()
renderer = TicketRenderer(template, PrinterConfig(paper_width=48))

# Données du ticket
data = {
    "event":   {"name": "Concert d'été", "date": "15 juillet 2026", "time": "20:00"},
    "venue":   {"name": "Amphithéâtre Central", "address": "123 Parc Central, NY"},
    "seat":    {"section": "A", "row": "5", "seat": "12", "gate": "Nord"},
    "barcode": {"value": "EVT00012345"},
    "holder":  {"name": "Jean Dupont"},
}

# Aperçu texte (sans imprimante)
print(renderer.render_to_text(data))
```

### Imprimer via Python

```python
from src.printer import ZJ8360Printer
from src.template_system import TemplateBuilder
from src.ticket_renderer import TicketPrinter, PrinterConfig

template = TemplateBuilder.create_event_template()
printer = ZJ8360Printer(paper_width=48)

if printer.connect():
    try:
        tp = TicketPrinter(printer, template, PrinterConfig(paper_width=48))
        tp.print_formatted_ticket(data, cut_paper=True, feed_lines=3)
    finally:
        printer.disconnect()
```

→ Référence complète : [`docs/templates.md`](docs/templates.md) · [`docs/python-api.md`](docs/python-api.md)

---

## 📊 Structure JSON

### Ticket d'événement

```json
{
  "event":   { "name": "Concert d'été 2026", "date": "15 juillet 2026", "time": "20:00" },
  "venue":   { "name": "Amphithéâtre Central", "address": "123 Parc Central, NY 10001" },
  "seat":    { "section": "A", "row": "5", "seat": "12", "gate": "Nord" },
  "barcode": { "value": "EVT00012345" },
  "holder":  { "name": "Jean Dupont" }
}
```

### Reçu

```json
{
  "merchant":    { "name": "Coffee Shop Express", "address": "42 Rue de la Paix" },
  "order":       { "commande_number": "CMD-2026-002156", "ticket_number": "002156", "caisse_number": "02" },
  "transaction": { "date": "2026-03-30", "hour": "14:32", "type": "À emporter" },
  "staff":       { "seller": "Thomas Lefevre" },
  "items": [
    { "quantity": 1, "designation": "Cappuccino Moyen", "unit_price": 4.50, "total_price": 4.50, "tva": 0.72 },
    { "quantity": 2, "designation": "Croissant Jambon",  "unit_price": 5.50, "total_price": 11.00, "tva": 1.76 }
  ],
  "totals":  { "total_ht": 15.50, "tva_amount": 2.48, "total_ttc": 17.98 },
  "qr_code": { "value": "CMD-2026-002156-CAFE" },
  "footer":  { "message": "À bientôt !" }
}
```

### Plusieurs tickets (tableau)

Passer un tableau JSON pour imprimer/prévisualiser plusieurs tickets d'un coup :

```json
[
  { "event": { "name": "Show" }, "holder": { "name": "Alice" }, "..." : "..." },
  { "event": { "name": "Show" }, "holder": { "name": "Bob" },   "..." : "..." }
]
```

### Fichiers d'exemple inclus

| Fichier                            | Template  | Format     | Contenu                          |
|------------------------------------|-----------|------------|----------------------------------|
| `sample_event_ticket.json`         | `event`   | Objet      | Ticket d'événement complet       |
| `sample_multiple_tickets.json`     | `event`   | Tableau ×3 | Trois places pour le même show   |
| `sample_receipt.json`              | `receipt` | Objet      | Reçu complet avec TVA et QR      |
| `sample_student_attendence_1.json` | `receipt` | Tableau ×1 | Reçu sans TVA par article        |
| `sample_student_attendence_2.json` | `receipt` | Objet      | Reçu complet avec coordonnées    |
| `sample_qr.json`                   | —         | Objet      | Payload QR seul (commande `qr`)  |

→ Référence complète : [`docs/json-schemas.md`](docs/json-schemas.md)

---

## 🔲 Génération de Codes QR

Les codes QR sont générés automatiquement pour tout ticket contenant un champ `barcode.value` ou `qr_code.value`.

| Format      | Usage                   | Commande                                           |
|-------------|-------------------------|----------------------------------------------------|
| **ASCII**   | Aperçu terminal (█)    | `./run.sh qr -d "DATA"`                           |
| **Printer** | Aperçu terminal (#)    | `./run.sh qr -d "DATA" --format printer`           |
| **PNG**     | Export image            | `./run.sh qr -d "DATA" -o qr.png --size large`    |
| **ESC Z**   | Impression native       | Automatique lors de `print` (commande USB directe) |

Niveaux de correction d'erreur : `L` (7%), `M` (15%), `Q` (25%), `H` (30%).

Tailles PNG : `tiny` (32×32), `small` (48×48), `medium` (96×96), `large` (144×144).

---

## 🧪 Collections de tests API

Trois collections prêtes à l'emploi pour tester l'API avec votre client préféré :

| Client                                    | Fichier à importer                                                      | Requêtes |
|-------------------------------------------|-------------------------------------------------------------------------|----------|
| [Bruno](https://www.usebruno.com/)        | `api-collections/bruno/` (ouvrir le dossier)                            | 11       |
| [Postman](https://www.postman.com/)       | `api-collections/postman/HZTZPrinter_API.postman_collection.json`       | 16       |
| [Insomnia](https://insomnia.rest/)        | `api-collections/insomnia/HZTZPrinter_API.insomnia_v4.json`            | 19       |

Chaque collection inclut des requêtes pour tous les endpoints, des données d'exemple, et des cas d'erreur.
L'environnement par défaut pointe sur `http://localhost:8360`.

---

## 📁 Structure du projet

```
HZTZPrinter/
├── fool_printer.py              # Point d'entrée CLI
├── run.sh                       # Script shell (setup + raccourci CLI)
├── requirements.txt             # Dépendances Python
├── .env                         # Configuration port/debug (non commité)
├── .env.example                 # Template .env
│
├── src/                         # Package Python principal
│   ├── __init__.py
│   ├── printer.py               # Driver USB ZJ-8360
│   ├── template_system.py       # Moteur de templates
│   ├── ticket_renderer.py       # Rendu texte + impression hardware
│   ├── qrcode_generator.py      # Génération QR (ASCII, PNG, ESC/POS)
│   └── api_server.py            # Serveur Flask (create_app, run_tests)
│
├── templates/                   # Fichiers JSON d'exemple
│   ├── sample_event_ticket.json
│   ├── sample_multiple_tickets.json
│   ├── sample_receipt.json
│   ├── sample_student_attendence_1.json
│   ├── sample_student_attendence_2.json
│   └── sample_qr.json
│
├── docs/                        # Documentation détaillée
│   ├── index.md                 # Vue d'ensemble
│   ├── installation.md          # Guide d'installation
│   ├── cli.md                   # Référence CLI complète
│   ├── api.md                   # Référence API HTTP
│   ├── python-api.md            # Référence API Python
│   ├── templates.md             # Système de templates
│   └── json-schemas.md          # Schémas JSON des données
│
└── api-collections/             # Collections de tests API
    ├── bruno/
    ├── postman/
    └── insomnia/
```

---

## 🐛 Dépannage

### L'imprimante n'est pas détectée

```bash
# Lister les périphériques USB
./run.sh list-usb

# Vérifier avec debug
./run.sh -v list-usb
```

- Vérifier que l'imprimante est **allumée** (LED d'alimentation)
- Vérifier le **câble USB** (essayer un autre port)
- Sur **macOS** : installer `libusb` (`brew install libusb`)

### Erreur "Permission denied"

```bash
# Exécuter avec sudo (solution rapide)
sudo python fool_printer.py list-usb
```

Sur **Linux**, créer une règle udev pour un accès permanent :

```bash
# /etc/udev/rules.d/99-zj8360.rules
SUBSYSTEM=="usb", ATTR{idVendor}=="0416", ATTR{idProduct}=="5011", MODE="0666"
```

Puis : `sudo udevadm control --reload-rules && sudo udevadm trigger`

### Le texte s'imprime mal

- Vérifier la largeur papier : `--paper-width 32` (80mm) ou `--paper-width 48` (96mm)
- Utiliser `--printer-safe` pour remplacer les caractères Unicode par de l'ASCII
- Vérifier que le papier n'est pas coincé

### Le serveur ne démarre pas

```bash
# Vérifier que les dépendances Flask sont installées
pip install flask flask-cors python-dotenv

# Vérifier que le port n'est pas déjà utilisé
./run.sh serve --port 9000
```

→ Guide d'installation détaillé : [`docs/installation.md`](docs/installation.md)

---

## 📚 Documentation

| Document                                     | Contenu                                              |
|----------------------------------------------|------------------------------------------------------|
| [`docs/index.md`](docs/index.md)             | Vue d'ensemble du projet                             |
| [`docs/installation.md`](docs/installation.md) | Installation, venv, permissions USB, `.env`         |
| [`docs/cli.md`](docs/cli.md)                 | Toutes les commandes CLI, flags, exemples            |
| [`docs/api.md`](docs/api.md)                 | Référence API HTTP — endpoints, schémas, exemples    |
| [`docs/python-api.md`](docs/python-api.md)   | API Python — classes, méthodes, exemples             |
| [`docs/templates.md`](docs/templates.md)     | Système de templates, auto-détection, personnalisation |
| [`docs/json-schemas.md`](docs/json-schemas.md) | Schémas JSON pour event tickets et receipts        |

---

## 📚 Commandes ESC/POS de base

L'imprimante supporte le standard ESC/POS :

| Fonction         | Commande | Code         |
|------------------|----------|--------------|
| Initialiser      | `ESC @`  | `\x1b\x40`  |
| Caractère gras   | `ESC E`  | `\x1b\x45`  |
| Alignement       | `ESC a`  | `\x1b\x61`  |
| Taille police    | `GS !`   | `\x1d\x21`  |
| Coupe papier     | `GS V`   | `\x1d\x56`  |
| Avancer papier   | `LF`     | `\n`         |
| QR code natif    | `ESC Z`  | `\x1b\x5a`  |

---

## 🔗 Ressources

- [Documentation ZJ-8360](http://www.zjiang.com/en/init.php/product/index?id=65)
- [Standard ESC/POS (Epson)](https://www.epson.biz/products/by-type/pos-printers/esc-pos)
- [PyUSB Documentation](https://pyusb.github.io/pyusb/)
- [Flask Documentation](https://flask.palletsprojects.com/)
- [Bruno API Client](https://www.usebruno.com/)

---

## ✅ Checklist d'installation

- [ ] Python 3.9+ installé
- [ ] `./run.sh setup` exécuté
- [ ] `./run.sh test` — 13/13 tests passent
- [ ] `.env` créé (`cp .env.example .env`)
- [ ] Imprimante USB connectée et allumée
- [ ] `./run.sh list-usb` — imprimante détectée (Vendor `0x0416`)
- [ ] `./run.sh preview -j templates/sample_event_ticket.json` — aperçu OK
- [ ] `./run.sh serve` — serveur démarre sur le port configuré

---

## 📝 Licence

Ce code est fourni à titre éducatif et d'exemple. Libre d'utilisation.

## 🆘 Support

1. Consulter la [documentation détaillée](docs/index.md)
2. Lancer les tests : `./run.sh test`
3. Vérifier les logs : `./run.sh -v <commande>`
4. [Documentation officielle ZJ-8360](http://www.zjiang.com/en/init.php/product/index?id=65)