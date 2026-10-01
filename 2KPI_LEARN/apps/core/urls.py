from django.urls import path
from . import views

app_name = "core"
urlpatterns = [
    path("", views.accueil, name="parametres"),
    path("formations/", views.formations, name="formations"),
    path("formations/<int:pk>/", views.formation, name="formation"),
    path("modules/<int:pk>/", views.module, name="module"),
    path("calendrier/", views.calendrier, name="calendrier"),
    path("quiz/", views.quiz_liste, name="quiz_liste"),
    path("quiz/<int:pk>/", views.quiz, name="quiz"),
    path("quiz/<int:quiz_pk>/questions/ajouter/", views.question, name="question_ajouter"),
    path("quiz/<int:quiz_pk>/questions/<int:pk>/", views.question, name="question"),
    path("modifier/<str:modele>/<int:pk>/", views.modifier, name="modifier"),
    path("supprimer/<str:modele>/<int:pk>/", views.supprimer, name="supprimer"),
    path("<slug:section>/", views.section, name="section"),
]
