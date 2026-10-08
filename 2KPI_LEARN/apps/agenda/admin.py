from django.contrib import admin
from django.contrib import messages
from .models import AccesModule, Annonce, Promotion, Indisponibilite, Evenement, Notification
from .services import generer_agenda

class IndispoInline(admin.TabularInline):
    model = Indisponibilite
    extra = 0

@admin.register(Promotion)
class PromotionAdmin(admin.ModelAdmin):
    list_display = ("nom", "formation", "date_debut", "formateur", "active", "publiee_vitrine")
    list_filter = ("active", "publiee_vitrine", "formation")
    fieldsets = [
        (None, {"fields": ["nom", "formation", "date_debut", "formateur", "active", "ouverture_auto"]}),
        ("Site vitrine", {"fields": ["publiee_vitrine", "code_vitrine", "domaine", "mode", "date_affichage",
                                     "horaire", "duree", "lieu", "places_total", "places_hors_plateforme",
                                     "prix", "description_vitrine"]}),
    ]
    inlines = [IndispoInline]
    actions = ["action_generer_agenda"]

    @admin.action(description="Générer l'agenda (12 semaines) à partir de la date de début")
    def action_generer_agenda(self, request, queryset):
        total = 0
        for promo in queryset:
            total += generer_agenda(promo)
        self.message_user(request, f"{total} événements générés.", messages.SUCCESS)

@admin.register(Evenement)
class EvenementAdmin(admin.ModelAdmin):
    list_display = ("date_debut", "libelle", "promotion", "statut", "mode", "duree_h")
    list_filter = ("promotion", "statut", "mode")
    date_hierarchy = "date_debut"

@admin.register(Indisponibilite)
class IndispoAdmin(admin.ModelAdmin):
    list_display = ("date_debut", "date_fin", "motif", "promotion")

@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("titre", "destinataire", "expediteur", "type", "lu", "date_creation")
    list_filter = ("type", "lu")


@admin.register(Annonce)
class AnnonceAdmin(admin.ModelAdmin):
    list_display = ("titre", "expediteur", "cible", "promotion", "nb_destinataires", "date_envoi")
    list_filter = ("cible",)


@admin.register(AccesModule)
class AccesModuleAdmin(admin.ModelAdmin):
    list_display = ("module", "promotion", "etat", "modifie_par", "modifie_le")
    list_filter = ("etat", "promotion")
