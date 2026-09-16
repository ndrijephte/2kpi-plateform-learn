# 2KPI LEARN — Architecture de l'application

Plateforme d'apprentissage 2KPI (espace apprenant) — application web sur mesure.

- **Domaine** : `learn.2kpinnov.org`
- **Nature** : application Django (Python), rendue côté serveur, hébergée via **cPanel « Setup Python App » (Passenger)**
- **Base de données** : PostgreSQL
- **Périmètre du MVP** : 5 briques — comptes · cours GéoAI (modules & séances) · quiz · **tableau de bord de performance** (calqué sur `Suivi_Performance_Formation_GeoAI.xlsx`) · galerie de notebooks (liens Colab)
- **Principe** : le calcul lourd (Earth Engine, ML) reste hors serveur (GEE + Colab + machine de l'apprenant). L'application **suit et présente**, elle ne calcule pas.

---

## 1. Pile technique

| Élément | Choix | Pourquoi |
|---|---|---|
| Langage / framework | Python 3.11+ / **Django 5.x** | Aligné Python/notebooks, batteries incluses (auth, admin, ORM) |
| Base de données | **PostgreSQL** (dispo sur l'hébergement) | Robuste ; MySQL possible en repli |
| Authentification | **Django auth** (hachage mots de passe, sessions) + vérification e-mail | Sécurité éprouvée, pas de code maison sensible |
| Fichiers statiques | **WhiteNoise** | Sert le CSS/JS sans config serveur, idéal en mutualisé |
| Rendu | Templates Django + CSS **aux couleurs de la vitrine** 2KPI | Cohérence de marque, simple sous Passenger |
| Notebooks | `nbconvert` (rendu HTML) + bouton **« Ouvrir dans Colab »** | Exécution en ligne sans serveur Jupyter |
| Déploiement | cPanel **Setup Python App** (Passenger) + Git | Ton workflow local → Git → déploiement |
| Tâches périodiques | **cron** cPanel | Rappels, recalculs éventuels (pas de worker permanent) |

---

## 2. Modèle de données (calqué sur ton tableur)

> Chaque onglet du classeur de suivi devient une ou plusieurs tables.

### Comptes & inscription

- **Profil** (étend l'utilisateur Django) : `role` (apprenant / formateur / admin), `structure`,
  `specialite`, `telephone`. → onglet *Participant*
- **Prerequis** : lié au profil, statuts (OK / En cours / À faire) pour : compte GEE, compte
  GitHub, Miniconda+JupyterLab, QGIS, Git, machine ≥ 8 Go. → onglet *Participant*
- **Inscription** : `apprenant`, `formation`, `date_debut`, `date_fin_prevue`, `statut`.

### Contenu de formation

- **Formation** : `titre` (« GéoAI — Sassandra »), `slug`, `description`.
- **Module** (M1–M12) : `formation`, `code` (M1), `titre`, `ordre`. → structure des 12 modules
- **Seance** (48) : `module`, `jour` (Lundi/Mercredi/Vendredi/Samedi), `theme`,
  `duree_prevue_h`, `ordre`. → onglet *Suivi_Séances* / *Présence*
- **Competence** (24) : `module`, `code` (C1.1), `libelle`, `niveau_vise` (1–4). → onglet *Compétences*
- **Ressource** : `seance` (ou module), `type` (PDF / notebook / lien), `fichier`, `url`,
  `colab_url`. → PDF & `.ipynb` de la formation

### Évaluation & performance

- **Presence** : `inscription`, `seance`, `statut` (Présent/Retard/Excusé/Absent),
  `duree_realisee_h`. → onglet *Présence*
- **Livrable** : `inscription`, `seance`, `rendu` (oui/non), `note_sur_20`, `fichier`,
  `observations`. → onglet *Suivi_Séances*
- **Quiz** : `module`, `titre`, `bareme`. **Question** / **Choix** (importables depuis le GIFT S1).
  **TentativeQuiz** : `inscription`, `quiz`, `score`, `date`.
- **EvaluationCompetence** : `inscription`, `competence`, `auto_eval` (1–4),
  `eval_formateur` (1–4), `valide`. → onglet *Compétences*
- **EvaluationProjet** : `inscription`, 6 critères pondérés (Acquisition 20 %, Modélisation 25 %,
  Stats spatiales 15 %, Alerte 20 %, Cartographie 10 %, Reproductibilité 10 %) → `note_projet_20`.
  → onglet *Projet_Final*
- **Soutenance** : `inscription`, `note_sur_20`.

### Synthèse (calculée, non stockée)

Le **tableau de bord** recalcule à la volée (comme l'onglet *Tableau_de_bord*) :
taux de présence · note moyenne séances · compétences validées (x/24) · niveau moyen (1–4) ·
note projet · note soutenance · **NOTE GLOBALE = 40 % continu + 40 % projet + 20 % soutenance**.

---

## 3. Écrans (interface)

### Côté apprenant

| Écran | Contenu |
|---|---|
| Connexion / création de compte | Auth sécurisée, vérification e-mail, mot de passe oublié |
| **Tableau de bord** | Progression %, note globale, compétences validées, taux de présence, prochaine séance |
| Mon cours | 12 modules → séances ; marquer une séance « terminée » (progression) |
| Séance | Cours, ressources (PDF), **notebook + bouton Colab**, dépôt du livrable |
| Quiz | Passer le test du module, voir sa note et la correction |
| Mes compétences | Auto-évaluation 1–4 par compétence, niveau formateur, validation |
| Mon projet / soutenance | Grille du projet, notes reçues |
| Profil & prérequis | Infos participant + cases prérequis (GEE, GitHub, QGIS…) |

### Côté formateur / admin

| Écran | Contenu |
|---|---|
| Apprenants | Inscrire / gérer les apprenants d'une promo |
| Présence | Saisie par séance (48) — Présent/Retard/Excusé/Absent |
| Correction | Livrables : note /20 + observations |
| Compétences | Saisie du niveau formateur (1–4), validation |
| Projet & soutenance | Grille pondérée + note de soutenance |
| **Admin Django** | Édition du contenu (modules, séances, quiz, ressources) sans coder |

---

## 4. Structure du projet (dépôt Git)

```
2KPI_LEARN/
├── manage.py
├── passenger_wsgi.py        # point d'entrée exigé par cPanel/Passenger
├── requirements.txt
├── .env.example             # variables (SECRET_KEY, DB, e-mail) — jamais commité en vrai
├── .gitignore
├── config/                  # settings.py, urls.py, wsgi.py
├── apps/
│   ├── comptes/             # Profil, rôles, prérequis, auth
│   ├── formation/           # Formation, Module, Seance, Competence, Ressource
│   ├── evaluation/          # Quiz, Presence, Livrable, EvaluationCompetence, Projet, Soutenance
│   └── tableau_bord/        # calculs & pages de synthèse
├── templates/               # gabarits HTML (charte 2KPI)
├── static/                  # CSS/JS 2KPI
└── docs/ARCHITECTURE.md     # ce document
```

---

## 5. Déploiement (cPanel « Setup Python App »)

1. cPanel → **Setup Python App** → *Create* : Python 3.11, **Application root** = dossier du dépôt,
   **Application URL** = `learn.2kpinnov.org`, **startup file** = `passenger_wsgi.py`.
2. Créer la base **PostgreSQL** + l'utilisateur (cPanel) ; renseigner `.env`.
3. Dans le terminal de l'app (virtualenv fourni) : `pip install -r requirements.txt`,
   `python manage.py migrate`, `python manage.py collectstatic`, créer le super-utilisateur.
4. Charger les données de départ (12 modules, 24 compétences, 48 séances, questions S1) via un
   script d'import (fourni) réutilisant le `.csv` et le `.gift` déjà produits.
5. **Restart** de l'application → le site répond sur `learn.2kpinnov.org`.

> Rôle & sécurité : je fournis tout le code et les scripts ; **toi** tu crées la base, saisis les
> secrets (`.env`), déploies et crées les comptes réels. Je ne manipule ni mots de passe ni
> identifiants.

---

## 6. Feuille de route

| Phase | Contenu | Résultat |
|---|---|---|
| **A — Fondations** | Projet Django + `passenger_wsgi.py` + auth + modèles + admin + import des données GéoAI | Contenu éditable, « ça tourne » sur Passenger |
| **B — Apprenant** | Tableau de bord, cours, séance, quiz, notebooks/Colab | L'apprenant suit et est noté |
| **C — Formateur** | Présence, correction, compétences, projet, soutenance | Le formateur pilote le suivi |
| **D — Finition** | Charte 2KPI, e-mails, RGPD, lien depuis la vitrine | Prêt pour la 1re promo |

Réemploi : la structure des 12 modules, le référentiel de compétences (`referentiel_competences_geoai.csv`)
et les 22 questions (`Test_S1_banque_questions.gift`) déjà produits alimentent directement la
Phase A (scripts d'import).
