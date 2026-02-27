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
from django.contrib.auth.models import User
from django.contrib.auth.admin import UserAdmin
from django.utils import timezone

# ==========================================
# PAINEL DE USUÁRIOS E FOGUINHOS (STREAK)
# ==========================================

# 1. Removemos a tabela chata padrão do Django
admin.site.unregister(User)

# 2. Criamos a nossa tabela turbinada
@admin.register(User)
class AtletaAdmin(UserAdmin):
    # Escolhemos exatamente o que vai aparecer nas colunas
    list_display = ('first_name', 'username', 'foguinhos_atuais', 'status_foguinho', 'date_joined')
    
    # Função que calcula os Foguinhos atuais do atleta
    def foguinhos_atuais(self, obj):
        if not obj.first_name:
            return "0 🔥"
            
        atividades = Atividade.objects.filter(nome_usuario=obj.first_name).order_by('-data_envio')
        datas_treinos = list(atividades.dates('data_envio', 'day', order='DESC'))
        hoje = timezone.now().date()
        
        streak = 0
        if datas_treinos:
            dias_sem_treino = (hoje - datas_treinos[0]).days
            if dias_sem_treino <= 3:
                streak = 1 
                for i in range(len(datas_treinos) - 1):
                    if (datas_treinos[i] - datas_treinos[i+1]).days <= 3:
                        streak += 1
                    else:
                        break 
        return f"{streak} 🔥"
    foguinhos_atuais.short_description = 'Sequência'

    # Função que calcula quanto tempo falta para perder
    def status_foguinho(self, obj):
        if not obj.first_name:
            return "-"
            
        ultima_ativ = Atividade.objects.filter(nome_usuario=obj.first_name).order_by('-data_envio').first()
        if not ultima_ativ:
            return "Sem treinos"
            
        hoje = timezone.now().date()
        
        # Pega a data do último treino
        try:
            data_ultimo = ultima_ativ.data_envio.date()
        except AttributeError:
            data_ultimo = ultima_ativ.data_envio
            
        dias_sem_treino = (hoje - data_ultimo).days
        
        # A regra de ouro: expira se passar de 3 dias
        dias_restantes = 3 - dias_sem_treino
        
        if dias_restantes < 0:
            return "❌ Apagado (Perdeu)"
        elif dias_restantes == 0:
            return "⚠️ Vence HOJE!"
        elif dias_restantes == 1:
            return "⏳ Vence amanhã"
        else:
            return f"✅ Seguro por {dias_restantes} dias"
            
    status_foguinho.short_description = 'Status do Fogo'
