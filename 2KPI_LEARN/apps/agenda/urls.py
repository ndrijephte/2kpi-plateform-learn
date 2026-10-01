from django.urls import path
from . import views

app_name = "agenda"
urlpatterns = [
    path("", views.mon_agenda, name="mon_agenda"),
    path("notifications/", views.notifications, name="notifications"),
    path("notifications/envoyer/", views.envoyer, name="envoyer"),
    path("promotions/", views.promotions, name="promotions"),
    path("promotions/<int:promo_id>/generer/", views.generer_promo, name="generer_promo"),
    path("planning/<int:promo_id>/", views.planning, name="planning"),
    path("planning/<int:promo_id>/synchroniser/", views.synchroniser, name="synchroniser"),
    path("promotions/<int:promo_id>/acces/", views.acces_contenus, name="acces"),
    path("evenement/<int:ev_id>/action/", views.evenement_action, name="evenement_action"),
    path("evenement/<int:ev_id>/presences/", views.presences, name="presences"),
]
