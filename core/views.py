from django.shortcuts import render, redirect
from .models import Atividade, MetaMensal
from django.db.models import Sum, Count
from django.db.models.functions import TruncDate
from datetime import datetime
from .forms import AtividadeForm

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
