from django.contrib import admin
from .models import Simulacao


@admin.register(Simulacao)
class SimulacaoAdmin(admin.ModelAdmin):
    list_display = ("id", "usuario", "criada_em")
    list_filter = ("criada_em", "usuario")