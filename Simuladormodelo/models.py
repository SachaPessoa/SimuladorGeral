from django.conf import settings
from django.db import models


class Simulacao(models.Model):
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    criada_em = models.DateTimeField(auto_now_add=True)
    entradas = models.JSONField()
    resumo = models.JSONField()

    class Meta:
        ordering = ["-criada_em"]

    def __str__(self):
        return f"Simulação {self.id} - {self.usuario} - {self.criada_em:%d/%m/%Y %H:%M}"