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
| Planning, présences, correction | — | **ses** promotions, **ses** modules (attribués par l'admin) | toutes |
| Utilisateurs, rôles, rattachement | — | — | `/comptes/utilisateurs/` |
| Lancer une session (assistant + aperçu), choisir le référent, publier sur la vitrine | — | — | Sessions › **Lancer une session** |
| Confier une ou plusieurs promotions à un formateur | — | — | Utilisateurs › fiche du formateur |
| Autoriser des formateurs, module par module | — | — | Sessions › ⋯ › **Formateurs par module** |
| Auto-évaluation sur les objectifs des séances | s'évalue, **Mes acquis** | rédige les objectifs, synthèse, demandes d'aide | toutes |
| Ouvrir les modules aux apprenants | — | consultation | Sessions › ⋯ › **Ouverture des modules** |
| Générer / recaler le calendrier | — | référent uniquement | toutes |
| Admin Django | — | — | ✔ (accès synchronisé avec le rôle) |

| Ressources pédagogiques (fichiers + consignes) | consultation | dépôt sur **ses** modules | toutes |
| Paramètres (identité, logo, page de connexion, formations/séances, jours non travaillés, fichiers) | — | — | `/parametres/` |
| Modifier son profil | ✔ | ✔ | ✔ (+ tout compte via Utilisateurs) |

Le super-utilisateur est toujours administrateur. L'administrateur n'est ni apprenant ni formateur : il
n'est jamais référent ni affecté à une promotion (il a déjà tous les droits). Un accès interdit renvoie une page 403.
Le rôle **Formateur** correspond aux enseignants.

### Création des comptes

- **Super-admin** : `python manage.py createsuperuser` — renseigner l'**e-mail** (indispensable au
  « mot de passe oublié »).
- **Apprenants, formateurs, admins** : **Utilisateurs → Nouveau compte** (rôle, mot de passe
  provisoire ; promotion pour un apprenant, une ou plusieurs promotions encadrées pour un formateur).
  La fiche d'un compte n'affiche que les champs de son rôle.
- **Libre-service** : `/creer-mon-compte/` (bouton « Créer mon compte » de la vitrine) — apprenant ou
  étudiant ; contenus accessibles seulement après rattachement à une promotion (candidature acceptée).
- **Candidatures** de la vitrine : *Accepter* crée le compte, l'inscrit et envoie le lien d'activation.

Pas à pas : `../docs/GUIDE_ADMINISTRATEUR.md`.

### Accès aux contenus : toujours sur autorisation de l'admin

Un **apprenant** n'ouvre un module (séances, ressources, quiz, dépôt de livrable) que si :
1. son **inscription** à la formation est « En cours » et rattachée à une promotion (validée par l'admin) ;
2. le module est **ouvert** pour sa promotion — Promotions › *Accès* (admin) : « Ouvert », « Fermé » ou
   « Auto » (ouverture le lundi de la semaine de la 1re séance, si l'admin a activé l'ouverture automatique).

Un **formateur** n'accède à une promotion, à sa formation et à ses modules que s'il en est le
**référent** (tous les modules) ou s'il y est **affecté** par l'admin (modèle `Affectation` : modules
cochés, ou tous). Sans affectation, il ne voit aucune formation. Cocher une promotion sur la fiche du
formateur crée une affectation « tous les modules » (les affectations module par module existantes
sont conservées) ; la décocher retire l'accès, y compris le rôle de référent. Tout est centralisé dans
`apps/core/permissions.py` (`interventions`, `q_interventions`, `modules_gerables`) et
`apps/formation/acces.py`.

Les fichiers des ressources et des livrables sont stockés dans `prive/` (jamais servis par le serveur
web) et téléchargés uniquement via l'application après contrôle des droits.

### Workflow d'une promotion (identique pour toute formation)

Les statuts ne se modifient jamais à la main : chaque passage vérifie sa check-list, applique ses effets
et s'inscrit au journal (`JournalStatut`). Écran : **Promotions › Pilotage** (décisions : admin ;
consultation : formateurs de la promotion). Logique : `apps/agenda/workflow.py`.

| Promotion | Pour y passer | Effets |
|---|---|---|
| Planifiée → **Inscriptions ouvertes** | formation active, chaque module a une séance, référent, calendrier généré, places | session publiée sur le site vitrine, personnes intéressées prévenues par e-mail |
| → **Prête à démarrer** | idem + effectif minimum d'inscriptions confirmées | — |
| → **En cours** | date de début atteinte (automatique, `workflow_quotidien`) | confirmées → en cours, retrait de la vitrine, notifications |
| → **Clôturée** | séances réalisées ou annulées, présences saisies, livrables rendus notés | résultat de chaque apprenant, admises restantes → abandon |
| → **Archivée** | — (annulation avant démarrage : aucune inscription confirmée) | `active = False` ; désarchivage possible |

Inscription : **admise** (candidature acceptée, rattachement) → **confirmée** (paiement reçu ou exonération ;
donne accès aux contenus) → **en cours** → **validée / non validée** à la clôture : assiduité ≥ seuil de la
formation (80 % par défaut, présent ou en retard sur les séances réalisées) **et** note finale ≥ note minimale
(10/20 par défaut, note globale 40/40/20). Seuils : Paramètres › Formations. Abandon et dérogation au
résultat : motif obligatoire.

**Prérequis et évaluation, par formation** (Paramètres › Formations) : liste de prérequis (un obligatoire
doit être « OK » pour confirmer l'inscription), grille du projet (critères notés sur 20, poids totalisant
100 %) et poids de la note finale (contrôle continu, projet, soutenance ; 40/40/20 par défaut, soutenance
à 0 = aucune). Saisie par promotion : **Promotions › Évaluation** (formateur référent et admin) ; l'apprenant
tient ses prérequis à jour depuis son profil. Une promotion ne se clôture qu'avec une évaluation complète.
Logique : `apps/evaluation/grille.py`.

**Attestation de réussite** : à la validation (clôture ou dérogation), l'inscription reçoit un numéro
(`2KPI-XXXX-XXXX`) ; le PDF (A4 paysage, ReportLab) se télécharge depuis le tableau de bord de l'apprenant
ou le Pilotage, et son QR code mène à la page publique `/attestation/<numéro>/` qui en atteste
l'authenticité (« retirée » si le résultat est ensuite invalidé). Signataire : Paramètres › Attestations.
Logique : `apps/evaluation/attestation.py`.

**À faire** : chaque tableau de bord commence par la liste de ce que le workflow attend de la personne
(urgences d'abord) — candidatures, inscriptions à confirmer, démarrages bloqués, clôtures possibles,
présences en retard (admin) ; feuilles de présence, corrections, demandes d'aide, évaluation finale
(formateur) ; confirmation en attente, prérequis, attestation (apprenant). `apps/tableau_bord/a_faire.py`.

**Exercices** (menu *Exercices*, app `apps/exercices`) : le formateur compose, sur ses modules, des
exercices dont chaque question a un barème (points) et une correction - choix multiple, vrai/faux, réponse
courte (variantes acceptées), valeur numérique (± tolérance) ou réponse rédigée notée à la main. Il les
planifie pour une promotion (ouverture, date limite) ; les apprenants sont prévenus, répondent et peuvent
modifier leurs réponses jusqu'à la date limite. Ensuite seulement, et une fois les réponses rédigées notées,
chacun voit sa note (ramenée sur 20), ses réponses, les réponses attendues, la correction et les commentaires.
Dès la première réponse, questions et barème sont figés (seule la correction reste modifiable). Distincts
des *quiz* de module (auto-tests illimités gérés dans Paramètres).

**Présences** : une séance ne devient « réalisée » qu'à l'enregistrement de sa feuille de présence complète
(apprenants confirmés ou en cours), ouverte dès le début de la séance. Les séances passées sans feuille
apparaissent dans le planning et le tableau de bord ; `workflow_quotidien` relance les formateurs de la
séance à J+1 et les administrateurs à J+3 (une fois chacun).

### Auto-évaluation sur les objectifs des séances

- Chaque séance porte des **objectifs** formulés pour l'apprenant (« À la fin de la séance, je suis
  capable de… ») : saisis **ligne par ligne** par l'admin (Paramètres › séance, ou page de la séance) ou
  par le formateur du module (carte « Objectifs de la séance » sur la page de la séance : Entrée ajoute
  une ligne, collage d'une liste découpé automatiquement, ordre modifiable). Modèle `ObjectifSeance`.
- Dès leur publication, ils apparaissent côté apprenant et les apprenants dont le module est ouvert
  sont notifiés des nouveaux objectifs ; sans objectifs, l'apprenant voit « Objectifs pas encore publiés ».
- L'apprenant se positionne sur chacun (1 Pas encore · 2 Avec de l'aide · 3 En autonomie · 4 Je peux
  l'expliquer), peut commenter et **demander de l'aide** ; il se réévalue quand il veut, son premier
  niveau est gardé pour mesurer la progression (`AutoEvaluation`). Vue d'ensemble : **Mes acquis**.
- Le formateur reçoit les demandes d'aide (notification + tableau de bord) et consulte la **synthèse**
  de chaque promotion (Planning › *Auto-évaluations*) : répartition des niveaux par objectif, part
  d'apprenants autonomes, commentaires ; « Aide apportée » prévient l'apprenant.
- Reformuler un objectif conserve les réponses ; un objectif retiré qui a des réponses est archivé.
  Logique : `apps/evaluation/autoevaluation.py`.

### Paramétrage (admin)

- **Identité & logo** : nom, suffixe, logo (barre latérale, connexion, favicon ; vide = logo officiel
  2KPI `static/img/logo-2kpi.png`), signature, e-mail de contact.
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

Installation initiale : `../docs/GUIDE_DEPLOIEMENT_2KPI.md` (Python 3.13, PostgreSQL, `.env`, puis
`migrate`, `seed_geoai`, `import_gift`, `createsuperuser`, `collectstatic`).
Mises à jour : **automatiques à chaque `git push` sur main** (`../docs/DEPLOIEMENT_AUTOMATIQUE.md`).

> Sécurité : tu crées la base, saisis les secrets (`.env`) et les comptes réels.
> L'app ne stocke jamais de mot de passe en clair (hachage Django).

## Structure

- `config/` — réglages, URLs, WSGI
- `apps/core` — transversal : rôles & permissions (`permissions.py`), icônes SVG (`{% icon %}`), navigation
- `apps/comptes` — profils, rôles, candidatures
- `apps/formation` — formation, modules, séances, compétences, ressources (+ `seed_geoai`)
- `apps/evaluation` — présence, livrables, quiz, compétences, prérequis et grille d'évaluation (`grille.py`), soutenance (+ `import_gift`)
- `apps/agenda` — promotions et leur workflow (`workflow.py`), calendrier, planning formateur, présences, notifications
- `apps/tableau_bord` — synthèse (note globale selon les poids de la formation) + vue formateur
- `docs/ARCHITECTURE.md` — architecture détaillée

## Tests

```bash
python manage.py test        # 96 tests : rôles, autorisations (apprenants, formateurs par module),
                             # promotions des formateurs, auto-évaluation, fichiers, quiz, candidatures,
                             # création de compte, mot de passe oublié, e-mails, workflow des promotions
```

## Exploitation

- `python manage.py tester_email adresse@exemple.org [--reinitialisation]` — diagnostic e-mail pas à pas
  (SMTP, sendmail du serveur) et, avec `--reinitialisation`, rejoue « mot de passe oublié » pour l'adresse
- E-mails : SMTP du `.env` avec **repli automatique sur sendmail** (cPanel) ; `EMAIL_ENVOI=sendmail` pour l'imposer
- `python manage.py envoyer_rappels` — rappels J-1 (cron quotidien)
- `python manage.py workflow_quotidien` — démarre les promotions prêtes à leur date, alerte les admins
  de celles qui ne le sont pas, relance les présences non saisies (cron quotidien, tôt le matin)
- `python manage.py sauvegarder [--garder 14]` — base + `media/` + `prive/` dans `sauvegardes/` (cron nocturne)
- Journaux : `logs/2kpi_learn.log` (dont chaque demande « mot de passe oublié » : envoyée, en échec,
  aucun compte, limite atteinte) ; `logs/deploiement.log` ; erreurs 500 envoyées par e-mail aux `ADMINS`

## Site vitrine : catalogue, liste d'intérêt, candidatures

La plateforme est la seule source : le site vitrine lit et écrit par une API publique (CORS limité à
`VITRINE_ORIGINS`, champ piège anti-robots, 5 envois par heure et par IP pour les envois).

| API | Rôle |
|---|---|
| `GET /api/catalogue/` | formations « au catalogue », avec leur état (`ouverte`, `a_venir`, `en_cours`) et leurs sessions ouvertes |
| `GET /api/sessions/` | sessions ouvertes aux inscriptions (formulaire d'inscription du site) |
| `POST /api/interet/` | « Être prévenu(e) » : nom, e-mail, téléphone, profil, structure → liste d'intérêt de la formation |
| `POST /api/candidatures/` | demande d'inscription à une session → **Candidatures** |

- **Catalogue** : Paramètres › Formations › « Afficher au catalogue du site », avec domaine, mode,
  durée habituelle, résumé et prix indicatif (affiché seulement si « Afficher le prix » est coché).
  Indépendant de « Active » (formation utilisable sur la plateforme, exigé pour ouvrir une session).
- **Publication d'une session** : assistant *Lancer une session* (`/agenda/promotions/nouvelle/`) puis
  « Créer et publier », ou « Enregistrer et publier » depuis la fiche d'un brouillon : la publication
  ouvre les inscriptions (workflow). Retrait : « Retirer du site » ou démarrage de la session. La fiche
  (`/agenda/promotions/<id>/vitrine/`) règle dates affichées, lieu, horaire, places et prix, avec un
  aperçu en direct de la carte du site.
- **Liste d'intérêt** (`Interet`) : Candidatures › *Listes d'intérêt* et liste « À faire » ; à
  l'ouverture d'une session, chaque personne en attente reçoit un e-mail avec le lien d'inscription
  (`VITRINE_URL/pages/inscription.html?session=<code>`), puis est marquée « prévenue ».
- **Candidatures** : *Accepter* crée le compte apprenant (ou retrouve celui de l'e-mail), l'admet dans
  la promotion et envoie l'e-mail d'activation ; l'inscription reste à confirmer dans Pilotage.

Variables : `VITRINE_ORIGINS` (sites autorisés à appeler l'API), `VITRINE_URL` (adresse du site dans les
e-mails, défaut `https://2kpinnov.org`). Voir `docs/DEPLOIEMENT_cPanel.md`, étapes 9 à 11.

## Commandes de données

- `python manage.py seed_geoai` — (ré)initialise la formation GéoAI
- `python manage.py import_gift` — (ré)importe le Test S1 dans le module M1
