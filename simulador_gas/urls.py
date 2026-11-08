from django.urls import path

from . import views

app_name = "simulador_gas"

urlpatterns = [
    path("", views.gas_home, name="home"),
    path("calcular/", views.gas_calcular, name="calcular"),
    path("resultado/", views.gas_results, name="results"),
    path("mollier-cache/", views.mollier_cache, name="mollier_cache"),
    path("memoria-calculo/", views.gas_calculation_memory, name="calculation_memory"),
]
