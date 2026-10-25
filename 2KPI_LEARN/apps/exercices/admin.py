from django.contrib import admin
from .models import Choix, Copie, Exercice, Planification, Question, Reponse


class ChoixInline(admin.TabularInline):
    model = Choix
    extra = 0


@admin.register(Exercice)
class ExerciceAdmin(admin.ModelAdmin):
    list_display = ("titre", "module", "auteur", "modifie_le")
    list_filter = ("module__formation",)


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ("__str__", "exercice", "type", "points")
    list_filter = ("type",)
    inlines = [ChoixInline]


@admin.register(Planification)
class PlanificationAdmin(admin.ModelAdmin):
    list_display = ("exercice", "promotion", "ouverture", "date_limite")
    list_filter = ("promotion",)


class ReponseInline(admin.TabularInline):
    model = Reponse
    extra = 0


@admin.register(Copie)
class CopieAdmin(admin.ModelAdmin):
    list_display = ("inscription", "planification", "enregistree_le")
    inlines = [ReponseInline]
