from django.urls import path
from . import views

app_name = "formation"
urlpatterns = [
    path("modules/", views.liste_modules, name="modules"),
    path("modules/<str:code>/", views.detail_module, name="module_detail"),
    path("seance/<int:pk>/", views.detail_seance, name="seance"),
]
