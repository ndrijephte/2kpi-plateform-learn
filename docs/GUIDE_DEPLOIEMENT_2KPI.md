# 🚀 Guide de déploiement — Plateforme 2KPI (cPanel)

Guide complet et éprouvé pour mettre en ligne la plateforme 2KPI :
la **vitrine** (site public) et l'**espace apprenant** (application Django).
Rédigé d'après le déploiement réel — **les erreurs rencontrées et leurs solutions sont en fin de document** (section Dépannage).

> À placer dans le dépôt : `PLATEFORME_2KPI/docs/GUIDE_DEPLOIEMENT_2KPI.md`

---

## 🗺️ Vue d'ensemble

```
                        Internet
                           │
        ┌──────────────────┴───────────────────┐
        │                                       │
  2kpinnov.org                          learn.2kpinnov.org
  (VITRINE — statique)                  (APP — Django/Passenger)
        │                                       │
   public_html/                 repositories/2kpi-plateform-learn/2KPI_LEARN
   (HTML/CSS/JS)                          │
        │                            PostgreSQL 13
        └───────── API ─────────────────▶ (c2864961c_geoai)
     inscription → /api/candidatures/
     catalogue  ← /api/sessions/
```

| Élément | Valeur (exemple réel) |
|---|---|
| Dépôt GitHub (unique) | `ndrijephte/2kpi-plateform-learn` |
| Clone serveur | `/home/c2864961c/repositories/2kpi-plateform-learn` |
| Dossier de l'app Django | `…/2kpi-plateform-learn/2KPI_LEARN` (contient `manage.py`, `passenger_wsgi.py`) |
| Sous-domaine app | `learn.2kpinnov.org` |
| Python (serveur) | **3.13** |
| Django | **5.2 LTS** (cible) — voir l'avertissement ci-dessous |
| Base de données | PostgreSQL **13** — `c2864961c_geoai` / user `c2864961c_learn` |

> ⚠️ **Compatibilité version Django ↔ PostgreSQL (à arbitrer)**
> Le projet vise **Django 5.2 LTS** (maintenu en sécurité jusqu'en 2028), **mais 5.2 exige
> PostgreSQL 14+** — l'hébergement est en **PostgreSQL 13**. Trois options :
> 1. **Obtenir PostgreSQL 14+** auprès de l'hébergeur → on garde Django 5.2 LTS + Postgres (idéal).
> 2. **Basculer la base en MariaDB/MySQL** (déjà présent, supporté par Django 5.2 LTS) → pérenne.
> 3. **Rester en Django 5.1 + PostgreSQL 13** (`pip install "Django>=5.1,<5.2"`) → ça fonctionne
>    tout de suite, **mais Django 5.1 est en fin de vie** (plus de correctifs de sécurité) : à ne
>    pas laisser en production durablement.

---

## ✅ Prérequis (déjà vérifiés sur cet hébergement)

- cPanel avec **Setup Python App** (Passenger) et **Contrôle de version Git**
- **PostgreSQL 13** + phpPgAdmin
- Sous-domaines, **Terminal**, **Tâches cron**, **AutoSSL**

---

# PARTIE A — L'application Django (learn.2kpinnov.org)

## A1. Créer le sous-domaine

cPanel → **Domaines → Sous-domaines** → `learn` sur `2kpinnov.org` → **Créer**.

## A2. Créer la base PostgreSQL ⭐ (étape sensible)

cPanel → **Bases de données PostgreSQL** :

1. **Créer une base** → nom court `geoai` → donne `c2864961c_geoai`.
2. **Créer un utilisateur** → `learn` → donne `c2864961c_learn` ; **génère et copie le mot de passe**.
3. 🔴 **AJOUTER L'UTILISATEUR À LA BASE** (section « Ajouter un utilisateur à une base de données ») :
   utilisateur `c2864961c_learn` + base `c2864961c_geoai` → **TOUS LES PRIVILÈGES**.

> 📌 **À retenir** : sans l'étape 3, la connexion échoue avec
> `no pg_hba.conf entry for … user … database …`. C'est l'erreur n°1.

**À noter** : NOM=`c2864961c_geoai`, USER=`c2864961c_learn`, MDP=…, HÔTE=`localhost`, PORT=`5432`.

## A3. Récupérer le code (Git)

cPanel → **Contrôle de version Git** → **Créer** :
- URL : `https://github.com/ndrijephte/2kpi-plateform-learn.git`
- Chemin : `repositories/2kpi-plateform-learn`

→ crée `/home/c2864961c/repositories/2kpi-plateform-learn/` avec `VITRINE_2KPI/` et `2KPI_LEARN/`.

## A4. Créer l'application Python (Passenger)

cPanel → **Setup Python App** → **Create Application** :

| Champ | Valeur |
|---|---|
| Python version | **3.13** |
| Application root | `repositories/2kpi-plateform-learn/2KPI_LEARN` |
| Application URL | `learn.2kpinnov.org` |
| Startup file | `passenger_wsgi.py` |
| Entry point | `application` |

> 📌 Si « **Virtual environment already exists** » : une app existe déjà pour ce dossier (réutilise-la)
> **ou** un environnement orphelin traîne → voir Dépannage.

## A5. Le fichier `.env` (secrets)

Dans **`2KPI_LEARN/`** (à côté de `manage.py`), crée `.env` (Gestionnaire de fichiers ou `nano .env`) :

```ini
DEBUG=False
SECRET_KEY=<clé générée>
ALLOWED_HOSTS=learn.2kpinnov.org

DB_ENGINE=postgresql
DB_NAME=c2864961c_geoai
DB_USER=c2864961c_learn
DB_PASSWORD=<le mot de passe de la base>
DB_HOST=localhost
DB_PORT=5432

VITRINE_ORIGINS=https://2kpinnov.org,https://www.2kpinnov.org

# Tant que le SSL n'est pas actif (voir A8), décommente :
# SECURE_SSL_REDIRECT=False
```

Générer la clé secrète (dans le terminal de l'app) :
```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

> 📌 Mot de passe avec `#`, espace ou guillemets → **entoure-le de guillemets** : `DB_PASSWORD="mon#mdp"`.

## A6. Installer, migrer, initialiser ⭐ (ordre important)

Dans **Setup Python App**, copie la **commande d'activation** de l'environnement, colle-la dans
**Terminal**, puis :

```bash
pip install -r requirements.txt

# ⚠️ Si PostgreSQL 13 et Django 5.2 (erreur « PostgreSQL 14 required ») :
#    arbitre d'abord (PG14 / MySQL / 5.1 temporaire — voir l'avertissement en tête).
#    Dépannage immédiat : pip install "Django>=5.1,<5.2"

python manage.py migrate            # 1) crée les tables  ← AVANT le seed !
python manage.py seed_geoai         # 2) 12 modules, 24 compétences, 48 séances
python manage.py import_gift        # 3) 22 questions du Test S1
python manage.py createsuperuser    # 4) ton compte admin
python manage.py collectstatic --noinput
```

> 📌 **Toujours `migrate` AVANT `seed_geoai`** — sinon :
> `relation "formation_formation" does not exist`.

## A7. Redémarrer et vérifier

Setup Python App → **Restart**. Ouvre `https://learn.2kpinnov.org` :
page de connexion → connexion admin → tableau de bord. `…/admin/` = administration.

## A8. Activer le HTTPS (SSL)

cPanel → **Sécurité → État SSL/TLS** → vérifie/`Exécuter AutoSSL` sur `learn.2kpinnov.org`.
Une fois le cadenas actif : **retire** `SECURE_SSL_REDIRECT=False` du `.env` → **Restart**.

## A9. E-mails (activation de compte, mot de passe oublié, notifications)

1. cPanel → **Comptes de messagerie** → crée `no-reply@2kpinnov.org`.
2. **Connect Devices** → relève le **SMTP sortant** (ex. `mail.2kpinnov.org`) et le **port SSL** (465).
3. Dans `.env` :
   ```ini
   EMAIL_HOST=mail.2kpinnov.org
   EMAIL_PORT=465
   EMAIL_HOST_USER=no-reply@2kpinnov.org
   EMAIL_HOST_PASSWORD=<mot de passe du compte>
   EMAIL_USE_SSL=True
   DEFAULT_FROM_EMAIL=2KPI Learn <no-reply@2kpinnov.org>
   ```
4. **Restart**, puis teste : `python manage.py tester_email ton.adresse@exemple.org`.

## A10. Tâches planifiées (cron)

cPanel → **Tâches cron**. Remplace `ACTIVER` par la commande d'activation (A6) :

| Fréquence | Commande |
|---|---|
| Tous les jours 18 h | `ACTIVER && python manage.py envoyer_rappels >> logs/cron.log 2>&1` |
| Tous les jours 2 h | `ACTIVER && python manage.py sauvegarder --garder 14 >> logs/cron.log 2>&1` |

---

# PARTIE B — La vitrine (2kpinnov.org)

Le dépôt étant **unique**, un `.cpanel.yml` à la **racine** copie `VITRINE_2KPI/` vers `public_html`.

1. cPanel → **Contrôle de version Git** → sur le dépôt `2kpi-plateform-learn` →
   **Update from Remote** puis **Deploy HEAD Commit**.
2. La vitrine est copiée dans `public_html` → visible sur `https://2kpinnov.org`.

---

# PARTIE C — Relier la vitrine et l'app

1. **Promotions › Vitrine** (dans l'app) : publie une promotion comme « session vitrine ».
   → la vitrine lit le catalogue sur `https://learn.2kpinnov.org/api/sessions/`.
2. **Inscription** depuis la vitrine → POST `…/api/candidatures/` → apparaît dans **Candidatures**
   (côté admin) ; « Accepter » crée le compte + inscription + e-mail.
3. **Bouton « Espace apprenant »** → `https://learn.2kpinnov.org/login/`.
4. `.env` › `VITRINE_ORIGINS` doit contenir le domaine de la vitrine.

---

# 🔁 Mettre à jour (à chaque nouvelle version)

Sur ta machine : `git add -A && git commit -m "…" && git push`. Puis sur le serveur :

```bash
# cPanel → Git Version Control → Update from Remote (+ Deploy pour la vitrine)
# Terminal (app) :
pip install -r requirements.txt     # si requirements a changé
python manage.py migrate            # si nouvelles migrations
python manage.py collectstatic --noinput
# Setup Python App → Restart
```

---

# 🛠️ Dépannage (erreurs réellement rencontrées)

| Message | Cause | Solution |
|---|---|---|
| `Virtual environment already exists …` | Une app existe déjà pour ce dossier, ou venv orphelin | Réutilise l'app existante ; sinon `rm -rf /home/c2864961c/virtualenv/repositories/2kpi-plateform-learn/2KPI_LEARN` puis recrée |
| `no pg_hba.conf entry for host … user … database …` | L'utilisateur n'est **pas rattaché** à la base | cPanel → PostgreSQL → **Ajouter l'utilisateur à la base** (TOUS LES PRIVILÈGES) |
| `PostgreSQL 14 or later is required (found 13.x)` | Django 5.2 (requis par le projet) incompatible avec PostgreSQL 13 | **Arbitrer** (cf. avertissement en tête) : PostgreSQL 14+ **ou** MariaDB/MySQL **ou**, en dépannage, `pip install "Django>=5.1,<5.2"` (5.1 = fin de vie) |
| `password authentication failed for user …` | Mauvais mot de passe/utilisateur, ou identifiants du serveur utilisés en local | Recopie/régénère le MDP ; identifiants `c2864961c_*` **uniquement sur le serveur** ; guillemets si caractères spéciaux |
| `relation "…" does not exist` (au `seed`) | `seed` lancé avant `migrate` | Lance **`migrate` d'abord**, puis `seed_geoai` |
| `connection refused … port 5432` | Mauvais hôte | `DB_HOST=localhost` |
| Boucle de redirection (301) | SSL pas encore actif + `SECURE_SSL_REDIRECT=True` | Mets `SECURE_SSL_REDIRECT=False` jusqu'à l'AutoSSL (A8) |
| CSS/JS absents | `collectstatic` non lancé | `python manage.py collectstatic --noinput` + Restart |
| Erreur 500 / page blanche | `.env` incomplet ou erreur appli | Setup Python App → onglet **Log** ; vérifie `.env` |

---

# 🧭 Rappel express (installation « from scratch »)

```
1. Sous-domaine learn            6. pip install -r requirements.txt
2. Base PG + user + AJOUT user→DB 7. pip install "Django>=5.1,<5.2"
3. Git clone du dépôt            8. migrate → seed_geoai → import_gift
4. Setup Python App (3.13)       9. createsuperuser → collectstatic
5. .env (DB_ENGINE=postgresql)  10. Restart → AutoSSL → SMTP → cron
```

*Dernière mise à jour : octobre 2026. En cas de nouvelle erreur, note le message exact — il indique presque toujours la cause.*
