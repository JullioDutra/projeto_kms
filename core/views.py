from django.shortcuts import render, redirect
from .models import Atividade, MetaMensal
from django.db.models import Sum, Count
from django.db.models.functions import TruncDate
from datetime import datetime
from .forms import AtividadeForm
from django.db.models.functions import ExtractWeekDay
from django.db.models import Avg
from datetime import timedelta

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
        data_envio__month=hoje.month,
        data_envio__year=hoje.year
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
        total_km_geral=Sum('quantidade_km'),
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
    # Pega todos os nomes únicos que já registraram corridas
    atletas = Atividade.objects.values_list('nome_usuario', flat=True).distinct().order_by('nome_usuario')
    atleta_selecionado = request.GET.get('atleta')
    context = {'atletas': atletas, 'atleta_selecionado': atleta_selecionado}

    if atleta_selecionado:
        atividades = Atividade.objects.filter(nome_usuario=atleta_selecionado).order_by('-data_envio')
        
        if atividades.exists():
            hoje = datetime.now()
            mes_atual = hoje.month
            ano_atual = hoje.year
            
            # Lógica para achar mês passado
            mes_passado = 12 if mes_atual == 1 else mes_atual - 1
            ano_passado = ano_atual - 1 if mes_atual == 1 else ano_atual

            # 1. Comparativo de Meses (KMs)
            km_atual = atividades.filter(data_envio__month=mes_atual, data_envio__year=ano_atual).aggregate(Sum('quantidade_km'))['quantidade_km__sum'] or 0
            km_passado = atividades.filter(data_envio__month=mes_passado, data_envio__year=ano_passado).aggregate(Sum('quantidade_km'))['quantidade_km__sum'] or 0

            variacao_pct = 0
            if km_passado > 0:
                variacao_pct = ((km_atual - km_passado) / float(km_passado)) * 100
            elif km_atual > 0:
                variacao_pct = 100 # Se não correu mês passado, crescimento de 100%

            # 2. Estatísticas Gerais
            media_km = atividades.aggregate(Avg('quantidade_km'))['quantidade_km__avg'] or 0
            total_corridas = atividades.count()

            # 3. Dia Favorito
            dias_semana = ['Domingo', 'Segunda-feira', 'Terça-feira', 'Quarta-feira', 'Quinta-feira', 'Sexta-feira', 'Sábado']
            fav_day_query = atividades.annotate(dia=ExtractWeekDay('data_envio')).values('dia').annotate(count=Count('id')).order_by('-count').first()
            dia_favorito = dias_semana[fav_day_query['dia'] - 1] if fav_day_query else "Indefinido"

            # 4. Smart Coach: Recomendações baseadas na última corrida
            ultima = atividades.first()
            km_recomendado = float(ultima.quantidade_km) * 1.10 # Regra de ouro: aumentar max 10% do volume
            
            # Cálculo de Pace recomendado
            pace_rec_leve = "06:00"
            pace_rec_forte = "05:00"
            if ultima.pace and ':' in ultima.pace:
                try:
                    minutos, segundos = map(int, ultima.pace.split(':'))
                    total_segundos = (minutos * 60) + segundos
                    
                    seg_leve = total_segundos + 45 # Treino regenerativo (+45s)
                    seg_forte = total_segundos - 15 # Treino de tiro/tempo run (-15s)
                    
                    pace_rec_leve = f"{seg_leve//60:02d}:{seg_leve%60:02d}"
                    pace_rec_forte = f"{seg_forte//60:02d}:{seg_forte%60:02d}"
                except:
                    pass

            # Quando correr de novo?
            dias_descanso = 2 if float(ultima.quantidade_km) > 10 else 1
            prox_data = ultima.data_envio + timedelta(days=dias_descanso)
            
            mensagem_data = ""
            if prox_data.date() <= hoje.date():
                mensagem_data = "Hoje! Seu corpo já está descansado."
            else:
                mensagem_data = f"{prox_data.strftime('%d/%m/%Y')} (Amanhã)"

            context.update({
                'km_atual': km_atual,
                'km_passado': km_passado,
                'variacao_pct': round(variacao_pct, 1),
                'media_km': round(media_km, 2),
                'total_corridas': total_corridas,
                'dia_favorito': dia_favorito,
                'ultima': ultima,
                'km_recomendado': round(km_recomendado, 2),
                'pace_rec_leve': pace_rec_leve,
                'pace_rec_forte': pace_rec_forte,
                'mensagem_data': mensagem_data
            })

    return render(request, 'core/desempenho.html', context)
