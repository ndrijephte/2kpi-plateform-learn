from django.contrib import admin
from apps.core.permissions import appliquer_role
from .models import Profil, Prerequis

class PrerequisInline(admin.StackedInline):
    model = Prerequis
    can_delete = False

@admin.register(Profil)
class ProfilAdmin(admin.ModelAdmin):
    list_display = ("utilisateur", "role", "structure", "telephone")
    list_filter = ("role",)
    search_fields = ("utilisateur__username", "utilisateur__first_name",
                     "utilisateur__last_name", "structure")
    inlines = [PrerequisInline]

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        appliquer_role(obj.utilisateur, obj.role)  # garde l'accès admin Django cohérent avec le rôle
