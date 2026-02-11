from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
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
    is_modal = request.GET.get('modal') == 'true'
    if request.method == 'POST':
        form = ConfiguracaoNotificacaoForm(request.POST, instance=perfil)
        if form.is_valid():
            form.save()
            messages.success(request, "Preferências de notificação atualizadas!")
            return redirect('listar_despesa')
    else:
        form = ConfiguracaoNotificacaoForm(instance=perfil)

    if is_modal:
        return render(request, 'configuracao_notificacoes_modal.html', {'form': form})
    
    return render(request, 'configuracao_notificacoes.html', {'form': form})


@login_required
def deletar_conta(request):
    if request.method == "POST":
        from despesas.forms.configuracao import DeleteAccountForm
        from django.contrib.auth import logout
        
        form = DeleteAccountForm(request.POST)
        if form.is_valid():
            user = request.user
            logout(request)
            user.delete()
            messages.success(request, "Sua conta foi excluída com sucesso.")
            return redirect("home") 
    else:
        from despesas.forms.configuracao import DeleteAccountForm
        form = DeleteAccountForm()

    return render(request, "deletar_conta.html", {"form": form})