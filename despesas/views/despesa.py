import json
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from django.utils import timezone

from despesas.models import Despesa, Categoria, ItemDespesa
from despesas.forms import DespesaForm, ItemDespesaFormSet

@login_required
def listar_despesa(request):
    despesas = Despesa.objects.filter(user=request.user).order_by("-data", "-id")
    return render(request, "despesas/despesa_lista.html", {"despesas": despesas})

@login_required
def criar_despesa(request):
    if not Categoria.objects.filter(user=request.user).exists():
        Categoria.objects.create(user=request.user, nome="Outros")

    if request.method == "POST":
        form = DespesaForm(request.POST, user=request.user)
        formset = ItemDespesaFormSet(request.POST)
        
        if form.is_valid() and formset.is_valid():
            with transaction.atomic():
                despesa = form.save(commit=False)
                despesa.user = request.user
                despesa.save()
                
                formset.instance = despesa
                formset.save()
                
                despesa.qtd_total_itens = despesa.itens.count()
                despesa.save()
                
            messages.success(request, "Despesa registrada!", extra_tags="despesa")
            return redirect("listar_despesa")
    else:
        form = DespesaForm(user=request.user, initial={"data": timezone.localdate()})
        formset = ItemDespesaFormSet(queryset=ItemDespesa.objects.none())

    return render(request, "despesas/despesa_form.html", {"form": form, "formset": formset})

@login_required
def editar_despesa(request, pk: int):
    despesa = get_object_or_404(Despesa, pk=pk, user=request.user)

    if request.method == "POST":
        form = DespesaForm(request.POST, instance=despesa, user=request.user)
        formset = ItemDespesaFormSet(request.POST, instance=despesa)
        
        if form.is_valid() and formset.is_valid():
            with transaction.atomic():
                form.save()
                formset.save()
                despesa.refresh_from_db()
                despesa.qtd_total_itens = despesa.itens.count()
                despesa.save()

            messages.success(request, "Despesa atualizada!", extra_tags="despesa")
            return redirect("listar_despesa")
    else:
        form = DespesaForm(instance=despesa, user=request.user)
        formset = ItemDespesaFormSet(instance=despesa)

    return render(request, "despesas/despesa_form.html", {
        "form": form, 
        "formset": formset, 
        "edicao": True, 
        "despesa_obj": despesa 
    })

@login_required
def deletar_despesa(request, pk: int):
    despesa = get_object_or_404(Despesa, pk=pk, user=request.user)
    if request.method == "POST":
        despesa.delete()
        messages.success(request, "Despesa excluída com sucesso!")
        return redirect("listar_despesa")
    return render(request, "despesas/confirmar_exclusao.html", {"objeto": despesa, "tipo": "despesa"})