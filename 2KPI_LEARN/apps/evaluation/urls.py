from django.urls import path
from . import views

app_name = "evaluation"
urlpatterns = [
    path("quiz/<int:quiz_id>/", views.quiz, name="quiz"),
    path("quiz/<int:quiz_id>/resultats/", views.quiz_resultats, name="quiz_resultats"),
    path("livrables/", views.livrables, name="livrables"),
    path("livrables/<int:pk>/fichier/", views.livrable_fichier, name="livrable_fichier"),
]
