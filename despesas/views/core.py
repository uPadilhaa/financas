from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.utils import timezone
from despesas.models import Receita, Despesa, Usuario

def home(request):
    return render(request, "home.html")

def pagina_login(request):
    return render(request, "auth/login.html")

def pagina_cadastro(request):
    return render(request, "auth/cadastro.html")

@login_required
def dashboard(request):
    hoje = timezone.localdate()
    perfil, _ = Usuario.objects.get_or_create(user=request.user)
    renda_fixa = perfil.renda_fixa
    investimento_fixo = perfil.investimento_fixo
    receitas_extras = Receita.objects.filter(user=request.user, data__month=hoje.month, data__year=hoje.year)    
    extra_bruto = receitas_extras.aggregate(Sum('valor_bruto'))['valor_bruto__sum'] or 0
    extra_investido = receitas_extras.aggregate(Sum('valor_investimento'))['valor_investimento__sum'] or 0
    total_bruto = extra_bruto
    total_investido = investimento_fixo + extra_investido    
    receita_disponivel = (renda_fixa + total_bruto) - total_investido
    despesas = Despesa.objects.filter(user=request.user, data__month=hoje.month, data__year=hoje.year)
    total_gasto = despesas.aggregate(Sum('valor'))['valor__sum'] or 0
    saldo = receita_disponivel - total_gasto
    context = {
        "mes_atual": hoje,
        "perfil": perfil,
        "total_bruto": total_bruto,
        "extra_bruto": extra_bruto,  
        "total_investido": total_investido,
        "receita_disponivel": receita_disponivel,
        "total_gasto": total_gasto,
        "saldo": saldo,
        "tem_renda_extra": extra_bruto > 0
    }
    return render(request, "dashboard.html", context)