from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.utils import timezone
from despesas.models import Receita, Despesa, Usuario

from despesas.services.dashboard_dados import obter_dados_dashboard

def home(request):
    context = {}
    if request.user.is_authenticated:
        try:
            dados = obter_dados_dashboard(request)
            context = dados["contexto"]
        except Exception:
             # Em caso de erro (ex: banco vazio), falha silenciosa para renderizar home normal
             pass
    return render(request, "home.html", context)

def pagina_login(request):
    return render(request, "account/login.html")

def pagina_cadastro(request):
    return render(request, "account/signup.html")