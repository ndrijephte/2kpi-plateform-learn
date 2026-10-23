# Déployer 2KPI Learn sur cPanel — guide pas à pas

Objectif : mettre l'application en ligne sur **https://learn.2kpinnov.org**.
Compte cPanel : utilisateur **c2864961c**. Suis les étapes dans l'ordre. À chaque étape, note ce
qui est demandé « à retenir » — on s'en sert plus loin.

---

## Étape 1 — Créer le sous-domaine

1. Page d'accueil cPanel → rubrique **Domaines** → clique **Sous-domaines**.
2. Champ **Sous-domaine** : tape `learn`
3. **Domaine** : choisis `2kpinnov.org`
4. **Racine du document** : laisse ce que cPanel propose (ex. `learn.2kpinnov.org`).
5. Clique **Créer**.

✅ À retenir : le sous-domaine `learn.2kpinnov.org` existe maintenant.

---

## Étape 2 — Créer la base de données PostgreSQL

Le plus simple : l'**assistant**.

1. Accueil cPanel → rubrique **Bases de données** → clique **Assistant de base de données PostgreSQL**.
2. **Étape 1 (Nom de la base)** : tape `learn` → Suivant.
   → cPanel crée `c2864961c_learn`. **À retenir : NOM_BASE = `c2864961c_learn`**
3. **Étape 2 (Utilisateur)** :
   - Nom d'utilisateur : `learn` → cPanel crée `c2864961c_learn`. **À retenir : USER = `c2864961c_learn`**
   - Mot de passe : clique **Générateur de mots de passe**, copie-le en lieu sûr.
     **À retenir : MOT_DE_PASSE = (celui que tu as copié)**
   - Clique **Créer un utilisateur**.
4. **Étape 3 (Privilèges)** : coche **TOUS LES PRIVILÈGES** → **Suivant**.

✅ À retenir (récap) : NOM_BASE, USER, MOT_DE_PASSE, HÔTE = `localhost`, PORT = `5432`.

---

## Étape 3 — Mettre le code sur le serveur (Git)

> Prérequis : avoir poussé le dépôt unique **PLATEFORME_2KPI** (vitrine + app) sur GitHub.
> Ce même clone sert aussi à déployer la vitrine (`.cpanel.yml` à la racine du dépôt) : ne le crée qu'une fois.

1. Accueil cPanel → rubrique **Fichiers** → clique **Contrôle de version Git** (Git Version Control).
2. Clique **Créer**.
3. **URL du clone** : colle l'adresse du dépôt GitHub `https://github.com/ndrijephte/2kpi-plateform-learn.git`.
4. **Chemin du dépôt** : `repositories/2kpi-plateform-learn`  (cPanel le crée dans `/home/c2864961c/repositories/2kpi-plateform-learn`).
   L'app est dans son sous-dossier `2KPI_LEARN`.
   **À retenir : CHEMIN_APP = `/home/c2864961c/repositories/2kpi-plateform-learn/2KPI_LEARN`**
5. Clique **Créer**. Le code est cloné.

> **Dépôt privé ?** cPanel doit pouvoir lire GitHub : cPanel → **Accès SSH** → *Gérer les clés SSH*
> → *Générer une nouvelle clé* (sans phrase de passe) → *Autoriser* → copie la clé **publique**.
> Sur GitHub : dépôt → *Settings* → *Deploy keys* → *Add deploy key* (lecture seule), colle-la.
> URL du clone à utiliser alors : `git@github.com:ndrijephte/2kpi-plateform-learn.git`.

> Pas de dépôt GitHub prêt ? Alternative : **Gestionnaire de fichiers** → envoyer un `.zip` du dossier
> `2KPI_LEARN` dans `/home/c2864961c/repositories/2kpi-plateform-learn/2KPI_LEARN` puis **Extraire**.

---

## Étape 4 — Créer l'application Python (Passenger)

1. Accueil cPanel → rubrique **Logiciels** → clique **Setup Python App**
   (parfois « Configurer une application Python »).
2. Clique **Create Application** / **Créer une application**.
3. Renseigne :
   - **Python version** : choisis la plus récente proposée (**3.10 minimum**, requis par Django 5.2 ; 3.12+ idéal).
   - **Application root** (racine) : `repositories/2kpi-plateform-learn/2KPI_LEARN`  ← le CHEMIN_APP de l'étape 3.
   - **Application URL** : sélectionne `learn.2kpinnov.org`.
   - **Application startup file** : `passenger_wsgi.py`
   - **Application Entry point** : `application`
4. Clique **Create**.

En haut de la page de l'app, cPanel affiche une **commande pour entrer dans l'environnement virtuel**
(du type `source /home/c2864961c/virtualenv/repositories/2kpi-plateform-learn/2KPI_LEARN/3.13/bin/activate && cd /home/c2864961c/repositories/2kpi-plateform-learn/2KPI_LEARN`).
**Copie cette commande.** ← on l'utilise à l'étape 6.

---

## Étape 5 — Créer le fichier `.env` (secrets)

1. Génère une clé secrète : sur ton PC (dans le projet), lance :
   ```bash
   python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
   ```
   Copie la longue chaîne obtenue.
2. Dans cPanel → **Gestionnaire de fichiers** → va dans `/home/c2864961c/repositories/2kpi-plateform-learn/2KPI_LEARN`.
3. Bouton **+ Fichier** → nomme-le `.env` → **Créer**.
4. Sélectionne `.env` → **Modifier** → colle le contenu de `.env.example` (fourni dans le dépôt)
   et remplace les valeurs par les tiennes : `SECRET_KEY`, mot de passe de la base, et la boîte
   e-mail d'envoi (étape 9).
5. **Enregistrer**.

> Si `https://learn.2kpinnov.org` n'a pas encore de certificat SSL (voir Étape 8), ajoute
> temporairement une ligne : `SECURE_SSL_REDIRECT=False` (à retirer une fois le SSL actif).

---

## Étape 6 — Installer et initialiser (terminal)

1. Accueil cPanel → rubrique **Avancé** → clique **Terminal**.
2. Colle la **commande d'activation** copiée à l'étape 4, puis Entrée. (Tu es maintenant dans
   l'environnement de l'app, au bon dossier.)
3. Lance les commandes une par une :
   ```bash
   pip install -r requirements.txt
   python manage.py migrate
   python manage.py collectstatic --noinput
   python manage.py seed_geoai        # première installation uniquement
   python manage.py import_gift       # première installation uniquement
   python manage.py createsuperuser
   ```
   - `createsuperuser` te demande un identifiant, un e-mail et un mot de passe : ce sera **ton
     compte administrateur** de la plateforme.
   - Les dossiers `media/` (logo, photos — publics) et `prive/` (ressources, livrables — **jamais
     servis directement**) sont créés dans `/home/c2864961c/repositories/2kpi-plateform-learn/2KPI_LEARN`, donc **hors** du
     dossier public du sous-domaine : ne les déplace pas dans `public_html`.

---

## Étape 7 — Redémarrer l'application

Retourne sur la page **Setup Python App** → sur ton application, clique **Restart**.

Ouvre **https://learn.2kpinnov.org** :
- la page de **connexion** s'affiche ;
- connecte-toi avec le compte admin → tableau de bord ;
- `https://learn.2kpinnov.org/admin/` donne accès à l'admin (contenu éditable).

---

## Étape 8 — Activer le HTTPS (SSL)

1. Accueil cPanel → rubrique **Sécurité** → **État SSL/TLS**.
2. Vérifie que `learn.2kpinnov.org` a un certificat (sinon clique **Exécuter AutoSSL**).
3. Une fois le cadenas actif, retire la ligne `SECURE_SSL_REDIRECT=False` du `.env` si tu l'avais
   ajoutée, puis **Restart** l'application.

---

## Étape 9 — E-mails (activation des comptes, mot de passe oublié, notifications)

1. cPanel → **Comptes de messagerie** → crée `no-reply@2kpinnov.org` (mot de passe fort).
2. Sur ce compte → **Connect Devices** : relève le **serveur SMTP sortant** (souvent
   `mail.2kpinnov.org`) et le **port SSL** (465).
3. Renseigne dans `.env` : `EMAIL_HOST`, `EMAIL_PORT=465`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`,
   `DEFAULT_FROM_EMAIL`, `ADMINS` → **Restart**.
4. Teste dans le terminal : `python manage.py tester_email ton.adresse@exemple.org --reinitialisation`
   — diagnostic étape par étape (DNS, connexion, TLS, authentification, envoi), test du sendmail du
   serveur, puis envoi d'un vrai lien « mot de passe oublié » si un compte a cette adresse.

> **« Mot de passe oublié » OK en local mais rien n'arrive en ligne ?** Causes classiques sur cPanel :
> - l'app n'a pas été **redémarrée** après la modification du `.env` (le terminal lit le nouveau
>   `.env`, l'app en ligne garde l'ancien) → *Restart* ;
> - une variable `EMAIL_*` saisie dans *Setup Python App › Environment variables* **écrase** le `.env`
>   (le diagnostic le signale) → supprime-la ;
> - **SMTP Restrictions** de l'hébergeur : les applications ne peuvent pas ouvrir de connexion SMTP.
>   L'app bascule alors seule sur le `sendmail` du serveur ; pour l'imposer : `EMAIL_ENVOI=sendmail` ;
> - aucun compte **actif** n'a exactement cette adresse (la page affiche quand même « e-mail envoyé ») ;
> - l'e-mail est arrivé dans les **spams** : cPanel › *Email Deliverability* → réparer SPF et DKIM.
> Chaque demande est tracée dans `logs/2kpi_learn.log` (« lien envoyé à… », « ÉCHEC d'envoi… »,
> « aucun compte actif… »).

---

## Étape 10 — Tâches planifiées (cPanel › Tâches cron)

cPanel → **Avancé › Tâches cron** (*Cron Jobs*).

**1. Adresse e-mail de cron** (encadré « Adresse e-mail de cron » en haut de la page) : indique une boîte
**que quelqu'un lit**, par exemple `contacts@2kpinnov.org` ou l'adresse de l'administrateur technique.
cPanel y envoie ce qu'une tâche affiche *hors* du journal : les commandes ci-dessous écrivent tout dans
`logs/cron.log`, donc **aucun e-mail en temps normal** ; tu n'en reçois un que si la tâche ne peut même pas
démarrer (chemin erroné, Python introuvable…). C'est l'alarme qui signale une tâche cassée.

**2. Ajouter les trois tâches** (« Ajouter une nouvelle tâche cron » ; laisse « Paramètres courants » sur
*Paramètres personnalisés* et remplis les cinq champs) :

| Tâche | Minute | Heure | Jour | Mois | Jour de la semaine |
|---|---|---|---|---|---|
| Workflow (démarrages, relances de présences) | `0` | `6` | `*` | `*` | `*` |
| Rappels J-1 aux apprenants | `0` | `18` | `*` | `*` | `*` |
| Sauvegarde (base + fichiers) | `0` | `2` | `*` | `*` | `*` |

Commande de chaque tâche, **à copier telle quelle** (une ligne chacune) :

```
cd /home/c2864961c/repositories/2kpi-plateform-learn/2KPI_LEARN && /home/c2864961c/virtualenv/repositories/2kpi-plateform-learn/2KPI_LEARN/3.13/bin/python manage.py workflow_quotidien >> logs/cron.log 2>&1
```
```
cd /home/c2864961c/repositories/2kpi-plateform-learn/2KPI_LEARN && /home/c2864961c/virtualenv/repositories/2kpi-plateform-learn/2KPI_LEARN/3.13/bin/python manage.py envoyer_rappels >> logs/cron.log 2>&1
```
```
cd /home/c2864961c/repositories/2kpi-plateform-learn/2KPI_LEARN && /home/c2864961c/virtualenv/repositories/2kpi-plateform-learn/2KPI_LEARN/3.13/bin/python manage.py sauvegarder --garder 14 >> logs/cron.log 2>&1
```

> Le Python de l'environnement virtuel est appelé directement : pas besoin de `source …/activate`
> (le shell des tâches cron ne le connaît pas toujours). `3.13` est la version choisie dans
> *Setup Python App* : si tu en changes, adapte ce nombre (il figure dans la commande affichée en haut de
> la page de l'app).

**3. Vérifier** dès le lendemain : Gestionnaire de fichiers →
`repositories/2kpi-plateform-learn/2KPI_LEARN/logs/cron.log`. On doit y lire, par exemple,
« 0 promotion(s) démarrée(s), 0 en retard ; présences : … » et « … rappel(s) envoyé(s) ».
Pour tester tout de suite sans attendre, colle une des commandes dans le **Terminal** cPanel.

Les sauvegardes (base + `media/` + `prive/`) vont dans `sauvegardes/`. Télécharge-en une
régulièrement hors du serveur (Gestionnaire de fichiers › Télécharger).

---

## Étape 11 — Mettre en ligne la vitrine et la relier

1. **Sauvegarde d'abord l'ancien site** : Gestionnaire de fichiers → `public_html` → tout
   sélectionner → **Compresser** (zip) → télécharge le zip. Le déploiement remplace les fichiers de
   même nom (`index.html`, `pages/`, `css/`, `js/`, `assets/`) ; les autres restent en place.
2. cPanel → **Contrôle de version Git** → sur le dépôt `repositories/2kpi-plateform-learn` → **Gérer** → onglet
   *Pull or Deploy* → **Deploy HEAD Commit**. Le fichier `.cpanel.yml` (racine du dépôt) copie
   `VITRINE_2KPI/` dans `public_html`. Vérifie `https://2kpinnov.org` (vider le cache : Ctrl+F5).
3. **Le catalogue se gère dans l'application**, jamais dans le site :
   - **Formations affichées** : Paramètres › Formations › « Afficher au catalogue du site » (les 6
     formations historiques y ont été mises par la migration). Sans session ouverte, le site propose
     « Être prévenu(e) » (Candidatures › *Listes d'intérêt*).
   - **Session réservable** : Promotions › fiche **Vitrine** (dates affichées, lieu, horaire, places),
     puis *Pilotage* › « Ouvrir les inscriptions » : elle apparaît aussitôt sur le site, les personnes
     intéressées sont prévenues, et les **places restantes** baissent seules.
   La vitrine lit `https://learn.2kpinnov.org/api/catalogue/` ; si l'app est injoignable, elle affiche
   « catalogue momentanément indisponible » (aucune session fictive).
4. Le site vitrine envoie les inscriptions à `https://learn.2kpinnov.org/api/candidatures/`
   (`js/inscription-config.js` › `LEARN_API_URL`). Elles arrivent dans **Candidatures** (badge dans
   le menu admin). **Accepter** crée le compte, l'inscrit à la promotion et envoie l'e-mail
   d'activation.
5. Le bouton **Espace apprenant** du menu de la vitrine pointe vers `https://learn.2kpinnov.org/login/`.
6. Si la vitrine est servie sur un autre domaine que `2kpinnov.org` / `www.2kpinnov.org`, ajoute-le à
   `VITRINE_ORIGINS` dans `.env`.
7. **Test final** : sur `https://2kpinnov.org/pages/inscription.html`, envoie une inscription test →
   elle doit apparaître dans `learn.2kpinnov.org` › **Candidatures** (puis supprime-la).

---

## Mise à jour (à chaque nouvelle version)

**Automatique** : un `git push` sur main lance les tests puis met en ligne vitrine + app
(voir `docs/DEPLOIEMENT_AUTOMATIQUE.md` à la racine du dépôt pour la mise en place, une seule fois).

À la main si besoin (même effet) : Contrôle de version Git → **Update from Remote** puis
**Deploy HEAD Commit** — `.cpanel.yml` lance `deploy/deployer.sh` (vitrine, pip, sauvegarde + migrate,
collectstatic, redémarrage). Journal : `logs/deploiement.log`.

---

## En cas de souci

- **Erreur 500 / page blanche** : consulte `logs/2kpi_learn.log` (et l'e-mail envoyé aux `ADMINS`) ;
  vérifie le `.env` (identifiants de base, SECRET_KEY présents).
- **Les e-mails ne partent pas** : `python manage.py tester_email … --reinitialisation` affiche l'étape
  qui échoue et la correction (voir l'encadré de l'étape 9).
- **Le formulaire de la vitrine bascule sur l'e-mail** : l'API n'est pas joignable ou le domaine de la
  vitrine manque dans `VITRINE_ORIGINS`.
- **Boucle de redirection** : SSL pas encore actif → mets `SECURE_SSL_REDIRECT=False` le temps de
  faire l'AutoSSL (étape 8).
- **`pip` tente de compiler psycopg** : assure-toi que `requirements.txt` contient bien
  `psycopg[binary]` (déjà corrigé) et non `psycopg2-binary`.
- **CSS absent** : relance `python manage.py collectstatic --noinput` puis **Restart**.

---
