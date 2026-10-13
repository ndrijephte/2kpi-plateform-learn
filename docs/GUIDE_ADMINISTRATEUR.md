# 👤 Guide administrateur — comptes, rôles, inscriptions

Comment créer ton compte super-admin, puis les comptes des apprenants et des enseignants, et
comment les personnes arrivent sur la plateforme **https://learn.2kpinnov.org**.

---

## Les trois rôles

| Rôle (dans l'app) | Qui | Ce qu'il fait |
|---|---|---|
| **Apprenant** | apprenants, étudiants | suit ses cours, son agenda, ses quiz, dépose ses livrables — **uniquement** après rattachement à une promotion |
| **Formateur** | les **enseignants** | anime **ses** promotions : planning, présences, correction, ressources de ses formations |
| **Administrateur** | toi, l'équipe 2KPI | pilote tout : utilisateurs, promotions, candidatures, paramètres |

Un **super-utilisateur** (créé par `createsuperuser`) est toujours administrateur, avec en plus
l'accès complet à `/admin/` (l'administration technique de Django).

---

## 1. Créer ton compte super-admin (une seule fois)

Dans le **Terminal** cPanel :

```bash
source ~/virtualenv/repositories/2kpi-plateform-learn/2KPI_LEARN/*/bin/activate
cd ~/repositories/2kpi-plateform-learn/2KPI_LEARN
python manage.py createsuperuser
```

La commande demande :
- **Identifiant** : ex. `jephte` ;
- **Adresse e-mail** : ⚠️ **obligatoire en pratique**. Sans e-mail sur le compte, « Mot de passe
  oublié » ne peut **jamais** envoyer de lien (et la page affiche quand même « e-mail envoyé ») ;
- **Mot de passe** (deux fois ; rien ne s'affiche pendant la saisie, c'est normal).

Connexion ensuite sur https://learn.2kpinnov.org/login/ avec l'identifiant **ou** l'e-mail.

**Le compte existe déjà ?** Le passer super-admin et lui donner son e-mail :

```bash
python manage.py shell -c "from django.contrib.auth import get_user_model as U; u=U().objects.get(username='IDENTIFIANT'); u.email='prenom.nom@2kpinnov.org'; u.is_superuser=u.is_staff=True; u.save(); print('ok', u.username)"
```

**Voir tous les comptes et leurs e-mails** (utile si « mot de passe oublié » ne trouve personne) :

```bash
python manage.py shell -c "from django.contrib.auth import get_user_model as U; [print(u.username, repr(u.email), 'actif' if u.is_active else 'INACTIF') for u in U().objects.order_by('username')]"
```

---

## 2. Créer un apprenant ou un enseignant (dans la plateforme)

Connecté en administrateur :

1. Menu de gauche **Pilotage → Utilisateurs**.
2. Déplie **« + Nouveau compte »**.
3. Renseigne prénom, nom, **e-mail** (unique), identifiant de connexion, puis le **Rôle** :
   - **Apprenant** → choisis aussi sa **Promotion** : c'est elle qui ouvre l'accès aux cours ;
   - **Formateur** → pour un enseignant ; affecte-le ensuite à ses promotions
     (**Promotions** → colonne *Formateur* de la promotion, ou à la création d'une promotion) ;
   - **Administrateur** → mêmes droits que toi.
4. Saisis un **mot de passe provisoire** → **Créer le compte**.
5. Transmets identifiant et mot de passe provisoire à la personne ; elle le change depuis
   **Mon profil → Changer mon mot de passe** (ou via « Mot de passe oublié »).

Toujours dans **Utilisateurs** : changer un rôle, rattacher / détacher d'une promotion,
désactiver / réactiver un compte, et **modifier toutes les informations** d'un compte (bouton
d'édition de la ligne : identité, e-mail, rôle, promotion, statut d'inscription, nouveau mot de passe).

> Tu ne peux ni retirer ton propre rôle d'administrateur ni désactiver ton propre compte
> (garde-fou contre le verrouillage).

---

## 3. Les autres façons d'arriver sur la plateforme

### a) L'apprenant / l'étudiant crée lui-même son compte

Site vitrine → **Espace apprenant → Créer mon compte** (ou https://learn.2kpinnov.org/creer-mon-compte/).
Il indique s'il est **Étudiant(e)** ou **Professionnel(le)**, ses coordonnées, son université ou sa
structure, et peut choisir une **session**.

- Le compte est créé et connecté aussitôt (rôle Apprenant), un e-mail de bienvenue part, et les
  administrateurs reçoivent une notification.
- **Aucun contenu n'est accessible** tant que l'inscription n'est pas validée.
- S'il a choisi une session, une **candidature** apparaît dans **Candidatures** → l'accepter le
  rattache à la promotion (son espace s'ouvre, il est prévenu par e-mail).
- Sans session choisie : rattache-le toi-même dans **Utilisateurs** (colonne Promotion).

Protections : piège anti-robots, 5 créations de compte par heure et par connexion, e-mail unique.

### b) La demande d'inscription depuis la vitrine

Page **Sessions → S'inscrire** de la vitrine : la demande arrive dans **Candidatures**.
**Accepter** (en choisissant la promotion) crée le compte s'il n'existe pas, l'inscrit et envoie
un e-mail avec un lien pour **choisir son mot de passe** (valable 3 jours ; ensuite : « Mot de
passe oublié »). **Refuser** envoie un e-mail de refus (motif facultatif).

---

## 4. « Mot de passe oublié » : si un utilisateur ne reçoit rien

Par conception, la page affiche toujours « e-mail envoyé » (pour ne pas révéler quels comptes
existent). Pour savoir ce qui s'est réellement passé, dans le Terminal :

```bash
python manage.py tester_email adresse.de.la.personne@exemple.org --reinitialisation
grep -iE "mot de passe oublié|SMTP|sendmail|limite" logs/2kpi_learn.log | tail -20
```

| Le diagnostic dit | Signification | Solution |
|---|---|---|
| `✘ Aucun compte n'a cette adresse` | le compte a un autre e-mail, ou aucun | corrige l'e-mail du compte (Utilisateurs → édition) |
| `compte … : DÉSACTIVÉ` | compte désactivé | réactive-le dans Utilisateurs |
| `limite horaire atteinte` (journal) | plus de 3 demandes en une heure pour cette adresse | attendre 1 h |
| `✘ Échec SMTP` puis `✔ sendmail` | SMTP bloqué, le repli automatique prend le relais | rien à faire (ou `EMAIL_ENVOI=sendmail`) |
| `Mode console` | le `.env` du serveur n'a pas les réglages e-mail | compléter `EMAIL_*` puis Restart |
| tout en ✔ mais rien reçu | l'e-mail est filtré | dossier spam ; cPanel › *Email Deliverability* (SPF, DKIM) |

En dépannage, tu peux aussi définir un nouveau mot de passe toi-même : **Utilisateurs →
édition du compte → Nouveau mot de passe**.
