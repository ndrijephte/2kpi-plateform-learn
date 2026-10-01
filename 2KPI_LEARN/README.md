# 2KPI Learn — espace apprenant (Django)

Application du suivi de formation 2KPI (première formation : **GéoAI — Sassandra**).
Déploiement visé : `learn.2kpinnov.org` via cPanel **Setup Python App** (Passenger) + PostgreSQL.

## Démarrer en local

```bash
python -m venv .venv && source .venv/bin/activate      # Windows : .venv\Scripts\activate
pip install -r requirements.txt

# Créer la base PostgreSQL locale (une fois) :
createdb -h 127.0.0.1 -U postgres formation2kpi
# Puis un .env LOCAL (copie de .env.example) avec DEBUG=True et DB_ENGINE=postgresql,
# DB_NAME / DB_USER / DB_PASSWORD de ta base locale. EMAIL_HOST vide = e-mails dans la console.

python manage.py migrate
python manage.py seed_geoai   # 12 modules, 24 compétences, 48 séances
python manage.py import_gift  # 22 questions du Test S1 (module M1)
python manage.py createsuperuser
python manage.py runserver     # http://127.0.0.1:8000
```

> Local et production utilisent **PostgreSQL** (même moteur = pas de surprise au déploiement).
> `DB_ENGINE` vide bascule sur SQLite (repli de secours uniquement). En local (`DEBUG=True`),
> aucun `collectstatic` n'est nécessaire.

Pages : `/` (tableau de bord) · `/formation/modules/` · `/agenda/` · `/agenda/notifications/` ·
`/comptes/profil/` · espace formateur `/agenda/promotions/` (planning, présences) · `/admin/`.

### Profils et accès

| | Apprenant | Formateur | Admin |
|---|---|---|---|
| Tableau de bord | sa progression | ses promotions, séances, livrables à corriger | indicateurs plateforme + points d'attention |
| Cours / quiz | suivre, déposer | consultation, quiz en aperçu | consultation |
| Agenda | sa promotion | ses séances | toutes les séances |
| Planning, présences, correction | — | **ses** promotions | toutes |
| Utilisateurs, rôles, rattachement | — | — | `/comptes/utilisateurs/` |
| Créer une promotion, affecter le formateur | — | — | `/agenda/promotions/` |
| Admin Django | — | — | ✔ (accès synchronisé avec le rôle) |

| Ressources pédagogiques (fichiers + consignes) | consultation | dépôt sur **ses** formations | toutes |
| Paramètres (identité, logo, page de connexion, formations/séances, jours non travaillés, fichiers) | — | — | `/parametres/` |
| Modifier son profil | ✔ | ✔ | ✔ (+ tout compte via Utilisateurs) |

Le super-utilisateur est toujours administrateur. Un accès interdit renvoie une page 403.

### Accès des apprenants aux contenus (autorisation)

Un apprenant n'ouvre un module (séances, ressources, quiz, dépôt de livrable) que si :
1. son **inscription** à la formation est « En cours » et rattachée à une promotion (réglable par l'admin) ;
2. le module est **ouvert** pour sa promotion — Promotions › *Accès* : « Ouvert », « Fermé » ou
   « Auto » (ouverture le lundi de la semaine de la 1re séance, si l'ouverture automatique est active).

Les fichiers des ressources et des livrables sont stockés dans `prive/` (jamais servis par le serveur
web) et téléchargés uniquement via l'application après contrôle des droits.

### Paramétrage (admin)

- **Identité & logo** : nom, suffixe, logo (barre latérale, connexion, favicon), signature, e-mail de contact.
- **Page de connexion** : image de fond (défaut : `static/img/connexion.jpg`, issue de `docs/accueil.png`),
  titre et accroche ; un voile sombre garantit la lisibilité.
- **Formations & séances** : chaque séance a son créneau (semaine, jour, heure, durée, mode, lieu)
  et ses objectifs. Planning d'une promotion existante : bouton « Appliquer le paramétrage ».
- **Jours non travaillés** : globaux ou par promotion, évités à la génération.
- **Fichiers déposés** : extensions autorisées et taille max (les formats exécutables/HTML/SVG restent refusés).

> Production : `media/` (logo, image de connexion, photos) est servi par Apache ; `prive/` ne doit
> **pas** être exposé (le placer hors du dossier public) ; aligner la limite d'upload du serveur sur
> « Taille maximale ».

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
- `apps/core` — transversal : rôles & permissions (`permissions.py`), icônes SVG (`{% icon %}`), navigation
- `apps/comptes` — profils, rôles, prérequis
- `apps/formation` — formation, modules, séances, compétences, ressources (+ `seed_geoai`)
- `apps/evaluation` — présence, livrables, quiz, compétences, projet, soutenance (+ `import_gift`)
- `apps/agenda` — promotions, calendrier, planning formateur, présences, notifications
- `apps/tableau_bord` — synthèse (note globale 40/40/20) + vue formateur
- `docs/ARCHITECTURE.md` — architecture détaillée

## Tests

```bash
python manage.py test        # 32 tests : rôles, paramètres, accès aux contenus, fichiers, quiz, candidatures
```

## Exploitation

- `python manage.py tester_email adresse@exemple.org` — vérifie la configuration SMTP
- `python manage.py envoyer_rappels` — rappels J-1 (cron quotidien)
- `python manage.py sauvegarder [--garder 14]` — base + `media/` + `prive/` dans `sauvegardes/` (cron nocturne)
- Journaux : `logs/2kpi_learn.log` ; erreurs 500 envoyées par e-mail aux `ADMINS`

## Site vitrine

Le formulaire d'inscription de la vitrine envoie les demandes à `POST /api/candidatures/` (CORS limité à
`VITRINE_ORIGINS`, anti-robots, 5 envois/heure/IP). L'admin les traite dans **Candidatures** : accepter
crée le compte apprenant, l'inscrit à la promotion (rattachée via son « code session vitrine ») et
envoie un e-mail d'activation. Voir `docs/DEPLOIEMENT_cPanel.md`, étapes 9 à 11.

## Commandes de données

- `python manage.py seed_geoai` — (ré)initialise la formation GéoAI
- `python manage.py import_gift` — (ré)importe le Test S1 dans le module M1
