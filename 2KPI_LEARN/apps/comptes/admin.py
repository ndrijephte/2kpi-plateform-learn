from django.contrib import admin
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
