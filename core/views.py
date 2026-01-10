from django.shortcuts import render, redirect
from .models import Atividade, MetaMensal
from django.db.models import Sum
from datetime import datetime
from .forms import AtividadeForm

def dashboard(request):
    hoje = datetime.now()
    
    # 1. Pegar a meta do mês atual
    meta = MetaMensal.objects.filter(mes=hoje.month, ano=hoje.year).first()
    meta_valor = meta.objetivo_km if meta else 1000 # Valor padrão caso não tenha meta cadastrada
    
    # 2. Calcular total de KM feitos por todos no mês
    total_acumulado = Atividade.objects.filter(
        data_envio__month=hoje.month, 
        data_envio__year=hoje.year
    ).aggregate(Sum('quantidade_km'))['quantidade_km__sum'] or 0
    
    # 3. Calcular porcentagem do tanque
    # core/views.py
    porcentagem = round((total_acumulado / meta_valor) * 100, 2)
    if porcentagem > 100: porcentagem = 100 # Tanque cheio!

    # 4. Ranking de usuários
    ranking = Atividade.objects.filter(
        data_envio__month=hoje.month
    ).values('nome_usuario').annotate(total=Sum('quantidade_km')).order_by('-total')

    context = {
        'total_acumulado': total_acumulado,
        'meta_valor': meta_valor,
        'porcentagem': porcentagem,
        'ranking': ranking,
    }
    return render(request, 'core/dashboard.html', context)

def registrar_km(request):
    if request.method == 'POST':
        form = AtividadeForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            return redirect('dashboard') # Redireciona para o tanque após salvar
    else:
        form = AtividadeForm()
    
    return render(request, 'core/registrar.html', {'form': form})