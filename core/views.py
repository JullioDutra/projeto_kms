from django.shortcuts import render, redirect
from .models import Atividade, MetaMensal
from django.db.models import Sum, Count
from django.db.models.functions import TruncDate
from datetime import datetime
from .forms import AtividadeForm
from django.db.models.functions import ExtractWeekDay
from django.db.models import Sum, Avg, Count, Max
from datetime import timedelta
import calendar

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
    atletas = Atividade.objects.values_list('nome_usuario', flat=True).distinct().order_by('nome_usuario')
    atleta_selecionado = request.GET.get('atleta')
    context = {'atletas': atletas, 'atleta_selecionado': atleta_selecionado}

    if atleta_selecionado:
        atividades = Atividade.objects.filter(nome_usuario=atleta_selecionado).order_by('-data_envio')
        
        if atividades.exists():
            hoje = datetime.now()
            mes_atual = hoje.month
            ano_atual = hoje.year
            
            mes_passado = 12 if mes_atual == 1 else mes_atual - 1
            ano_passado = ano_atual - 1 if mes_atual == 1 else ano_atual

            # 1. Comparativo de Meses (KMs)
            km_atual = atividades.filter(data_envio__month=mes_atual, data_envio__year=ano_atual).aggregate(Sum('quantidade_km'))['quantidade_km__sum'] or 0
            km_passado = atividades.filter(data_envio__month=mes_passado, data_envio__year=ano_passado).aggregate(Sum('quantidade_km'))['quantidade_km__sum'] or 0

            variacao_pct = 0
            if km_passado > 0:
                variacao_pct = ((float(km_atual) - float(km_passado)) / float(km_passado)) * 100
            elif km_atual > 0:
                variacao_pct = 100 

            # 2. Estatísticas Avançadas & Projeção
            media_km = atividades.aggregate(Avg('quantidade_km'))['quantidade_km__avg'] or 0
            total_corridas = atividades.count()
            maior_corrida = atividades.aggregate(Max('quantidade_km'))['quantidade_km__max'] or 0
            
            # Projeção de fim de mês
            _, ult_dia_mes = calendar.monthrange(ano_atual, mes_atual)
            dia_hoje = hoje.day
            projecao_mensal = (float(km_atual) / dia_hoje) * ult_dia_mes if dia_hoje > 0 else 0

            total_km_historico = atividades.aggregate(Sum('quantidade_km'))['quantidade_km__sum'] or 0
            calorias_queimadas = float(total_km_historico) * 65 
            fatias_pizza = int(calorias_queimadas / 285) 

            # 3. Dia Favorito e Calendário
            fav_day_query = atividades.annotate(dia=ExtractWeekDay('data_envio')).values('dia').annotate(count=Count('id')).order_by('-count').first()
            
            # Converter dia do Django (1=Dom, 7=Sáb) para Python (0=Seg, 6=Dom)
            fav_idx = (fav_day_query['dia'] - 2) % 7 if fav_day_query else 6 # Padrão Domingo se não tiver
            
            dias_pt = {0: 'Segunda', 1: 'Terça', 2: 'Quarta', 3: 'Quinta', 4: 'Sexta', 5: 'Sábado', 6: 'Domingo'}
            dia_favorito = dias_pt[fav_idx]

            # 4. Cálculo de Pace e Última Corrida
            ultima = atividades.first()
            km_recomendado = float(ultima.quantidade_km) * 1.10 
            default_pace = ultima.pace if (ultima and ultima.pace) else "06:00"

            pace_rec_leve = "06:00"
            pace_rec_forte = "05:00"
            if ultima.pace and ':' in ultima.pace:
                try:
                    m, s = map(int, ultima.pace.split(':'))
                    t_seg = (m * 60) + s
                    pace_rec_leve = f"{(t_seg + 45)//60:02d}:{(t_seg + 45)%60:02d}"
                    pace_rec_forte = f"{(t_seg - 15)//60:02d}:{(t_seg - 15)%60:02d}"
                except: pass

            # 5. GERADOR DO CALENDÁRIO INTELIGENTE (7 DIAS)
            plano_semanal = []
            for i in range(7):
                d_date = hoje + timedelta(days=i)
                d_idx = d_date.weekday()
                
                # Regras simples do Coach baseadas no dia favorito
                if d_idx == fav_idx:
                    tipo, cor, icon, desc = "Treino Longo", "warning", "🏃‍♂️🔥", f"Até {round(km_recomendado,1)}km"
                elif (d_idx - fav_idx) % 7 == 1: # Dia seguinte ao longo
                    tipo, cor, icon, desc = "Descanso", "secondary", "🛌💤", "Recuperação total"
                elif (d_idx - fav_idx) % 7 == -3 or (d_idx - fav_idx) % 7 == 4: # Meio da semana
                    tipo, cor, icon, desc = "Tiros/Ritmo", "danger", "⚡⏱️", f"Pace {pace_rec_forte}"
                else:
                    tipo, cor, icon, desc = "Rodagem Leve", "success", "🍃👟", f"Pace {pace_rec_leve}"
                    
                plano_semanal.append({
                    'data': d_date.strftime("%d/%m"),
                    'dia_semana': dias_pt[d_idx],
                    'tipo': tipo, 'cor': cor, 'icon': icon, 'desc': desc,
                    'is_hoje': i == 0
                })

            context.update({
                'km_atual': km_atual, 'km_passado': km_passado, 'variacao_pct': round(variacao_pct, 1),
                'media_km': round(media_km, 2), 'total_corridas': total_corridas, 'maior_corrida': maior_corrida,
                'projecao_mensal': round(projecao_mensal, 1),
                'dia_favorito': dia_favorito, 'ultima': ultima, 'default_pace': default_pace,
                'calorias': int(calorias_queimadas), 'pizzas': fatias_pizza,
                'plano_semanal': plano_semanal # Enviando o calendário
            })

    return render(request, 'core/desempenho.html', context)
