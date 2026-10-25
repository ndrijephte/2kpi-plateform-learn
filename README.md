# PLATEFORME_2KPI

Dépôt Git **unique** regroupant les deux projets de la plateforme 2KPI —
GitHub : <https://github.com/ndrijephte/2kpi-plateform-learn>

```
PLATEFORME_2KPI/
├── .cpanel.yml     → Déploiement cPanel de la vitrine (lu à la racine du dépôt)
├── VITRINE_2KPI/   → Vitrine publique (HTML/CSS/JS statique)
│                     Déploiement : cPanel Git → public_html (2kpinnov.org)
└── 2KPI_LEARN/     → Espace apprenant (application Django)
                      Déploiement : cPanel « Setup Python App » (learn.2kpinnov.org)
```

L'historique des deux anciens dépôts (`2kpi-learn` et `2kpi-plateform`) a été conservé : chaque
commit apparaît désormais dans son sous-dossier (`git log -- 2KPI_LEARN`, `git log -- VITRINE_2KPI`).

## Travailler au quotidien

```bash
git status
git add -A
git commit -m "learn: …"   # préfixer par learn: / vitrine: / plateforme: aide à relire l'historique
git push
```

Une même modification qui touche la vitrine **et** l'app (ex. le formulaire d'inscription et
l'API de candidatures) peut désormais tenir dans **un seul commit**.

## Déploiement (cPanel)

**Automatique à chaque `git push` sur main** (tests puis mise en ligne vitrine + app) :
voir [`docs/DEPLOIEMENT_AUTOMATIQUE.md`](docs/DEPLOIEMENT_AUTOMATIQUE.md) — mise en place unique.

Un seul clone sur le serveur : `/home/c2864961c/repositories/2kpi-plateform-learn`.

- *Git Version Control* → *Update from Remote* → *Deploy HEAD Commit* : `.cpanel.yml` lance
  `deploy/deployer.sh` → vitrine copiée dans `public_html`, puis app (pip, sauvegarde + migrate,
  collectstatic, redémarrage). C'est exactement ce que fait GitHub Actions à chaque push.
- **App** : *Setup Python App* → **Application root** = `repositories/2kpi-plateform-learn/2KPI_LEARN`
  (installation initiale : `docs/GUIDE_DEPLOIEMENT_2KPI.md`).

## Comment la vitrine et l'app se parlent

- **Catalogue des sessions** → la vitrine lit `https://learn.2kpinnov.org/api/sessions/` : les
  sessions publiées dans l'app (**Sessions › Lancer une session**), avec places restantes calculées.
  Repli automatique sur `VITRINE_2KPI/js/sessions-data.js` si l'app ne répond pas.
- **Inscription depuis la vitrine** → envoyée en POST à `https://learn.2kpinnov.org/api/candidatures/`
  (réglée dans `VITRINE_2KPI/js/inscription-config.js` › `LEARN_API_URL`). Les demandes arrivent
  dans l'app (**Candidatures**) ; l'admin « Accepte » → compte créé + inscription + e-mail.
- **Menu « Espace apprenant »** de la vitrine → *Se connecter* (`/login/`) ou *Créer mon compte*
  (`/creer-mon-compte/`) : les apprenants et étudiants créent eux-mêmes leur compte ; la session
  choisie devient une candidature à accepter dans **Candidatures** (accès aux cours après validation).
- Côté app, les origines autorisées de la vitrine sont listées dans `.env` › `VITRINE_ORIGINS`.

## Développer en local (vitrine + app reliées)

Deux terminaux, depuis la racine `PLATEFORME_2KPI/` :

```bash
# 1) L'app sur http://127.0.0.1:8000
cd 2KPI_LEARN
python -m venv .venv && source .venv/bin/activate   # première fois ; ensuite : source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver

# 2) La vitrine sur http://127.0.0.1:5500
cd VITRINE_2KPI
python3 -m http.server 5500
```

Ouverte en local, la vitrine **bascule seule** vers l'app locale (`VITRINE_2KPI/js/learn-config.js`) :
catalogue lu sur `http://127.0.0.1:8000/api/sessions/`, inscriptions envoyées à
`…/api/candidatures/`, « Espace apprenant » vers `…/login/`.
Première fois : `python manage.py importer_sessions_vitrine` pour reprendre les sessions du site.
En ligne, elle utilise `learn.2kpinnov.org` — rien à modifier avant de déployer.
Côté app, le `.env` local doit autoriser la vitrine locale :
`VITRINE_ORIGINS=http://127.0.0.1:5500,http://localhost:5500`.

## Documentation

- **Administration (comptes super-admin, apprenants, enseignants, candidatures)** :
  `docs/GUIDE_ADMINISTRATEUR.md`
- Déploiement automatique (push → production) : `docs/DEPLOIEMENT_AUTOMATIQUE.md`
- Installation cPanel complète et dépannage : `docs/GUIDE_DEPLOIEMENT_2KPI.md`

- Vitrine : `VITRINE_2KPI/DEPLOIEMENT.md`
- Application : `2KPI_LEARN/README.md`, `2KPI_LEARN/docs/ARCHITECTURE.md`,
  `2KPI_LEARN/docs/DEPLOIEMENT_cPanel.md`
