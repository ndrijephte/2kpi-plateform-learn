from django.urls import path
from . import views

app_name = "tableau_bord"
urlpatterns = [
    path("", views.accueil, name="accueil"),
]
