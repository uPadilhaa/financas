from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from despesas.forms import ConfiguracaoFinanceiraForm
from despesas.models import Usuario

@login_required
def configurar_financas(request):
    perfil, _ = Usuario.objects.get_or_create(user=request.user)

    if request.method == "POST":
        form = ConfiguracaoFinanceiraForm(request.POST, instance=perfil)
        if form.is_valid():
            form.save()
            messages.success(request, "Configurações financeiras atualizadas!")
            return redirect("dashboard")
    else:
        form = ConfiguracaoFinanceiraForm(instance=perfil)

    return render(request, "receitas/configuracao_form.html", {"form": form})