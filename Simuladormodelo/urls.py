from django.urls import path
from . import views

app_name = "simulador"

urlpatterns = [
    path("", views.formulario, name="formulario"),
    path("resultado/", views.resultado, name="resultado"),
    path("vscalc/", views.vscalc, name="vscalc"),
]