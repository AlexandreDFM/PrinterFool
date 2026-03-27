#!/bin/bash
# Setup script pour le projet ZJ-8360

set -e

echo "🔧 Installation HZTZPrinter ZJ-8360..."
echo ""

# Vérifier Python3
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 n'est pas installé"
    exit 1
fi

# Vérifier Homebrew
if ! command -v brew &> /dev/null; then
    echo "❌ Homebrew n'est pas installé"
    exit 1
fi

# Installer libusb s'il n'existe pas
if ! brew list libusb &> /dev/null; then
    echo "📦 Installation de libusb..."
    brew install libusb
fi

# Créer virtual environment
if [ ! -d "venv" ]; then
    echo "🐍 Création de l'environnement virtuel..."
    python3 -m venv venv
fi

# Activer et installer les dépendances
echo "📥 Installation des dépendances Python..."
source venv/bin/activate
pip install -r requirements.txt

echo ""
echo "✅ Installation complète!"
echo ""
echo "Pour utiliser l'imprimante, lancez:"
echo "  ./run.sh examples.py 1"
echo ""
echo "Ou directement:"
echo "  source venv/bin/activate"
echo "  python3 examples.py 1"
