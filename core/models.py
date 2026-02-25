from django.db import models

class MetaMensal(models.Model):
    mes = models.IntegerField(choices=[(i, i) for i in range(1, 13)], verbose_name="Mês (Número)")
    ano = models.IntegerField(default=2026)
    objetivo_km = models.DecimalField(max_digits=7, decimal_places=2, verbose_name="Meta Total (KM)")

    def __str__(self):
        return f"Meta de {self.mes}/{self.ano}: {self.objetivo_km}km"


class Atividade(models.Model):
    TIPO_CHOICES = [
        ('corrida', '🏃 Corrida / Caminhada'),
        ('bike', '🚴 Ciclismo / Bike'),
    ]
    
    nome_usuario = models.CharField(max_length=100, verbose_name="Nome do Atleta")
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, default='corrida', verbose_name="Tipo de Treino")
    
    quantidade_km = models.DecimalField(max_digits=5, decimal_places=2, verbose_name="KM Percorrido")
    pace = models.CharField(max_length=5, blank=True, null=True, verbose_name="Pace (Min/Km)")
    
    foto_comprovante = models.ImageField(upload_to='comprovantes/', verbose_name="Foto do Comprovante", blank=True, null=True)
    data_envio = models.DateTimeField(auto_now_add=True)
    strava_id = models.CharField(max_length=100, blank=True, null=True, unique=True)
    
    # NOVO: Sistema de Medalhas para o Feed
    medalha = models.CharField(max_length=100, blank=True, null=True, verbose_name="Medalha de Superação", help_text="Adicione pelo painel Admin")

    avatar_url = models.URLField(max_length=500, blank=True, null=True, verbose_name="Foto de Perfil (Strava)")
    
    def __str__(self):
        return f"[{self.tipo.upper()}] {self.nome_usuario} - {self.quantidade_km}km"

    class Meta:
        verbose_name = "Atividade"
        verbose_name_plural = "Atividades"


class Rota(models.Model):
    nome = models.CharField(max_length=100, verbose_name="Nome da Rota")
    criador = models.CharField(max_length=100, verbose_name="Criador (Atleta)")
    distancia_estimada = models.DecimalField(max_digits=5, decimal_places=2, verbose_name="Distância (KM)")
    # O JSONField vai guardar todas as coordenadas (Latitude e Longitude) que a pessoa clicou
    coordenadas = models.JSONField(verbose_name="Coordenadas do Mapa")
    data_criacao = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.nome} ({self.distancia_estimada}km) - {self.criador}"

    class Meta:
        verbose_name = "Rota da Comunidade"
        verbose_name_plural = "Rotas da Comunidade"


class TempoRota(models.Model):
    rota = models.ForeignKey(Rota, on_delete=models.CASCADE, related_name='tempos')
    nome_atleta = models.CharField(max_length=100, verbose_name="Atleta")
    tempo_minutos = models.PositiveIntegerField(verbose_name="Minutos")
    tempo_segundos = models.PositiveIntegerField(verbose_name="Segundos")
    data_registro = models.DateTimeField(auto_now_add=True)

    @property
    def tempo_total_segundos(self):
        return (self.tempo_minutos * 60) + self.tempo_segundos

    @property
    def tempo_formatado(self):
        return f"{self.tempo_minutos:02d}:{self.tempo_segundos:02d}"

    def __str__(self):
        return f"{self.nome_atleta} - {self.tempo_formatado} em {self.rota.nome}"

    class Meta:
        verbose_name = "Tempo na Rota"
        verbose_name_plural = "Tempos nas Rotas"

class TokenStrava(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='strava_token')
    strava_id = models.CharField(max_length=100, unique=True)
    access_token = models.CharField(max_length=255)
    refresh_token = models.CharField(max_length=255)
    expires_at = models.DateTimeField()

    def __str__(self):
        return f"Tokens de {self.user.first_name}"
