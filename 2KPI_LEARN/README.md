# 2KPI Learn — espace apprenant (Django)

Application du suivi de formation 2KPI (première formation : **GéoAI — Sassandra**).
Déploiement visé : `learn.2kpinnov.org` via cPanel **Setup Python App** (Passenger) + PostgreSQL.

## Démarrer en local

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # laisser DB_ENGINE vide => SQLite en local
python manage.py migrate
python manage.py seed_geoai   # 12 modules, 24 compétences, 48 séances
python manage.py import_gift  # 22 questions du Test S1 (module M1)
python manage.py createsuperuser
python manage.py runserver
```

Pages : `/` (tableau de bord) · `/formation/modules/` · `/comptes/profil/` · `/admin/`.

## Déploiement (cPanel Setup Python App)

1. Créer l'« application Python » (3.11) sur `learn.2kpinnov.org`, startup file `passenger_wsgi.py`.
2. Créer une base **PostgreSQL** (cPanel) et renseigner `.env` (DB_ENGINE=postgresql, identifiants).
3. Dans le terminal de l'app : `pip install -r requirements.txt`, `python manage.py migrate`,
   `python manage.py collectstatic --noinput`, `seed_geoai`, `import_gift`, `createsuperuser`.
4. **Restart** de l'application.

> Sécurité : tu crées la base, saisis les secrets (`.env`) et les comptes réels.
> L'app ne stocke jamais de mot de passe en clair (hachage Django).

## Structure

- `config/` — réglages, URLs, WSGI
- `apps/comptes` — profils, rôles, prérequis
- `apps/formation` — formation, modules, séances, compétences, ressources (+ `seed_geoai`)
- `apps/evaluation` — présence, livrables, quiz, compétences, projet, soutenance (+ `import_gift`)
- `apps/tableau_bord` — synthèse (note globale 40/40/20)
- `docs/ARCHITECTURE.md` — architecture détaillée

## Commandes de données

- `python manage.py seed_geoai` — (ré)initialise la formation GéoAI
- `python manage.py import_gift` — (ré)importe le Test S1 dans le module M1
