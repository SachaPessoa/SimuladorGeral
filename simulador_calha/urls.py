from django.urls import path

from . import views

app_name = 'simulador_calha'

urlpatterns = [
    path('', views.simuladores, name='home'),
]
