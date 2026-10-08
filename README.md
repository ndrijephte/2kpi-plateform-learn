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

- **Inscription depuis la vitrine** → envoyée en POST à `https://learn.2kpinnov.org/api/candidatures/`
  (réglée dans `VITRINE_2KPI/js/inscription-config.js` › `LEARN_API_URL`). Les demandes arrivent
  dans l'app (**Candidatures**) ; l'admin « Accepte » → compte créé + inscription + e-mail.
- **Bouton « Espace apprenant »** du menu vitrine → `https://learn.2kpinnov.org/login/`.
- Côté app, les origines autorisées de la vitrine sont listées dans `.env` › `VITRINE_ORIGINS`.

## Développer en local (app)

```bash
cd 2KPI_LEARN
python -m venv .venv             # une seule fois
source .venv/bin/activate        # Windows : .venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate         # .env local en SQLite (DB_ENGINE vide)
python manage.py runserver
```

## Documentation

- Vitrine : `VITRINE_2KPI/DEPLOIEMENT.md`
- Application : `2KPI_LEARN/README.md`, `2KPI_LEARN/docs/ARCHITECTURE.md`,
  `2KPI_LEARN/docs/DEPLOIEMENT_cPanel.md`
