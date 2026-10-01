from django.urls import path
from . import views

app_name = "comptes"
urlpatterns = [
    path("profil/", views.profil, name="profil"),
    path("profil/modifier/", views.profil_modifier, name="profil_modifier"),
    path("utilisateurs/", views.utilisateurs, name="utilisateurs"),
    path("utilisateurs/<int:pk>/", views.utilisateur_modifier, name="utilisateur_modifier"),
    path("utilisateurs/<int:pk>/editer/", views.utilisateur_editer, name="utilisateur_editer"),
    path("candidatures/", views.candidatures, name="candidatures"),
]
