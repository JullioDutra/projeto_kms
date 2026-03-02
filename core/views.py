import requests
from django.conf import settings
from django.shortcuts import render, redirect, get_object_or_404
from .models import Atividade, MetaMensal, Rota, TokenStrava, Desafio
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
from django.contrib.auth.models import User
from django.contrib.auth import login
 

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
        data_envio__year=hoje.year,
        tipo='corrida' # <--- Apenas Corridas no Tanque!
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

    # --- INÍCIO DA LÓGICA DO CARTÃO DO ATLETA ---
    if request.user.is_authenticated:
        nome_atleta = request.user.first_name
        
        # Importações locais de segurança
        from django.db.models import Count 
        from .models import Rota, TempoRota
        
        # 1. Pega os KMs e Total de Corridas (Apenas Corridas também!)
        stats_usuario = Atividade.objects.filter(nome_usuario=nome_atleta, tipo='corrida').aggregate(
            total_km=Sum('quantidade_km'),
            total_corridas=Count('id')
        )
        context['meu_total_km'] = stats_usuario['total_km'] or 0
        context['minhas_corridas'] = stats_usuario['total_corridas'] or 0
        
        # 2. Verifica se ele é "Rei" de alguma Rota
        minhas_coroas = 0
        for rota in Rota.objects.all():
            melhor_tempo = TempoRota.objects.filter(rota=rota).order_by('tempo_minutos', 'tempo_segundos').first()
            if melhor_tempo and melhor_tempo.nome_atleta == nome_atleta:
                minhas_coroas += 1
                
        context['minhas_coroas'] = minhas_coroas
    # --- FIM DA LÓGICA DO CARTÃO ---

    return render(request, 'core/dashboard.html', context)

def registrar_km(request):
    if request.method == 'POST':
        form = AtividadeForm(request.POST, request.FILES)
        if form.is_valid():
            atividade = form.save(commit=False) # Pausa antes de guardar
            # Se a pessoa estiver logada via Strava, roubamos a foto para o post manual!
            if request.user.is_authenticated and 'foto_strava' in request.session:
                atividade.avatar_url = request.session['foto_strava']
            atividade.save() # Agora sim, guarda no banco
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
        # 🛡️ A MÁGICA SALVADORA: Se a soma der None (Vazio), vira 0.
        km = s['total_km_geral'] or 0
        s['total_km_geral'] = km # Atualiza o valor no dicionário para o HTML não quebrar
        
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

    # Reordena a lista final para garantir que quem tem 0 vá para o final do pódio
    ranking_final = sorted(ranking_final, key=lambda x: x['total_km_geral'], reverse=True)

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
    error = request.GET.get('error')
    if error: return redirect('dashboard')
    code = request.GET.get('code')
    if not code: return redirect('dashboard')

    token_url = "https://www.strava.com/oauth/token"
    payload = {
        'client_id': settings.STRAVA_CLIENT_ID,
        'client_secret': settings.STRAVA_CLIENT_SECRET,
        'code': code,
        'grant_type': 'authorization_code'
    }
    res = requests.post(token_url, data=payload)
    if res.status_code != 200: return redirect('dashboard')

    token_data = res.json()
    access_token = token_data.get('access_token')
    refresh_token = token_data.get('refresh_token')
    # O Strava manda a validade em segundos. Convertemos para data e hora reais:
    expires_at = timezone.now() + timedelta(seconds=token_data.get('expires_in', 21600))
    
    # 1. PEGAR OS DADOS PESSOAIS DO ATLETA
    athlete = token_data.get('athlete', {})
    athlete_nome = athlete.get('firstname', 'Atleta Strava')
    strava_id = str(athlete.get('id'))
    foto_url = athlete.get('profile', 'https://cdn-icons-png.flaticon.com/512/149/149071.png')

    # 2. SISTEMA DE LOGIN E COFRE DE TOKENS (A MÁGICA DA AUTOMAÇÃO)
    # Procura se o atleta já existe no nosso banco. Se não, cria uma conta para ele!
    user, created = User.objects.get_or_create(username=strava_id)
    if created:
        user.first_name = athlete_nome
        user.save()

    # Guarda ou atualiza a "Chave Mestra" do Strava no Cofre do Banco de Dados
    TokenStrava.objects.update_or_create(
        user=user,
        defaults={
            'strava_id': strava_id,
            'access_token': access_token,
            'refresh_token': refresh_token,
            'expires_at': expires_at
        }
    )

    # Faz o login oficial (cria o cookie de sessão)
    login(request, user)
    
    # Salva a foto na sessão para mostrarmos no site
    request.session['foto_strava'] = foto_url
    request.session['nome_strava'] = athlete_nome

    # 3. PUXAR A ÚLTIMA CORRIDA
    activities_url = "https://www.strava.com/api/v3/athlete/activities?per_page=1"
    headers = {'Authorization': f'Bearer {access_token}'}
    act_res = requests.get(activities_url, headers=headers)

    if act_res.status_code == 200 and len(act_res.json()) > 0:
        atividade = act_res.json()[0]
        act_strava_id = str(atividade['id'])
        
        if not Atividade.objects.filter(strava_id=act_strava_id).exists():
            distancia_km = atividade['distance'] / 1000.0
            
            tipo_atividade = 'corrida'
            if atividade.get('type') == 'Ride':
                tipo_atividade = 'bike'

            if distancia_km > 0.1:
                moving_time = atividade['moving_time']
                nome_do_treino = atividade.get('name', 'Treino sem título')
                pace_str = ""
                if distancia_km > 0:
                    pace_segundos = moving_time / distancia_km
                    m = int(pace_segundos // 60)
                    s = int(pace_segundos % 60)
                    pace_str = f"{m:02d}:{s:02d}"

                # Salva o treino puxando também a foto para aparecer no Feed!
                Atividade.objects.create(
                    nome_usuario=athlete_nome,
                    quantidade_km=round(distancia_km, 2),
                    pace=pace_str,
                    strava_id=act_strava_id,
                    tipo=tipo_atividade,
                    avatar_url=foto_url,
                    descricao=nome_do_treino
                )
                
    return redirect('dashboard')


def feed_atividades(request):
    from .models import Desafio
    from django.db.models import Sum
    atividades_feed = Atividade.objects.all().order_by('-data_envio')
    atletas = Atividade.objects.values_list('nome_usuario', flat=True).distinct()
    ranking_foguinhos = []
    hoje = timezone.now().date()
    
    # 1. CRIAMOS UM DICIONÁRIO DE ROSTOS
    avatares = {}

    # Se você (ou qualquer um) estiver logado, já garantimos a foto no dicionário!
    if request.user.is_authenticated and 'foto_strava' in request.session:
        avatares[request.user.first_name] = request.session['foto_strava']
    
    for atleta in atletas:
        atividades_atleta = Atividade.objects.filter(nome_usuario=atleta).order_by('-data_envio')
        datas_treinos = list(atividades_atleta.dates('data_envio', 'day', order='DESC'))
        
        # Procura a foto deste atleta (pega da sessão se já tiver, ou busca no banco)
        avatar = avatares.get(atleta) 
        if not avatar:
            for ativ in atividades_atleta:
                if ativ.avatar_url:
                    avatar = ativ.avatar_url
                    avatares[atleta] = avatar # Salva no dicionário para usar depois
                    break
                    
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
                        
        if streak > 0:
            ranking_foguinhos.append({'nome': atleta, 'fogo': streak, 'avatar': avatar})
            
    ranking_foguinhos = sorted(ranking_foguinhos, key=lambda x: x['fogo'], reverse=True)
    if ranking_foguinhos:
        ranking_foguinhos[0]['is_first'] = True 
        
    for rank in ranking_foguinhos:
        fogo = rank['fogo']
        if fogo <= 2: rank['cor'] = '#ffca28' 
        elif fogo <= 5: rank['cor'] = '#ff7043' 
        elif fogo <= 10: rank['cor'] = '#e91e63' 
        else: rank['cor'] = '#00e5ff' 

    destaque = Atividade.objects.filter(
        data_envio__month=hoje.month, 
        data_envio__year=hoje.year, 
        tipo='corrida'
    ).values('nome_usuario').annotate(total=Sum('quantidade_km')).order_by('-total').first()

    # 2.RETROATIVA: Aplica a foto a TODOS os posts antigos que estavam sem foto
    for post in atividades_feed:
        if not post.avatar_url and post.nome_usuario in avatares:
            post.avatar_url = avatares[post.nome_usuario]
            post.save()

    # =========================================================
    # --- NOVO: MODELO INSTAGRAM (Banners e Posts Especiais) ---
    # =========================================================


    # A. Banner de Alerta (Só aparece se o usuário logado tiver sido desafiado)
    desafios_pendentes = 0
    if request.user.is_authenticated:
        desafios_pendentes = Desafio.objects.filter(desafiado=request.user.first_name, status='pendente').count()

    # B. Criar os "Posts" de Desafio para o Feed
    # Pega as 3 batalhas mais recentes (ativas ou recém-concluídas)
    desafios_recentes = Desafio.objects.filter(status__in=['ativo', 'concluido']).order_by('-data_criacao')[:3]
    posts_desafios = []
    
    for d in desafios_recentes:
        fim = d.data_fim if d.data_fim and d.data_fim < timezone.now() else timezone.now()
        
        # O Django pode atualizar automaticamente para concluído se o prazo passou!
        if d.status == 'ativo' and d.data_fim and d.data_fim < timezone.now():
            d.status = 'concluido'
            d.save()

        km_desafiante = Atividade.objects.filter(
            nome_usuario=d.desafiante, data_envio__gte=d.data_inicio, data_envio__lte=fim, tipo='corrida'
        ).aggregate(Sum('quantidade_km'))['quantidade_km__sum'] or 0
        
        km_desafiado = Atividade.objects.filter(
            nome_usuario=d.desafiado, data_envio__gte=d.data_inicio, data_envio__lte=fim, tipo='corrida'
        ).aggregate(Sum('quantidade_km'))['quantidade_km__sum'] or 0

        # Quem está ganhando?
        if km_desafiante > km_desafiado: vencendo = d.desafiante
        elif km_desafiado > km_desafiante: vencendo = d.desafiado
        else: vencendo = 'Empate'

        posts_desafios.append({
            'id': d.id,
            'desafiante': d.desafiante,
            'desafiado': d.desafiado,
            'avatar_desafiante': avatares.get(d.desafiante, ''),
            'avatar_desafiado': avatares.get(d.desafiado, ''),
            'km_desafiante': km_desafiante,
            'km_desafiado': km_desafiado,
            'alvo_km': d.alvo_km,
            'status': d.status,
            'vencendo': vencendo
        })

    context = {
        'atividades': atividades_feed, 
        'foguinhos': ranking_foguinhos,
        'destaque': destaque,
        'desafios_pendentes': desafios_pendentes, # Para o banner
        'posts_desafios': posts_desafios # Para o feed de notícias
    }
    return render(request, 'core/feed.html', context)
# ==========================================
# PLANEJADOR DE ROTAS (MAPAS)
# ==========================================
def criar_rota(request):
    # 1. TRAVA DE SEGURANÇA: Só passa se estiver logado
    if not request.user.is_authenticated:
        return redirect('listar_rotas')
        
    if request.method == 'POST':
        try:
            # Recebe os dados do mapa em JavaScript
            data = json.loads(request.body)
            
            Rota.objects.create(
                nome=data.get('nome'),
                # 2. TRAVA DE AUTORIA: O Django injeta o nome da sessão de forma segura!
                criador=request.user.first_name, 
                distancia_estimada=data.get('distancia'),
                coordenadas=data.get('coordenadas')
            )
            return JsonResponse({'status': 'sucesso'})
        except Exception as e:
            return JsonResponse({'status': 'erro', 'mensagem': str(e)})

    # Se não for POST (só está a abrir a página), carrega o HTML
    return render(request, 'core/criar_rota.html')

def listar_rotas(request):
    rotas = Rota.objects.all().order_by('-data_criacao')
    return render(request, 'core/listar_rotas.html', {'rotas': rotas})

def ver_rota(request, id):
    rota = get_object_or_404(Rota, id=id)
    
    # 1. Se a pessoa enviar um tempo novo pelo formulário do Modal:
    if request.method == 'POST':
        # Importamos a Atividade aqui para poder salvar no Tanque também
        from .models import TempoRota, Atividade 
        
        atleta = request.POST.get('atleta')
        minutos = int(request.POST.get('minutos', 0) or 0)
        segundos = int(request.POST.get('segundos', 0) or 0)
        pace = request.POST.get('pace', '')
        foto = request.FILES.get('foto_comprovante') # Pega a foto que a pessoa subiu
        
        if atleta and (minutos > 0 or segundos > 0) and foto:
            # AÇÃO 1: Registra o tempo para o Leaderboard (Rei da Rota)
            TempoRota.objects.create(
                rota=rota,
                nome_atleta=atleta,
                tempo_minutos=minutos,
                tempo_segundos=segundos
            )
            
            # AÇÃO 2: Envia para o Tanque/Feed como uma atividade normal!
            Atividade.objects.create(
                nome_usuario=atleta,
                tipo='corrida', # O desafio da rota conta como corrida
                quantidade_km=rota.distancia_estimada, # Puxa os KMs automáticos da Rota!
                pace=pace,
                foto_comprovante=foto,
                # Podemos até colocar uma medalhinha automática no feed!
                medalha=f"Desbravou: {rota.nome}" 
            )
            
            return redirect('ver_rota', id=rota.id)

    # 2. Montar o Ranking (Rei da Rota)
    tempos_brutos = list(rota.tempos.all())
    tempos_brutos.sort(key=lambda x: x.tempo_total_segundos)
    
    ranking_tempos = []
    atletas_vistos = set()
    
    for t in tempos_brutos:
        if t.nome_atleta not in atletas_vistos:
            ranking_tempos.append(t)
            atletas_vistos.add(t.nome_atleta)

    return render(request, 'core/ver_rota.html', {
        'rota': rota, 
        'ranking_tempos': ranking_tempos
    })

def excluir_rota(request, id):
    # Puxa a rota do banco de dados
    from .models import Rota
    rota = get_object_or_404(Rota, id=id)
    
    #REGRA 2: Só exclui se estiver logado E for o dono exato da rota
    if request.user.is_authenticated and request.user.first_name == rota.criador:
        rota.delete()
        
    # Redireciona de volta para a biblioteca de mapas
    return redirect('listar_rotas')

def editar_descricao(request, id):
    # 1. Trava Básica: Tem que estar logado
    if not request.user.is_authenticated:
        return redirect('feed')
        
    if request.method == 'POST':
        # Puxa a atividade exata que a pessoa clicou
        from .models import Atividade
        atividade = get_object_or_404(Atividade, id=id)
        
        # 2. Trava de Segurança Nível Chefe: O usuário logado é o dono do post?
        if request.user.first_name == atividade.nome_usuario:
            # Pega o texto que veio do formulário (janela preta)
            nova_descricao = request.POST.get('nova_descricao')
            
            # Atualiza e salva!
            atividade.descricao = nova_descricao
            atividade.save()
            
    # Independente de dar certo ou errado, devolve a pessoa para o Feed
    return redirect('feed')

# ==========================================
# ARENA DE DESAFIOS (1 VS 1)
# ==========================================

def arena_desafios(request):
    if not request.user.is_authenticated:
        return redirect('dashboard')
        
    desafios_db = Desafio.objects.all().order_by('-data_criacao')
    desafios = []
    
    usuarios = User.objects.exclude(id=request.user.id)
    usuarios_disponiveis = [u.first_name for u in usuarios if u.first_name]

    for d in desafios_db:
        km_desafiante = 0
        km_desafiado = 0
        
        # Só calcula os KMs se o desafio já foi aceito e possui data de início!
        if d.status == 'ativo' and d.data_inicio:
            
            # CORREÇÃO DE DATA: Ignora as horas e pega apenas o dia para evitar bugs de fuso horário
            data_inicio_corte = d.data_inicio.date()
            fim = d.data_fim if d.data_fim and d.data_fim < timezone.now() else timezone.now()
            data_fim_corte = fim.date()
            
            # Busca os KMs do desafiante
            km_desafiante = Atividade.objects.filter(
                nome_usuario=d.desafiante, 
                data_envio__gte=data_inicio_corte, 
                data_envio__lte=data_fim_corte,
                tipo='corrida' # Apenas corrida entra no X1
            ).aggregate(Sum('quantidade_km'))['quantidade_km__sum'] or 0

            # Busca os KMs do desafiado
            km_desafiado = Atividade.objects.filter(
                nome_usuario=d.desafiado, 
                data_envio__gte=data_inicio_corte, 
                data_envio__lte=data_fim_corte,
                tipo='corrida'
            ).aggregate(Sum('quantidade_km'))['quantidade_km__sum'] or 0

        # Converte para float para evitar erro de Decimal
        alvo = float(d.alvo_km) if d.alvo_km > 0 else 1
        
        # Calcula a porcentagem com trava visual no máximo de 100%
        porc_desafiante = min((float(km_desafiante) / alvo) * 100, 100)
        porc_desafiado = min((float(km_desafiado) / alvo) * 100, 100)

        # SOLUÇÃO DAS FOTOS: Puxa da sessão se for o logado, senão cria um Avatar com a inicial do nome
        avatar_desafiante = request.session.get('foto_strava') if request.user.first_name == d.desafiante else f"https://ui-avatars.com/api/?name={d.desafiante}&background=00d2ff&color=fff&bold=true&size=150"
        avatar_desafiado = request.session.get('foto_strava') if request.user.first_name == d.desafiado else f"https://ui-avatars.com/api/?name={d.desafiado}&background=ff416c&color=fff&bold=true&size=150"

        desafios.append({
            'id': d.id,
            'desafiante': d.desafiante,
            'desafiado': d.desafiado,
            'status': d.status,
            'alvo_km': alvo,
            'prazo_dias': d.prazo_dias,
            'km_desafiante': float(km_desafiante),
            'km_desafiado': float(km_desafiado),
            'porc_desafiante': porc_desafiante,
            'porc_desafiado': porc_desafiado,
            'avatar_desafiante': avatar_desafiante,
            'avatar_desafiado': avatar_desafiado,
        })

    return render(request, 'core/arena.html', {
        'desafios': desafios,
        'usuarios_disponiveis': usuarios_disponiveis
    })



def criar_desafio(request):
    if not request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        desafiado = request.POST.get('desafiado')
        tipo = request.POST.get('tipo', 'distancia')
        alvo_km = request.POST.get('alvo_km', 0)
        prazo_dias = request.POST.get('prazo_dias', 7)

        # Evita que a pessoa desafie ela mesma (hacker alert!)
        if desafiado and desafiado != request.user.first_name:
            Desafio.objects.create(
                desafiante=request.user.first_name,
                desafiado=desafiado,
                tipo=tipo,
                alvo_km=alvo_km if alvo_km else 0,
                prazo_dias=prazo_dias
            )
            
    return redirect('arena_desafios')


def responder_desafio(request, desafio_id, resposta):
    if not request.user.is_authenticated:
        return redirect('dashboard')

    desafio = get_object_or_404(Desafio, id=desafio_id)

    # SEGURANÇA: Só quem foi desafiado pode clicar em "Aceitar"
    if request.user.first_name == desafio.desafiado and desafio.status == 'pendente':
        if resposta == 'aceitar':
            desafio.status = 'ativo'
            desafio.data_inicio = timezone.now()
            # O Relógio começa a contar agora!
            desafio.data_fim = desafio.data_inicio + timedelta(days=desafio.prazo_dias)
        elif resposta == 'recusar':
            desafio.status = 'recusado'
            
        desafio.save()

    return redirect('arena_desafios')

# No final do core/views.py

def desafio_fenix(request):
    if not request.user.is_authenticated:
        return redirect('dashboard')
    
    if request.method == 'POST':
        # Recebe os dados do formulário especial
        tempo_segundos = float(request.POST.get('segundos', 0))
        foto = request.FILES.get('foto_comprovante')
        
        # A Regra: 100m (0.1km) em 15 segundos ou menos
        # Pace de 15s/100m = 2:30 min/km (Muito rápido!)
        
        if tempo_segundos > 0 and tempo_segundos <= 15 and foto:
            # 1. Cria a atividade do Desafio (Para constar no histórico de hoje)
            Atividade.objects.create(
                nome_usuario=request.user.first_name,
                tipo='corrida',
                quantidade_km=0.1, # 100 metros
                pace=f"00:{int(tempo_segundos)}", # Ex: 00:14
                descricao="🔥 DESAFIO FÊNIX (100m < 15s)",
                avatar_url=request.session.get('foto_strava', ''),
                foto_comprovante=foto,
                data_envio=timezone.now() # Data de hoje
            )
            
            # 2. A MÁGICA DO RESGATE (Cria o Elo Perdido)
            # Descobre qual foi o último Domingo para salvar a sequência
            hoje = timezone.now().date()
            dias_para_domingo = (hoje.weekday() + 1) % 7
            ultimo_domingo = hoje - timedelta(days=dias_para_domingo)
            
            # Verifica se já não existe o salvamento para não duplicar
            ja_resgatou = Atividade.objects.filter(
                nome_usuario=request.user.first_name,
                data_envio=ultimo_domingo,
                descricao="🔥 Elo de Resgate (Fênix)"
            ).exists()
            
            if not ja_resgatou:
                Atividade.objects.create(
                    nome_usuario=request.user.first_name,
                    tipo='corrida',
                    quantidade_km=0.0, # Zero km para não fraudar a meta mensal
                    pace="00:00",
                    descricao="🔥 Elo de Resgate (Fênix)",
                    data_envio=ultimo_domingo # A data que salva o foguinho!
                )
                
            return redirect('dashboard')
            
    return redirect('dashboard')
