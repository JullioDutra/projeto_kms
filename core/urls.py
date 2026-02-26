from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('registrar/', views.registrar_km, name='registrar'),
    path('historico/', views.historico, name='historico'),
    path('ranking-geral/', views.ranking_geral, name='ranking_geral'),
    path('desempenho/', views.desempenho, name='desempenho'),
    path('feed/', views.feed_atividades, name='feed'),
    path('rotas/', views.listar_rotas, name='listar_rotas'),
    path('rotas/criar/', views.criar_rota, name='criar_rota'),
    path('rotas/<int:id>/', views.ver_rota, name='ver_rota'),
    path('rotas/<int:id>/excluir/', views.excluir_rota, name='excluir_rota'),
    path('editar-descricao/<int:id>/', views.editar_descricao, name='editar_descricao'),
    # --- ARENA DE DESAFIOS ---
    path('arena/', views.arena_desafios, name='arena_desafios'),
    path('arena/novo/', views.criar_desafio, name='criar_desafio'),
    path('arena/responder/<int:desafio_id>/<str:resposta>/', views.responder_desafio, name='responder_desafio'),
    # NOVAS ROTAS DO STRAVA
    path('strava/login/', views.strava_login, name='strava_login'),
    path('strava/callback/', views.strava_callback, name='strava_callback'),
]
