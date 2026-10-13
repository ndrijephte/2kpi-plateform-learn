# Déploiement automatique : `git push` → production (cPanel)

À chaque `git push` sur **main**, GitHub met en ligne la vitrine **et** l'application, sans
passer par cPanel :

```
git push ──▶ GitHub Actions
              1. Tests (50 tests Django, migrations à jour)      ✘ → rien n'est déployé
              2. API cPanel : « Update from Remote »              (le clone du serveur récupère le commit)
              3. API cPanel : « Deploy HEAD Commit »              → .cpanel.yml → deploy/deployer.sh
                   • vitrine copiée dans public_html
                   • pip install (seulement si requirements.txt a changé)
                   • sauvegarde de la base PUIS migrate (seulement s'il y a de nouvelles migrations)
                   • collectstatic, contrôle Django, redémarrage de l'app (tmp/restart.txt)
              4. Contrôle : learn.2kpinnov.org et 2kpinnov.org répondent 200
```

Suivi : GitHub › onglet **Actions** (un mail GitHub te prévient en cas d'échec).
Journal côté serveur : `2KPI_LEARN/logs/deploiement.log`.

Fichiers concernés : `.github/workflows/deploiement.yml`, `.cpanel.yml`, `deploy/deployer.sh`.

---

## Mise en place (une seule fois, ~10 minutes)

### 1. Créer un jeton d'API cPanel

1. cPanel → rubrique **Sécurité** → **Gérer les jetons d'API** (*Manage API Tokens*).
2. **Créer** → nom : `github-deploiement` → pas de date d'expiration (ou 1 an, à renouveler).
3. **Copie le jeton affiché** (il ne sera plus jamais montré).

> Rubrique absente ? L'hébergeur a désactivé les jetons : demande-lui de l'activer, ou utilise
> l'alternative SSH en bas de page.

### 2. Déclarer les secrets dans GitHub

Dépôt `ndrijephte/2kpi-plateform-learn` → **Settings** → **Secrets and variables** → **Actions**
→ **New repository secret**, trois fois. Chaque secret a deux champs : **Name** (le nom ci-dessous,
en majuscules) et **Secret** (la valeur seule, sans `:` ni guillemets) :

| Nom | Valeur |
|---|---|
| `CPANEL_HOST` | `2kpinnov.org` (vérifié : cPanel répond sur le port 2083 avec un certificat valide) — de façon générale, le nom du serveur cPanel, tel qu'il apparaît dans l'adresse de connexion à cPanel, **sans** `https://` ni `:2083` (ex. `2kpinnov.org` ou `serveurXX.hebergeur.com`) |
| `CPANEL_USER` | `c2864961c` |
| `CPANEL_TOKEN` | le jeton copié à l'étape 1 |

Le chemin du clone sur le serveur vaut par défaut `/home/c2864961c/repositories/2kpi-plateform-learn`.
S'il est différent : onglet **Variables** → `CPANEL_REPO` = le chemin exact
(cPanel › Contrôle de version Git › colonne *Chemin du dépôt*).

### 3. Préparer le serveur (une fois)

Dans le **Terminal** cPanel :

```bash
cd ~/repositories/2kpi-plateform-learn
git status            # doit indiquer « nothing to commit, working tree clean »
git checkout -- .     # sinon : annule les modifications faites à la main sur le serveur
```

Un clone « sale » (fichier modifié sur le serveur) bloque l'*Update from Remote* : c'est la
première cause d'échec. Les fichiers propres au serveur (`.env`, `media/`, `prive/`, `logs/`,
`staticfiles/`, `tmp/`) sont ignorés par Git et ne gênent pas.

### 4. Premier déploiement

GitHub → **Actions** → *Tests et mise en production* → **Run workflow** (ou simplement un `git push`).
Les 4 étapes doivent passer au vert. C'est tout : ensuite, chaque push sur main est mis en ligne.

---

## Au quotidien

```bash
python manage.py test        # facultatif : GitHub les relance de toute façon
git add -A && git commit -m "learn: …" && git push
```

- Tests en échec → **rien n'est déployé**, la production reste intacte.
- Pour une modification sans déploiement : travaille sur une autre branche, puis fusionne dans main.
- Le `.env` du serveur n'est **jamais** touché : une nouvelle variable de configuration s'ajoute à
  la main (Gestionnaire de fichiers), puis *Run workflow* ou *Setup Python App › Restart*.

## Si le déploiement échoue

| Étape rouge | Cause probable | Solution |
|---|---|---|
| *Vérifier la configuration* | Secret absent ou mal saisi : le message nomme le secret fautif et sa longueur (jamais sa valeur) | Étape 2. Ex. vécu : `CPANEL_USER invalide (32 caractères)` = le jeton collé dans `CPANEL_USER` (secrets inversés) |
| *Récupérer le commit* — `401` / `Access denied` | Jeton faux/expiré, ou `CPANEL_USER` faux | Recrée le jeton (étape 1) |
| *Récupérer le commit* — connexion impossible | `CPANEL_HOST` faux, ou port 2083 filtré | Mets le nom exact du serveur cPanel ; sinon alternative SSH |
| *Récupérer le commit* — refus de mise à jour | Fichier modifié sur le serveur | Étape 3 (`git checkout -- .`) |
| *Déployer* | Erreur dans pip / migrate / collectstatic | Les **journaux du serveur s'affichent dans GitHub** (annotations de l'étape) ; sinon `2KPI_LEARN/logs/deploiement.log` |
| *Contrôler les sites* — 500 | L'app ne démarre pas | `logs/2kpi_learn.log` ; Setup Python App › onglet Log |

Relancer à la main sur le serveur (même effet que le déploiement automatique) :
`bash ~/repositories/2kpi-plateform-learn/deploy/deployer.sh`

## Alternative : par SSH

Si l'hébergeur n'autorise ni les jetons d'API ni l'accès au port 2083 depuis GitHub, mais autorise
SSH : remplace les étapes 2 et 3 du job `production` par une connexion SSH (action
`appleboy/ssh-action`) qui exécute :

```bash
cd ~/repositories/2kpi-plateform-learn && git fetch origin main && git reset --hard origin/main \
  && bash deploy/deployer.sh
```

(clé SSH privée dans un secret `SSH_KEY`, clé publique autorisée dans cPanel › Accès SSH).
