#!/bin/bash
# Script wrapper pour exécuter les scripts Python avec la bonne configuration

export DYLD_LIBRARY_PATH=/opt/homebrew/lib:$DYLD_LIBRARY_PATH

# Activer le venv et exécuter le script
source venv/bin/activate
python3 "$@"
