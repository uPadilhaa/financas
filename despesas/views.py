from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .forms import DespesaForm, CategoriaForm
from .models import Despesa, Categoria


def home(request):
    return render(request, "home.html")

def pagina_login(request):
    return render(request, "auth/login.html")

def pagina_cadastro(request):
    return render(request, "auth/cadastro.html")

@login_required
def listar_despesa(request):
    despesas = Despesa.objects.filter(user=request.user).order_by("-data", "-id")
    return render(request, "despesas/despesa_lista.html", {"despesas": despesas})



@login_required
def criar_despesa(request):
    # garante que o usuário tenha ao menos uma categoria
    if not Categoria.objects.filter(user=request.user).exists():
        Categoria.objects.create(user=request.user, nome="Outros")

    if request.method == "POST":
        form = DespesaForm(request.POST, user=request.user)
        if form.is_valid():
            despesa = form.save(commit=False)
            despesa.user = request.user
            despesa.save()
            messages.success(request, "Despesa registrada com sucesso!", extra_tags="despesa")
            return redirect("listar_despesa")
    else:
        form = DespesaForm(user=request.user, initial={"data": timezone.localdate()})

    return render(request, "despesas/despesa_form.html", {"form": form})


@login_required
def editar_despesa(request, pk: int):
    despesa = get_object_or_404(Despesa, pk=pk, user=request.user)

    if request.method == "POST":
        form = DespesaForm(request.POST, instance=despesa, user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Despesa atualizada com sucesso!", extra_tags="despesa")
            return redirect("listar_despesa")
    else:
        form = DespesaForm(instance=despesa, user=request.user)

    return render(request, "despesas/despesa_form.html", {"form": form, "edicao": True})




@login_required
def criar_categoria(request):
    if request.method == "POST":
        form = CategoriaForm(request.POST, user=request.user)
        if form.is_valid():
            try:
                with transaction.atomic():
                    form.save()
            except IntegrityError:
                form.add_error("nome", "Você já possui uma categoria com esse nome.")
            else:
                messages.success(request, "Categoria criada com sucesso.", extra_tags="categoria")
                return redirect("listar_despesa")
    else:
        form = CategoriaForm(user=request.user)

    return render(request, "despesas/categoria_form.html", {"form": form})