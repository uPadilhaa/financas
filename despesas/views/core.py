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