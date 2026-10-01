from django.contrib import admin
from .models import Formation, Module, Seance, Competence, Ressource

class SeanceInline(admin.TabularInline):
    model = Seance
    extra = 0

class CompetenceInline(admin.TabularInline):
    model = Competence
    extra = 0

@admin.register(Formation)
class FormationAdmin(admin.ModelAdmin):
    list_display = ("titre", "active")
    prepopulated_fields = {"slug": ("titre",)}

@admin.register(Module)
class ModuleAdmin(admin.ModelAdmin):
    list_display = ("code", "titre", "formation", "ordre")
    list_filter = ("formation",)
    ordering = ("ordre",)
    inlines = [CompetenceInline, SeanceInline]

@admin.register(Seance)
class SeanceAdmin(admin.ModelAdmin):
    list_display = ("module", "ordre", "theme", "semaine", "jour", "heure_debut", "duree_prevue_h", "mode")
    list_filter = ("module__formation", "jour", "mode")

@admin.register(Competence)
class CompetenceAdmin(admin.ModelAdmin):
    list_display = ("code", "libelle", "module", "niveau_vise")
    list_filter = ("module__formation",)

@admin.register(Ressource)
class RessourceAdmin(admin.ModelAdmin):
    list_display = ("titre", "type", "seance", "module", "ajoute_par", "date_ajout")
    list_filter = ("type",)
    search_fields = ("titre", "instructions")
