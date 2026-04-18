#!/usr/bin/env bash
# Esci immediatamente se un comando fallisce
set -o errexit

# Installa le librerie
pip install -r requirements.txt

# Raccoglie i file statici (CSS, JS) per WhiteNoise
python manage.py collectstatic --no-input

# Applica le modifiche al database
python manage.py migrate
