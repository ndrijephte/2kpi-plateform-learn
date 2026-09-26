from django.urls import path
from . import views

app_name = "agenda"
urlpatterns = [
    path("", views.mon_agenda, name="mon_agenda"),
    path("notifications/", views.notifications, name="notifications"),
    path("planning/<int:promo_id>/", views.planning, name="planning"),
    path("evenement/<int:ev_id>/action/", views.evenement_action, name="evenement_action"),
]
