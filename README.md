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

Un seul clone sur le serveur, ex. `/home/c2864961c/apps/2kpi_plateforme` :

- **Vitrine** : *Git Version Control* → *Update from Remote* → *Deploy HEAD Commit*.
  `.cpanel.yml` copie `VITRINE_2KPI/` dans `public_html`.
- **App** : *Setup Python App* → **Application root** = `apps/2kpi_plateforme/2KPI_LEARN`.
  Après un *Update from Remote* : migrations / collectstatic puis *Restart*
  (voir `2KPI_LEARN/docs/DEPLOIEMENT_cPanel.md`).

## Comment la vitrine et l'app se parlent

- **Catalogue des sessions** → la vitrine lit `https://learn.2kpinnov.org/api/sessions/` : les
  promotions publiées dans l'app (**Promotions › Vitrine**), avec places restantes calculées.
  Repli automatique sur `VITRINE_2KPI/js/sessions-data.js` si l'app ne répond pas.
- **Inscription depuis la vitrine** → envoyée en POST à `https://learn.2kpinnov.org/api/candidatures/`
  (réglée dans `VITRINE_2KPI/js/inscription-config.js` › `LEARN_API_URL`). Les demandes arrivent
  dans l'app (**Candidatures**) ; l'admin « Accepte » → compte créé + inscription + e-mail.
- **Bouton « Espace apprenant »** du menu vitrine → `https://learn.2kpinnov.org/login/`.
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

- Vitrine : `VITRINE_2KPI/DEPLOIEMENT.md`
- Application : `2KPI_LEARN/README.md`, `2KPI_LEARN/docs/ARCHITECTURE.md`,
  `2KPI_LEARN/docs/DEPLOIEMENT_cPanel.md`
