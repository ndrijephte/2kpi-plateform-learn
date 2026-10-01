from django.urls import path
from . import views

app_name = "formation"
urlpatterns = [
    path("modules/", views.liste_modules, name="modules"),
    path("modules/<str:code>/", views.detail_module, name="module_detail"),
    path("seance/<int:pk>/", views.detail_seance, name="seance"),
    path("ressources/", views.ressources, name="ressources"),
    path("ressources/ajouter/", views.ressource_editer, name="ressource_ajouter"),
    path("ressources/<int:pk>/modifier/", views.ressource_editer, name="ressource_modifier"),
    path("ressources/<int:pk>/supprimer/", views.ressource_supprimer, name="ressource_supprimer"),
    path("ressources/<int:pk>/fichier/", views.ressource_fichier, name="ressource_fichier"),
]
