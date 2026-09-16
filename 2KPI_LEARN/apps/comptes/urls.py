from django.urls import path
from . import views

app_name = "comptes"
urlpatterns = [
    path("profil/", views.profil, name="profil"),
]
