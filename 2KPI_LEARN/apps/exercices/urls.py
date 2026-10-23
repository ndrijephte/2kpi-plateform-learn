from django.urls import path
from . import views

app_name = "exercices"
urlpatterns = [
    path("", views.liste, name="liste"),
    path("<int:pk>/", views.exercice, name="exercice"),
    path("<int:exercice_pk>/questions/ajouter/", views.question, name="question_ajouter"),
    path("<int:exercice_pk>/questions/<int:pk>/", views.question, name="question"),
    path("<int:exercice_pk>/questions/<int:pk>/supprimer/", views.question_supprimer, name="question_supprimer"),
    path("planifies/<int:pk>/suivi/", views.suivi, name="suivi"),
    path("copies/<int:pk>/", views.corriger, name="corriger"),
    path("planifies/<int:pk>/faire/", views.faire, name="faire"),
    path("planifies/<int:pk>/resultat/", views.resultat_apprenant, name="resultat"),
]
