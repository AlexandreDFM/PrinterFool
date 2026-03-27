# ZJ-8360 Thermal Ticket Printer - Python Interface

Interface Python pour contrôler l'imprimante à tickets thermique **ZJ-8360**.

## 📋 Spécifications de l'imprimante

- **Modèle**: ZJ-8360
- **Type**: Imprimante thermique à tickets
- **Largeur papier**: 80mm
- **Vendor ID**: `0x0416`
- **Product ID**: `0x5011`
- **Documentation officielle**: [http://www.zjiang.com/en/init.php/product/index?id=65](http://www.zjiang.com/en/init.php/product/index?id=65)

## 🔧 Installation

### Prérequis
- Python 3.7+
- pip

### Configuration sur macOS

#### 1. Installer les dépendances Python
```bash
pip install -r requirements.txt
```

#### 2. Configurer les permissions USB (macOS)

Si vous rencontrez des erreurs d'accès USB, vous devrez configurer les permissions :

**Option A: Utiliser `sudo` (simple)**
```bash
sudo python examples.py 1
```

**Option B: Configurer les permissions permanent (recommandé)**

Créer un fichier de règles udev ou/et macOS.

Sur **macOS**, si l'imprimante n'est pas détectée :
1. Installer les drivers libusb si nécessaire :
```bash
brew install libusb
```

2. Redémarrer le système d'exploitation ou reconnecter l'imprimante USB.

#### 3. Vérifier la détection de l'imprimante

```bash
python printer.py
```

Cela affichera tous les appareils USB connectés. Vous devriez voir :
```
Vendor: 0x0416 | Product: 0x5011 | Manufacturer: ...
```

## 📖 Guide d'utilisation

### Code simple

```python
from printer import ZJ8360Printer

# Créer une instance
printer = ZJ8360Printer()

# Se connecter à l'imprimante
if printer.connect():
    # Imprimer du texte
    printer.print_text("Bonjour!")

    # Avancer le papier
    printer.feed_paper(3)

    # Couper le papier
    printer.cut_paper()

    # Se déconnecter
    printer.disconnect()
else:
    print("Impossible de se connecter à l'imprimante")
```

### API Complète

#### Connexion

```python
printer = ZJ8360Printer()
printer.connect()  # Retourne True/False
printer.disconnect()
```

#### Impression basic

```python
# Texte simple
printer.print_text("Mon texte")

# Ligne de séparation
printer.print_line()  # Avec '-' par défaut
printer.print_line('=')  # Avec '=' personnalisé

# Texte centré
printer.print_centered("Titre")
```

#### Formatage

```python
# Gras
printer.set_bold(True)
printer.print_text("Texte gras")
printer.set_bold(False)

# Taille de police (1-8)
printer.set_font_size(height=2, width=2)

# Alignement
printer.set_alignment('left')    # ou 'center', 'right'
```

#### Gestion papier

```python
# Avancer le papier
printer.feed_paper(5)  # 5 lignes

# Couper le papier
printer.cut_paper()
```

#### Reçu formaté

```python
items = [
    ("Café", "2,50 €"),
    ("Croissant", "1,50 €"),
    ("Jus", "2,00 €"),
]

printer.print_receipt(
    items=items,
    title="FACTURE",
    total="6,00 €"
)
```

## 🎯 Exemples

### Exemple 1: Texte simple
```bash
python examples.py 1
```

### Exemple 2: Texte formaté
```bash
python examples.py 2
```

### Exemple 3: Reçu complet
```bash
python examples.py 3
```

### Exemple 4: Différentes tailles
```bash
python examples.py 4
```

### Exemple 5: Mise en page avancée
```bash
python examples.py 5
```

## 💡 Exemples avancés

### Imprimer un reçu avec logo

```python
printer = ZJ8360Printer()
printer.connect()

# Configuration
printer.set_alignment('center')
printer.set_font_size(2, 2)
printer.set_bold(True)

# En-tête
printer.print_centered("MAGASIN ABC")
printer.set_bold(False)
printer.set_font_size(1, 1)
printer.print_centered("123 Rue Principal")
printer.print_text("")

# Ligne séparation
printer.print_line("=")

# Détails
printer.set_alignment('left')
printer.print_text("Ref: #001234")
printer.print_text("Date: 27/03/2026")

# Tableau
printer.print_line()
printer.print_text(f"{'Produit':<15} {'Qty':>5} {'Prix':>10}")
printer.print_line()

items = [
    ("Articles", 2, "10,00"),
    ("Services", 1, "5,00"),
]

for name, qty, price in items:
    line = f"{name:<15} {qty:>5} {price:>10}"
    printer.print_text(line)

printer.print_line()

# Total
printer.set_bold(True)
printer.print_text(f"{'TOTAL':<15} {'':>5} {'15,00':>10}")
printer.set_bold(False)

# Footer
printer.set_alignment('center')
printer.print_text("Merci!")
printer.feed_paper(5)
printer.cut_paper()

printer.disconnect()
```

### Boucle d'impression continue

```python
printer = ZJ8360Printer()
printer.connect()

for i in range(10):
    printer.set_alignment('center')
    printer.print_centered(f"Ticket #{i+1}")
    printer.feed_paper(3)
    printer.cut_paper()

printer.disconnect()
```

## 🐛 Dépannage

### L'imprimante n'est pas détectée

1. **Vérifier la connexion USB**
   ```bash
   python printer.py
   ```

2. **Vérifier que l'imprimante est allumée** (LED d'alimentation)

3. **Redémarrer le MacBook ou l'imprimante**

4. **Déboguer avec logs**
   ```python
   import logging
   logging.basicConfig(level=logging.DEBUG)
   ```

### Erreur "Permission denied"

Sur macOS, exécuter avec `sudo` :
```bash
sudo python examples.py 1
```

Ou modifier les permissions de l'appareil.

### Le texte n'imprime pas correctement

- Vérifier l'encodage : `print_text(text, encoding='utf-8')`
- Réduire la largeur du texte (max 32 caractères par défaut)
- Vérifier que le papier ne est pas bloqué

### Problèmes de coupure du papier

- S'assurer que le ressort de coupure d'est pas bloqué
- Vérifier que la lame est propre
- Contacter le support ZJ si le problème persiste

## 📚 Commandes ESC/POS de base

Cette imprimante supporte le standard ESC/POS. Quelques commandes clés :

| Fonction | Commande | Code |
|----------|----------|------|
| Initialiser | `ESC @` | `\x1b\x40` |
| Caractère gras | `ESC E` | `\x1b\x45` |
| Alignement | `ESC a` | `\x1b\x61` |
| Taille police | `GS !` | `\x1d\x21` |
| Coupe papier | `GS V` | `\x1d\x56` |
| Avancer papier | `LF` | `\n` |

## 🔗 Ressources
- [Documentation ZJ-8360](http://www.zjiang.com/en/init.php/product/index?id=65)
- [Standard ESC/POS](https://www.epson.biz/products/by-type/pos-printers/esc-pos)
- [PyUSB Documentation](https://pyusb.github.io/pyusb/)

## 📝 Licence

Ce code est fourni à titre d'exemple. Libre d'utilisation.

## ✅ Checklist d'installation complète

- [x] Installation de Python 3.7+
- [ ] Installation de pip
- [ ] Installation des dépendances : `pip install -r requirements.txt`
- [ ] Connexion de l'imprimante USB
- [ ] Test de détection : `python printer.py`
- [ ] Test simple : `python examples.py 1`
- [ ] Configuration des permissions (si nécessaire)
- [ ] Commencer à imprimer!

## 🆘 Support

Pour les problèmes spécifiques à l'imprimante ZJ-8360 :
1. Consulter la [documentation officielle](http://www.zjiang.com/en/init.php/product/index?id=65)
2. Vérifier les logs : `python printer.py` avec les appareils USB connectés
3. Contacter le support ZJ Zjiang
