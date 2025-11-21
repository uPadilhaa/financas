from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.db.models import Q

from despesas.models import Receita
from despesas.forms import ReceitaForm

@login_required
def listar_receitas(request):
    busca = request.GET.get('busca')
    mes = request.GET.get('mes')
    ano = request.GET.get('ano')

    receitas = Receita.objects.filter(user=request.user)
    if busca:
        receitas = receitas.filter(descricao__icontains=busca)
    
    if mes and mes.isdigit():
        receitas = receitas.filter(data__month=int(mes))
    
    if ano and ano.isdigit():
        receitas = receitas.filter(data__year=int(ano))

    receitas = receitas.order_by("-data", "-id")
    hoje = timezone.localdate()
    anos_disponiveis = receitas.dates('data', 'year', order='DESC')

    context = {
        "receitas": receitas,
        "filtro_mes": mes,
        "filtro_ano": ano,
        "filtro_busca": busca,
        "anos_disponiveis": anos_disponiveis,
        "hoje": hoje
    }
    return render(request, "receitas/receita_lista.html", context)

@login_required
def criar_receita(request):
    if request.method == "POST":
        form = ReceitaForm(request.POST)
        if form.is_valid():
            receita = form.save(commit=False)
            receita.user = request.user
            receita.save()
            messages.success(request, "Renda registrada com sucesso!")
            return redirect("listar_receitas")
    else:
        form = ReceitaForm(initial={"data": timezone.localdate()})
    return render(request, "receitas/receita_form.html", {"form": form})

@login_required
def editar_receita(request, pk: int):
    receita = get_object_or_404(Receita, pk=pk, user=request.user)
    if request.method == "POST":
        form = ReceitaForm(request.POST, instance=receita)
        if form.is_valid():
            form.save()
            messages.success(request, "Renda atualizada.")
            return redirect("listar_receitas")
    else:
        form = ReceitaForm(instance=receita)
    return render(request, "receitas/receita_form.html", {"form": form, "edicao": True})

@login_required
def deletar_receita(request, pk: int):
    receita = get_object_or_404(Receita, pk=pk, user=request.user)
    if request.method == "POST":
        receita.delete()
        messages.success(request, "Renda removida.")
        return redirect("listar_receitas")
    return render(request, "despesas/confirmar_exclusao.html", {"objeto": receita, "tipo": "receita"})