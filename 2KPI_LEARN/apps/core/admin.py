from django.contrib import admin
from .models import Parametres


@admin.register(Parametres)
class ParametresAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return not Parametres.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False
