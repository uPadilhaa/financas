from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.http import require_POST
from despesas.forms.configuracao import ConfiguracaoRendaForm, ConfiguracaoNotificacaoForm 
from despesas.models import Usuario

@login_required
def configurar_financas(request):
    perfil, _ = Usuario.objects.get_or_create(user=request.user)

    if request.method == "POST":
        form = ConfiguracaoRendaForm(request.POST, instance=perfil)
        if form.is_valid():
            form.save()
            messages.success(request, "Dados de renda atualizados!")
            return redirect("dashboard")
    else:
        form = ConfiguracaoRendaForm(instance=perfil)

    return render(request, "receitas/configuracao_form.html", {"form": form})

@login_required
def configurar_notificacoes(request):
    perfil, _ = Usuario.objects.get_or_create(user=request.user)

    if request.method == 'POST':
        form = ConfiguracaoNotificacaoForm(request.POST, instance=perfil)
        if form.is_valid():
            form.save()
            messages.success(request, "Preferências de notificação atualizadas!")
            return redirect('configurar_notificacoes')
    else:
        form = ConfiguracaoNotificacaoForm(instance=perfil)

    return render(request, 'configuracao_notificacoes.html', {'form': form})