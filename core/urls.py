from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('registrar/', views.registrar_km, name='registrar'),
    path('historico/', views.historico, name='historico'),
    path('ranking-geral/', views.ranking_geral, name='ranking_geral'),
]
