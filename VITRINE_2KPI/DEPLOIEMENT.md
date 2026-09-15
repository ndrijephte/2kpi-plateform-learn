# Déploiement de la vitrine 2KPI

Workflow : **développement local → Git → GitHub → déploiement cPanel**.

## 1. Local (déjà fait)

Le dépôt Git a été initialisé et un **commit initial** existe déjà (branche `master`).

> ⚠️ Première étape sur TA machine — nettoyage : le dépôt a été créé depuis un
> environnement isolé qui n'a pas pu supprimer quelques fichiers verrous `.lock`.
> Depuis ton ordinateur (droits normaux), lance une fois, à la racine de `SITE_2KPI_V2/` :
>
> ```bash
> rm -f .git/HEAD.lock .git/index.lock .git/objects/maintenance.lock .git/refs/heads/master.lock
> git branch -M main          # renommer la branche en main
> git status                  # doit afficher "working tree clean", sans avertissement
> ```
>
> *Alternative propre* : supprime le dossier `.git`, puis refais tout toi-même —
> `git init && git add -A && git commit -m "Version initiale du site vitrine 2KPI"`.

Ensuite, cycle de travail habituel :

```bash
git add -A
git commit -m "Décris ta modification"
git push
```

## 2. GitHub (à faire une fois)

1. Crée un dépôt vide sur GitHub (ex. `2kpi-site`), **sans** README ni .gitignore.
2. Relie le dépôt local et pousse :

```bash
git remote add origin https://github.com/TON_COMPTE/2kpi-site.git
git branch -M main
git push -u origin main
```

> C'est **toi** qui crées le dépôt et t'authentifies auprès de GitHub (Claude ne manipule
> pas tes identifiants).

## 3. Déploiement sur l'hébergement (cPanel Git Version Control)

1. cPanel → **Git Version Control** → *Create* → colle l'URL du dépôt GitHub → clone.
2. Ouvre `.cpanel.yml` (à la racine du dépôt) et remplace **`CPANEL_USER`** par ton
   nom d'utilisateur cPanel réel.
3. Dans cPanel → Git Version Control → onglet *Pull or Deploy* → **Update from Remote**
   puis **Deploy HEAD Commit**.
3. La vitrine est copiée dans `public_html` → visible sur `https://2kpinnov.org`.

À chaque évolution : `git push` sur GitHub, puis *Update from Remote* + *Deploy* dans cPanel.
(Automatisable plus tard via un webhook ou GitHub Actions.)

## Notes

- Les images héritées inutilisées de l'ancienne démo (~50 Mo) sont exclues via `.gitignore` :
  le dépôt et le déploiement restent légers.
- L'espace apprenant **Moodle** est séparé (sous-domaine `learn.2kpinnov.org`) et ne se déploie
  pas par ce dépôt — voir `FORMATION_GeoAI/Moodle_2KPI/`.
