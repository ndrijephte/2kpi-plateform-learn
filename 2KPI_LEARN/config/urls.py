from django.contrib import admin
from django.conf import settings
from django.urls import include, path, re_path
from apps.agenda.api import sessions as sessions_api
from apps.comptes.api import candidature as candidature_api
from apps.core.views import media_publique
from django.contrib.auth import views as auth_views

admin.site.site_header = "2KPI Learn — Administration"
admin.site.site_title = "2KPI Learn"
admin.site.index_title = "Gestion de la plateforme"
admin.site.site_url = "/"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("comptes/", include("apps.comptes.urls")),
    path("login/", auth_views.LoginView.as_view(), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("mot-de-passe/changer/", auth_views.PasswordChangeView.as_view(), name="password_change"),
    path("mot-de-passe/change/", auth_views.PasswordChangeDoneView.as_view(), name="password_change_done"),
    path("mot-de-passe/oublie/", auth_views.PasswordResetView.as_view(), name="password_reset"),
    path("mot-de-passe/envoye/", auth_views.PasswordResetDoneView.as_view(), name="password_reset_done"),
    path("reinitialiser/<uidb64>/<token>/", auth_views.PasswordResetConfirmView.as_view(), name="password_reset_confirm"),
    path("reinitialiser/termine/", auth_views.PasswordResetCompleteView.as_view(), name="password_reset_complete"),
    path("formation/", include("apps.formation.urls")),
    path("evaluation/", include("apps.evaluation.urls")),
    path("agenda/", include("apps.agenda.urls")),
    path("parametres/", include("apps.core.urls")),
    path("api/candidatures/", candidature_api, name="api_candidatures"),
    path("api/sessions/", sessions_api, name="api_sessions"),
    path("", include("apps.tableau_bord.urls")),
]

# media/ public (logo, image de connexion, photos) : servi par Django en dev comme en production
urlpatterns.insert(0, re_path(r"^media/(?P<chemin>.+)$", media_publique, name="media_publique"))
