
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from despesas.forms.configuracao import ConfiguracaoRendaForm, ConfiguracaoNotificacaoForm
from despesas.models import Usuario

@login_required
def onboarding_renda(request):
    perfil, _ = Usuario.objects.get_or_create(user=request.user)
    if request.method == "POST":
        form = ConfiguracaoRendaForm(request.POST, instance=perfil)
        if form.is_valid():
            form.save()
            messages.success(request, "Renda salva com sucesso!")
            return redirect("onboarding_notificacoes")
    else:
        form = ConfiguracaoRendaForm(instance=perfil)
    return render(request, "onboarding/passo_renda.html", {"form": form})

@login_required
def onboarding_notificacoes(request):
    perfil, _ = Usuario.objects.get_or_create(user=request.user)
    if not perfil.renda_fixa:
        return redirect("onboarding_renda")

    if request.method == 'POST':
        form = ConfiguracaoNotificacaoForm(request.POST, instance=perfil)
        if form.is_valid():
            form.save()
            messages.success(request, "Configuração finalizada! Bem-vindo.")
            return redirect("dashboard") 
    else:
        form = ConfiguracaoNotificacaoForm(instance=perfil)

    return render(request, 'onboarding/passo_notificacoes.html', {'form': form})