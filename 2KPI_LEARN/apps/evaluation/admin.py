from django.contrib import admin
from .models import (Inscription, Presence, Livrable, Quiz, Question, Choix,
                     TentativeQuiz, EvaluationCompetence, EvaluationProjet, Soutenance)

class ChoixInline(admin.TabularInline):
    model = Choix
    extra = 0

@admin.register(Inscription)
class InscriptionAdmin(admin.ModelAdmin):
    list_display = ("apprenant", "formation", "promotion", "statut", "date_debut", "date_fin_prevue")
    list_filter = ("formation", "promotion", "statut")
    search_fields = ("apprenant__username", "apprenant__first_name", "apprenant__last_name")

@admin.register(Presence)
class PresenceAdmin(admin.ModelAdmin):
    list_display = ("inscription", "evenement", "seance", "statut", "duree_realisee_h")
    list_filter = ("statut", "evenement__promotion", "seance__module")

@admin.register(Livrable)
class LivrableAdmin(admin.ModelAdmin):
    list_display = ("inscription", "seance", "rendu", "note_sur_20")
    list_filter = ("rendu", "seance__module")

@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ("intitule", "type", "quiz", "categorie")
    list_filter = ("type", "quiz")
    inlines = [ChoixInline]

@admin.register(Quiz)
class QuizAdmin(admin.ModelAdmin):
    list_display = ("titre", "module", "bareme")

@admin.register(EvaluationCompetence)
class EvaluationCompetenceAdmin(admin.ModelAdmin):
    list_display = ("competence", "inscription", "auto_eval", "eval_formateur", "valide")
    list_filter = ("valide", "competence__module")

@admin.register(EvaluationProjet)
class EvaluationProjetAdmin(admin.ModelAdmin):
    list_display = ("inscription", "note_sur_20")

@admin.register(Soutenance)
class SoutenanceAdmin(admin.ModelAdmin):
    list_display = ("inscription", "note_sur_20", "date")

admin.site.register(TentativeQuiz)
