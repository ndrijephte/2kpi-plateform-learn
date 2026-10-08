# Déploiement de la vitrine 2KPI

Workflow : **développement local → Git → GitHub → déploiement cPanel**.

## 1. Dépôt Git

La vitrine fait partie du **dépôt unique `PLATEFORME_2KPI`** (avec l'app `2KPI_LEARN`).
Toutes les commandes Git se lancent depuis la racine `PLATEFORME_2KPI/` :

```bash
git add -A
git commit -m "vitrine: décris ta modification"
git push
```

## 2. Déploiement sur l'hébergement (cPanel Git Version Control)

1. cPanel → **Git Version Control** : le clone `apps/2kpi_plateforme` du dépôt unique
   (créé une seule fois, voir `2KPI_LEARN/docs/DEPLOIEMENT_cPanel.md`, étape 3).
2. Onglet *Pull or Deploy* → **Update from Remote** puis **Deploy HEAD Commit**.
3. `.cpanel.yml` (à la **racine** du dépôt) copie `VITRINE_2KPI/` dans `public_html`
   → visible sur `https://2kpinnov.org`.

À chaque évolution : `git push` sur GitHub, puis *Update from Remote* + *Deploy* dans cPanel.
(Automatisable plus tard via un webhook ou GitHub Actions.)

## Notes

- Les images héritées inutilisées de l'ancienne démo (~50 Mo) sont exclues via `.gitignore` :
  le dépôt et le déploiement restent légers.
- L'espace apprenant est l'app Django `2KPI_LEARN/` (sous-domaine `learn.2kpinnov.org`), dans le
  même dépôt mais déployée via « Setup Python App » — voir `2KPI_LEARN/docs/DEPLOIEMENT_cPanel.md`.
