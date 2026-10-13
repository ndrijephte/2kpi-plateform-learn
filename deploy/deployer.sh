#!/bin/bash
# Mise en production sur cPanel — vitrine + application Django, en une passe.
#
# Lancé automatiquement par .cpanel.yml (« Deploy HEAD Commit », déclenché par GitHub Actions
# à chaque push sur main — voir .github/workflows/deploiement.yml), ou à la main :
#   bash ~/repositories/2kpi-plateform-learn/deploy/deployer.sh
#
# Étapes : vitrine → public_html ; pip (si requirements.txt a changé) ; sauvegarde puis migrate
# (si nouvelles migrations) ; collectstatic ; contrôle Django ; redémarrage Passenger.
# Journal : 2KPI_LEARN/logs/deploiement.log
set -euo pipefail

DEPOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP="$DEPOT/2KPI_LEARN"
PUBLIC_HTML="${PUBLIC_HTML:-$HOME/public_html}"
mkdir -p "$APP/logs"
exec > >(tee -a "$APP/logs/deploiement.log") 2>&1

etape() { echo "[$(date '+%F %T')] $*"; }
trap 'etape "ÉCHEC à la ligne $LINENO — mise en production interrompue"' ERR

etape "=== Déploiement de $(git -C "$DEPOT" log -1 --format='%h « %s »') ==="

# 1) Vitrine → public_html (les fichiers propres à public_html non versionnés restent en place)
etape "Vitrine → $PUBLIC_HTML"
for element in index.html pages css js assets; do
  /bin/cp -R "$DEPOT/VITRINE_2KPI/$element" "$PUBLIC_HTML/"
done

# 2) Application : environnement virtuel créé par « Setup Python App »
#    (~/virtualenv/<racine de l'app>/<version Python>/bin/activate) — surcharge possible : VENV=…
VENV="${VENV:-$(ls -d "$HOME/virtualenv/${APP#"$HOME"/}"/*/ 2>/dev/null | sort -V | tail -1)}"
if [ -z "$VENV" ] || [ ! -f "$VENV/bin/activate" ]; then
  etape "AVERTISSEMENT : environnement Python introuvable — app non mise à jour (créer l'app dans Setup Python App)"
  exit 1
fi
# shellcheck disable=SC1091
source "$VENV/bin/activate"
cd "$APP"
etape "Python : $(python --version 2>&1) ($VENV)"

# cPanel réécrit parfois passenger_wsgi.py : on restaure la version du dépôt
git -C "$DEPOT" checkout -- 2KPI_LEARN/passenger_wsgi.py 2>/dev/null || true

EMPREINTE="logs/.requirements.sha256"
if ! sha256sum -c --status "$EMPREINTE" 2>/dev/null; then
  etape "Dépendances : pip install -r requirements.txt"
  pip install --quiet --disable-pip-version-check -r requirements.txt
  sha256sum requirements.txt > "$EMPREINTE"
else
  etape "Dépendances inchangées"
fi

if ! python manage.py migrate --check >/dev/null 2>&1; then
  etape "Nouvelles migrations : sauvegarde préalable de la base"
  python manage.py sauvegarder --garder 14
  etape "migrate"
  python manage.py migrate --noinput
else
  etape "Aucune migration en attente"
fi

etape "collectstatic"
python manage.py collectstatic --noinput -v0
python manage.py check

# 3) Redémarrage de l'app (Passenger relit tmp/restart.txt)
mkdir -p tmp && touch tmp/restart.txt
etape "=== Déploiement terminé : application redémarrée ==="
