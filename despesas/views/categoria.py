from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import IntegrityError

from despesas.models import Categoria
from despesas.forms import CategoriaForm

@login_required
def listar_categorias(request):
    categorias = Categoria.objects.filter(user=request.user).order_by("nome")
    return render(request, "despesas/categoria_lista.html", {"categorias": categorias})

@login_required
def criar_categoria(request):
    if request.method == "POST":
        form = CategoriaForm(request.POST, user=request.user)
        if form.is_valid():
            try:
                form.save()
                messages.success(request, "Categoria criada.", extra_tags="categoria")
                return redirect("listar_categorias")
            except IntegrityError:
                form.add_error("nome", "Você já possui uma categoria com esse nome.")
    else:
        form = CategoriaForm(user=request.user)
    return render(request, "despesas/categoria_form.html", {"form": form})

@login_required
def editar_categoria(request, pk: int):
    categoria = get_object_or_404(Categoria, pk=pk, user=request.user)
    if request.method == "POST":
        form = CategoriaForm(request.POST, instance=categoria, user=request.user)
        if form.is_valid():
            try:
                form.save()
                messages.success(request, "Categoria atualizada.")
                return redirect("listar_categorias")
            except IntegrityError:
                form.add_error("nome", "Nome já existe.")
    else:
        form = CategoriaForm(instance=categoria, user=request.user)
    return render(request, "despesas/categoria_form.html", {"form": form, "edicao": True})

@login_required
def deletar_categoria(request, pk: int):
    categoria = get_object_or_404(Categoria, pk=pk, user=request.user)
    if request.method == "POST":
        categoria.delete()
        messages.success(request, "Categoria excluída.")
        return redirect("listar_categorias")
    return render(request, "despesas/confirmar_exclusao.html", {"objeto": categoria, "tipo": "categoria"})