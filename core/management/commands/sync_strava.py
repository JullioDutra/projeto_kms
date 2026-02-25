import requests
from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.conf import settings
from core.models import TokenStrava, Atividade

class Command(BaseCommand):
    help = 'Puxa automaticamente as novas corridas do Strava para todos os usuários logados.'

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.SUCCESS('Iniciando sincronização automática do Strava...'))
        
        # Pega todos os usuários que têm a conta conectada no cofre
        tokens = TokenStrava.objects.all()
        
        if not tokens.exists():
            self.stdout.write(self.style.WARNING('Nenhuma conta Strava conectada encontrada.'))
            return

        for token_obj in tokens:
            self.stdout.write(f'Verificando atleta: {token_obj.user.first_name}...')
            
            # 1. VERIFICA SE A CHAVE ESTÁ VENCIDA E RENOVA SE PRECISO
            access_token = token_obj.access_token
            if timezone.now() >= token_obj.expires_at:
                self.stdout.write('Chave vencida. Renovando com o Strava...')
                refresh_url = "https://www.strava.com/oauth/token"
                payload = {
                    'client_id': settings.STRAVA_CLIENT_ID,
                    'client_secret': settings.STRAVA_CLIENT_SECRET,
                    'grant_type': 'refresh_token',
                    'refresh_token': token_obj.refresh_token
                }
                res = requests.post(refresh_url, data=payload)
                
                if res.status_code == 200:
                    data = res.json()
                    access_token = data.get('access_token')
                    token_obj.access_token = access_token
                    token_obj.refresh_token = data.get('refresh_token')
                    token_obj.expires_at = timezone.now() + timedelta(seconds=data.get('expires_in', 21600))
                    token_obj.save()
                    self.stdout.write(self.style.SUCCESS('Chave renovada com sucesso!'))
                else:
                    self.stdout.write(self.style.ERROR(f'Erro ao renovar chave: {res.text}'))
                    continue # Pula para o próximo usuário se der erro

            # 2. PUXA AS CORRIDAS COM A CHAVE VÁLIDA
            activities_url = "https://www.strava.com/api/v3/athlete/activities?per_page=1"
            headers = {'Authorization': f'Bearer {access_token}'}
            act_res = requests.get(activities_url, headers=headers)

            if act_res.status_code == 200 and len(act_res.json()) > 0:
                atividade = act_res.json()[0]
                act_strava_id = str(atividade['id'])
                
                # Se a corrida não existir no banco, ele salva!
                if not Atividade.objects.filter(strava_id=act_strava_id).exists():
                    distancia_km = atividade['distance'] / 1000.0
                    
                    tipo_atividade = 'corrida'
                    if atividade.get('type') == 'Ride':
                        tipo_atividade = 'bike'

                    if distancia_km > 0.1:
                        moving_time = atividade['moving_time']
                        pace_str = ""
                        if distancia_km > 0:
                            pace_segundos = moving_time / distancia_km
                            m = int(pace_segundos // 60)
                            s = int(pace_segundos % 60)
                            pace_str = f"{m:02d}:{s:02d}"

                        # Como é um robô rodando no fundo, puxamos a foto do usuário do Django
                        nome_atleta = token_obj.user.first_name
                        foto_url = 'https://cdn-icons-png.flaticon.com/512/149/149071.png' # Foto padrão caso falhe
                        
                        # Tenta pegar a última foto que esse atleta usou no sistema
                        ultima_ativ = Atividade.objects.filter(nome_usuario=nome_atleta, avatar_url__isnull=False).first()
                        if ultima_ativ:
                            foto_url = ultima_ativ.avatar_url

                        Atividade.objects.create(
                            nome_usuario=nome_atleta,
                            quantidade_km=round(distancia_km, 2),
                            pace=pace_str,
                            strava_id=act_strava_id,
                            tipo=tipo_atividade,
                            avatar_url=foto_url
                        )
                        self.stdout.write(self.style.SUCCESS(f'Nova atividade salva para {nome_atleta}: {distancia_km:.2f}km!'))
                else:
                    self.stdout.write(f'A última atividade de {token_obj.user.first_name} já está no sistema.')
            else:
                self.stdout.write(self.style.WARNING(f'Não foi possível puxar as atividades de {token_obj.user.first_name}.'))

        self.stdout.write(self.style.SUCCESS('Sincronização concluída!'))