import requests
from django.conf import settings
from django.shortcuts import render, redirect
from .models import Atividade, MetaMensal, Rota
from django.db.models import Sum, Count
from django.db.models.functions import TruncDate
from datetime import datetime
from .forms import AtividadeForm
from django.db.models.functions import ExtractWeekDay
from django.db.models import Sum, Avg, Count, Max, Q
from datetime import timedelta
from django.utils import timezone
import calendar
import json
from django.http import JsonResponse
 

# Helper para nomes dos meses
MESES_NOME = {
    1: 'Janeiro', 2: 'Fevereiro', 3: 'Março', 4: 'Abril', 
    5: 'Maio', 6: 'Junho', 7: 'Julho', 8: 'Agosto', 
    9: 'Setembro', 10: 'Outubro', 11: 'Novembro', 12: 'Dezembro'
}

def dashboard(request):
    hoje = datetime.now()
    
    meta = MetaMensal.objects.filter(mes=hoje.month, ano=hoje.year).first()
    meta_valor = meta.objetivo_km if meta else 1000
    
    total_acumulado = Atividade.objects.filter(
        data_envio__month=hoje.month, 
        data_envio__year=hoje.year
    ).aggregate(Sum('quantidade_km'))['quantidade_km__sum'] or 0
    
    porcentagem = round((total_acumulado / meta_valor) * 100, 2)
    porcentagem_visual = min(porcentagem, 100) # Trava em 100 para o CSS do tanque não quebrar

    ranking = Atividade.objects.filter(
        data_envio__month=hoje.month, data_envio__year=hoje.year, tipo='corrida'
    ).values('nome_usuario').annotate(total=Sum('quantidade_km')).order_by('-total')

    context = {
        'total_acumulado': total_acumulado,
        'meta_valor': meta_valor,
        'porcentagem': porcentagem,
        'porcentagem_visual': porcentagem_visual,
        'ranking': ranking,
    }
    return render(request, 'core/dashboard.html', context)

def registrar_km(request):
    if request.method == 'POST':
        form = AtividadeForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            return redirect('dashboard')
    else:
        form = AtividadeForm()
    
    return render(request, 'core/registrar.html', {'form': form})

def historico(request):
    metas = MetaMensal.objects.all().order_by('-ano', '-mes')
    dados = []
    
    for meta in metas:
        total = Atividade.objects.filter(
            data_envio__month=meta.mes, 
            data_envio__year=meta.ano
        ).aggregate(Sum('quantidade_km'))['quantidade_km__sum'] or 0
        
        pct = round((total / meta.objetivo_km) * 100, 1)
        
        dados.append({
            'mes_nome': MESES_NOME.get(meta.mes, 'Mês'),
            'ano': meta.ano,
            'objetivo': meta.objetivo_km,
            'total': total,
            'pct': pct,
            'pct_css': min(pct, 100),
            'atingiu': total >= meta.objetivo_km
        })
        
    return render(request, 'core/historico.html', {'dados': dados})

def ranking_geral(request):
    # Agrupa por usuário, soma KMs totais e conta dias distintos (dias ativos)
    # Funcionalidade Diferencial: Sistema de Níveis baseado no KM total
    
    stats = Atividade.objects.annotate(
        data_truncada=TruncDate('data_envio')
    ).values('nome_usuario').annotate(
        total_km_geral=Sum('quantidade_km', filter=Q(tipo='corrida')),
        dias_ativos=Count('data_truncada', distinct=True)
    ).order_by('-total_km_geral')
    
    ranking_final = []
    for s in stats:
        km = s['total_km_geral']
        
        # Lógica da Gamificação (Níveis)
        nivel = "Novato 🥚"
        classe = "text-secondary"
        if km > 50: 
            nivel = "Aspirante 🏃"
            classe = "text-info"
        if km > 150: 
            nivel = "Atleta 🥉"
            classe = "text-primary"
        if km > 300: 
            nivel = "Maratonista 🥈"
            classe = "text-warning"
        if km > 500: 
            nivel = "Lenda do Asfalto 🥇"
            classe = "text-success"
        if km > 1000: 
            nivel = "Máquina Viva 🤖"
            classe = "text-danger"
            
        s['nivel'] = nivel
        s['classe_nivel'] = classe
        ranking_final.append(s)

    return render(request, 'core/ranking_geral.html', {'ranking': ranking_final})

def desempenho(request):
    atletas = Atividade.objects.values_list('nome_usuario', flat=True).distinct().order_by('nome_usuario')
    atleta_selecionado = request.GET.get('atleta')
    context = {'atletas': atletas, 'atleta_selecionado': atleta_selecionado}

    if atleta_selecionado:
        atividades = Atividade.objects.filter(nome_usuario=atleta_selecionado, tipo='corrida').order_by('-data_envio')
        
        if atividades.exists():
            hoje = datetime.now()
            mes_atual = hoje.month
            ano_atual = hoje.year
            
            mes_passado = 12 if mes_atual == 1 else mes_atual - 1
            ano_passado = ano_atual - 1 if mes_atual == 1 else ano_atual

            # 1. Comparativo de Meses
            km_atual = atividades.filter(data_envio__month=mes_atual, data_envio__year=ano_atual).aggregate(Sum('quantidade_km'))['quantidade_km__sum'] or 0
            km_passado = atividades.filter(data_envio__month=mes_passado, data_envio__year=ano_passado).aggregate(Sum('quantidade_km'))['quantidade_km__sum'] or 0

            variacao_pct = 0
            if km_passado > 0:
                variacao_pct = ((float(km_atual) - float(km_passado)) / float(km_passado)) * 100
            elif km_atual > 0:
                variacao_pct = 100 

            # 2. Estatísticas Gerais
            media_km = atividades.aggregate(Avg('quantidade_km'))['quantidade_km__avg'] or 0
            total_corridas = atividades.count()
            maior_corrida = atividades.aggregate(Max('quantidade_km'))['quantidade_km__max'] or 0
            
            # 3. Dia Favorito
            fav_day_query = atividades.annotate(dia=ExtractWeekDay('data_envio')).values('dia').annotate(count=Count('id')).order_by('-count').first()
            fav_idx = (fav_day_query['dia'] - 2) % 7 if fav_day_query else 6 
            dias_pt = {0: 'Segunda', 1: 'Terça', 2: 'Quarta', 3: 'Quinta', 4: 'Sexta', 5: 'Sábado', 6: 'Domingo'}
            dia_favorito = dias_pt[fav_idx]

            # 4. Lógica Baseada na Última Corrida
            ultima = atividades.first()
            km_recomendado = float(ultima.quantidade_km) * 1.10 if ultima else 0
            default_pace = ultima.pace if (ultima and ultima.pace) else "06:00"

            dias_descanso = 2 if ultima and float(ultima.quantidade_km) > 10 else 1
            prox_data = ultima.data_envio + timedelta(days=dias_descanso) if ultima else hoje
            if prox_data.date() <= hoje.date():
                mensagem_data = "Hoje! Corpo recuperado."
            else:
                mensagem_data = f"{prox_data.strftime('%d/%m')} (Amanhã/Em breve)"

            # 5. Projeção e Calorias
            _, ult_dia_mes = calendar.monthrange(ano_atual, mes_atual)
            projecao_mensal = (float(km_atual) / hoje.day) * ult_dia_mes if hoje.day > 0 else 0
            total_km_historico = atividades.aggregate(Sum('quantidade_km'))['quantidade_km__sum'] or 0
            calorias_queimadas = float(total_km_historico) * 65 
            fatias_pizza = int(calorias_queimadas / 285) 

            # 6. Calendário Semanal
            plano_semanal = []
            for i in range(7):
                d_date = hoje + timedelta(days=i)
                d_idx = d_date.weekday()
                if d_idx == fav_idx:
                    tipo, cor, icon, desc = "Treino Longo", "warning", "🏃‍♂️🔥", f"Até {round(km_recomendado,1)}km"
                elif (d_idx - fav_idx) % 7 == 1:
                    tipo, cor, icon, desc = "Descanso", "secondary", "🛌💤", "Recuperação total"
                elif (d_idx - fav_idx) % 7 == -3 or (d_idx - fav_idx) % 7 == 4:
                    tipo, cor, icon, desc = "Tiros/Ritmo", "danger", "⚡⏱️", "Treino Forte"
                else:
                    tipo, cor, icon, desc = "Rodagem Leve", "success", "🍃👟", "Pace Leve"
                    
                plano_semanal.append({
                    'data': d_date.strftime("%d/%m"), 'dia_semana': dias_pt[d_idx],
                    'tipo': tipo, 'cor': cor, 'icon': icon, 'desc': desc, 'is_hoje': i == 0
                })

            context.update({
                'km_atual': km_atual, 'km_passado': km_passado, 'variacao_pct': round(variacao_pct, 1),
                'media_km': round(media_km, 2), 'total_corridas': total_corridas, 'maior_corrida': maior_corrida,
                'dia_favorito': dia_favorito, 'ultima': ultima, 'km_recomendado': round(km_recomendado, 2),
                'mensagem_data': mensagem_data, 'default_pace': default_pace,
                'projecao_mensal': round(projecao_mensal, 1), 'calorias': int(calorias_queimadas), 'pizzas': fatias_pizza,
                'plano_semanal': plano_semanal 
            })

    return render(request, 'core/desempenho.html', context)

# ==========================================
# INTEGRAÇÃO COM STRAVA
# ==========================================

def strava_login(request):
    """ Redireciona o usuário para a tela oficial de login do Strava """
    client_id = settings.STRAVA_CLIENT_ID
    redirect_uri = settings.STRAVA_REDIRECT_URI
    # Pedimos permissão para ler as atividades ('activity:read_all')
    url = f"https://www.strava.com/oauth/authorize?client_id={client_id}&response_type=code&redirect_uri={redirect_uri}&approval_prompt=force&scope=activity:read_all"
    return redirect(url)

def strava_callback(request):
    """ O Strava devolve o usuário para cá após o login """
    error = request.GET.get('error')
    if error:
        return redirect('dashboard') # Se a pessoa clicar em "Cancelar" no Strava

    code = request.GET.get('code')
    if not code:
        return redirect('dashboard')

    # 1. Trocar o 'code' por um Token de Acesso Oficial
    token_url = "https://www.strava.com/oauth/token"
    payload = {
        'client_id': settings.STRAVA_CLIENT_ID,
        'client_secret': settings.STRAVA_CLIENT_SECRET,
        'code': code,
        'grant_type': 'authorization_code'
    }
    res = requests.post(token_url, data=payload)
    
    if res.status_code != 200:
        return redirect('dashboard') # Erro de comunicação

    token_data = res.json()
    access_token = token_data.get('access_token')
    # Pega o primeiro nome da pessoa cadastrado no Strava
    athlete_nome = token_data.get('athlete', {}).get('firstname', 'Atleta Strava')

    # 2. Ir na conta da pessoa e pegar a ÚLTIMA corrida registrada
    activities_url = "https://www.strava.com/api/v3/athlete/activities?per_page=1"
    headers = {'Authorization': f'Bearer {access_token}'}
    act_res = requests.get(activities_url, headers=headers)

    if act_res.status_code == 200 and len(act_res.json()) > 0:
        atividade = act_res.json()[0]
        strava_id = str(atividade['id'])
        
        # Só salva se essa corrida ainda não estiver no nosso Banco de Dados
        if not Atividade.objects.filter(strava_id=strava_id).exists():
            
            # Converter metros para KM
            distancia_metros = atividade['distance']
            distancia_km = distancia_metros / 1000.0
            
            # Calcular o Pace (Tempo em movimento / Distancia)
            moving_time = atividade['moving_time']
            pace_str = ""
            if distancia_km > 0:
                pace_segundos = moving_time / distancia_km
                m = int(pace_segundos // 60)
                s = int(pace_segundos % 60)
                pace_str = f"{m:02d}:{s:02d}"

            # Salvar automaticamente no nosso Banco! (Sem precisar de foto)
            if distancia_km > 0.1: # Só salva se tiver corrido mais de 100 metros
                Atividade.objects.create(
                    nome_usuario=athlete_nome,
                    quantidade_km=round(distancia_km, 2),
                    pace=pace_str,
                    strava_id=strava_id
                )

    return redirect('dashboard')


def feed_atividades(request):
    atividades_feed = Atividade.objects.all().order_by('-data_envio')
    atletas = Atividade.objects.values_list('nome_usuario', flat=True).distinct()
    ranking_foguinhos = []
    hoje = timezone.now().date()
    
    for atleta in atletas:
        # Pega as datas únicas, da mais recente para a mais antiga
        datas_treinos = list(Atividade.objects.filter(nome_usuario=atleta).dates('data_envio', 'day', order='DESC'))
        
        streak = 0
        if datas_treinos:
            # Tolerância de 3 dias: Se a diferença entre hoje e o último treino for <= 3, a ofensiva tá viva!
            dias_sem_treino = (hoje - datas_treinos[0]).days
            if dias_sem_treino <= 3:
                streak = 1 # Já conta 1 ponto pela sequência viva
                
                # Conta o tamanho da corrente (se o intervalo entre os treinos não passar de 3 dias)
                for i in range(len(datas_treinos) - 1):
                    if (datas_treinos[i] - datas_treinos[i+1]).days <= 3:
                        streak += 1
                    else:
                        break # A corrente quebrou no passado
                        
        if streak > 0:
            ranking_foguinhos.append({'nome': atleta, 'fogo': streak})
            
    # Ordena pelo maior fogo
    ranking_foguinhos = sorted(ranking_foguinhos, key=lambda x: x['fogo'], reverse=True)
    
    # Define as Cores e Animação do 1º Lugar
    if ranking_foguinhos:
        ranking_foguinhos[0]['is_first'] = True # O primeiro colocado ganha o fogo pulsante
        
    for rank in ranking_foguinhos:
        fogo = rank['fogo']
        if fogo <= 2: rank['cor'] = '#ffca28' # Amarelo (Iniciante)
        elif fogo <= 5: rank['cor'] = '#ff7043' # Laranja (Esquentando)
        elif fogo <= 10: rank['cor'] = '#e91e63' # Rosa/Vermelho (Pegando Fogo)
        else: rank['cor'] = '#00e5ff' # Azul Cyan (Lendário)

    # Lógica do DESTAQUE DO MÊS (Quem tem mais KM no mês atual)
    destaque = Atividade.objects.filter(
        data_envio__month=hoje.month, 
        data_envio__year=hoje.year, 
        tipo='corrida'
    ).values('nome_usuario').annotate(total=Sum('quantidade_km')).order_by('-total').first()

    context = {
        'atividades': atividades_feed, 
        'foguinhos': ranking_foguinhos,
        'destaque': destaque
    }
    return render(request, 'core/feed.html', context)

# ==========================================
# PLANEJADOR DE ROTAS (MAPAS)
# ==========================================
def criar_rota(request):
    if request.method == 'POST':
        try:
            # Recebe os dados invisíveis do mapa em JavaScript
            data = json.loads(request.body)
            Rota.objects.create(
                nome=data.get('nome'),
                criador=data.get('criador'),
                distancia_estimada=data.get('distancia'),
                coordenadas=data.get('coordenadas')
            )
            return JsonResponse({'status': 'sucesso'})
        except Exception as e:
            return JsonResponse({'status': 'erro', 'mensagem': str(e)})

    return render(request, 'core/criar_rota.html')

def listar_rotas(request):
    rotas = Rota.objects.all().order_by('-data_criacao')
    return render(request, 'core/listar_rotas.html', {'rotas': rotas})
