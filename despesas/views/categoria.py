from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import IntegrityError
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from despesas.models import Categoria
from despesas.forms import CategoriaForm

@login_required
def listar_categorias(request):
    categorias = Categoria.objects.filter(user=request.user).order_by("nome")
    return render(request, "despesas/categoria_lista.html", {"categorias": categorias})


@login_required
@require_http_methods(["GET", "POST"])
def criar_categoria(request):
    if request.method == "POST":
        data = request.POST.copy()
        orcamento = data.get('orcamento_mensal')        
        if not orcamento:
            data['orcamento_mensal'] = '0'
        else:
            data['orcamento_mensal'] = orcamento.replace(',', '.')

        form = CategoriaForm(data, user=request.user)
        
        if form.is_valid():
            try:
                categoria = form.save()                
                if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                    return JsonResponse({
                        'success': True,
                        'id': categoria.id,
                        'nome': categoria.nome
                    })                
                return redirect("listar_categorias")
            
            except IntegrityError:
                msg = "Já existe uma categoria com este nome."
                if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                    return JsonResponse({'success': False, 'errors': {'nome': [msg]}}, status=400)
                form.add_error('nome', msg)
            except Exception as e:
                print(f"Erro ao criar categoria: {e}")
                if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                    return JsonResponse({'success': False, 'errors': {'__all__': ['Erro interno ao salvar.']}}, status=500)
        
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'errors': form.errors}, status=400)

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