from django.contrib import admin
from .models import Atividade, MetaMensal, Rota, TokenStrava, Desafio, TempoRota

# ==========================================
# PAINEL DE ATIVIDADES E TREINOS
# ==========================================
@admin.register(Atividade)
class AtividadeAdmin(admin.ModelAdmin):
    # Colunas que vão aparecer na tabela
    list_display = ('nome_usuario', 'quantidade_km', 'tipo', 'pace', 'data_envio')
    # Filtros laterais (facilita muito a vida)
    list_filter = ('tipo', 'data_envio', 'nome_usuario')
    # Barra de pesquisa
    search_fields = ('nome_usuario', 'descricao', 'strava_id')
    # Navegação por datas no topo
    date_hierarchy = 'data_envio'

# ==========================================
# PAINEL DA META COLETIVA (O TANQUE)
# ==========================================
@admin.register(MetaMensal)
class MetaMensalAdmin(admin.ModelAdmin):
    list_display = ('mes', 'ano', 'objetivo_km')
    list_filter = ('ano', 'mes')
    search_fields = ('ano', 'mes')
    ordering = ('-ano', '-mes')

# ==========================================
# PAINEL DA COMUNIDADE: ROTAS E TEMPOS
# ==========================================
@admin.register(Rota)
class RotaAdmin(admin.ModelAdmin):
    list_display = ('nome', 'criador', 'distancia_estimada', 'data_criacao')
    list_filter = ('data_criacao', 'criador')
    search_fields = ('nome', 'criador')

@admin.register(TempoRota)
class TempoRotaAdmin(admin.ModelAdmin):
    list_display = ('rota', 'nome_atleta', 'tempo_minutos', 'tempo_segundos', 'data_registro')
    list_filter = ('rota', 'data_registro')
    search_fields = ('nome_atleta', 'rota__nome')

# ==========================================
# PAINEL DA ARENA X1 (DESAFIOS)
# ==========================================
@admin.register(Desafio)
class DesafioAdmin(admin.ModelAdmin):
    list_display = ('desafiante', 'desafiado', 'alvo_km', 'status', 'prazo_dias', 'data_criacao')
    list_filter = ('status', 'tipo', 'data_criacao')
    search_fields = ('desafiante', 'desafiado')
    
    # Adiciona botões rápidos para mudar o status selecionando vários de uma vez
    actions = ['marcar_como_concluido', 'marcar_como_ativo']

    @admin.action(description='Marcar desafios selecionados como Concluídos')
    def marcar_como_concluido(self, request, queryset):
        queryset.update(status='concluido')

    @admin.action(description='Marcar desafios selecionados como Ativos')
    def marcar_como_ativo(self, request, queryset):
        queryset.update(status='ativo')

# ==========================================
# PAINEL DE SISTEMA (TOKENS STRAVA)
# ==========================================
@admin.register(TokenStrava)
class TokenStravaAdmin(admin.ModelAdmin):
    list_display = ('user', 'strava_id', 'expires_at')
    search_fields = ('user__username', 'strava_id', 'user__first_name')
