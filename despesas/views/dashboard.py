from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from despesas.services.dashboard_dados import obter_dados_dashboard
from despesas.services.dashboard_graficos import montar_graficos_dashboard


@login_required
def dashboard(request):    
    """
    View principal do Dashboard Financeiro.

    Orquestra a obtenção de dados brutos (services/dashboard_dados) e a
    geração dos gráficos (services/dashboard_graficos) para renderização.

    Args:
        request (HttpRequest): A requisição HTTP.

    Returns:
        HttpResponse: A página do dashboard renderizada com contexto e gráficos.
    """    
    dados = obter_dados_dashboard(request)
    contexto = dados["contexto"]
    graficos = montar_graficos_dashboard(dados)
    contexto["graficos"] = graficos
    return render(request, "dashboard.html", contexto)
