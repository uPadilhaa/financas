from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from django.utils import timezone
from django.db.models import Q
from django.http import JsonResponse
from dateutil.relativedelta import relativedelta

from despesas.models import Despesa, Categoria, ItemDespesa
from despesas.forms import DespesaForm, ItemDespesaFormSet
from despesas.enums.forma_pagamento_enum import FormaPagamento 

@login_required
def listar_despesa(request):
    busca = request.GET.get('busca')
    mes = request.GET.get('mes')
    ano = request.GET.get('ano')
    pagamento = request.GET.get('pagamento')

    despesas = Despesa.objects.filter(user=request.user)

    if busca:
        despesas = despesas.filter(
            Q(emitente_nome__icontains=busca) | 
            Q(descricao__icontains=busca)
        )
    
    if mes and mes.isdigit():
        despesas = despesas.filter(data__month=int(mes))
    
    if ano and ano.isdigit():
        despesas = despesas.filter(data__year=int(ano))
    
    if pagamento:
        despesas = despesas.filter(forma_pagamento=pagamento)

    despesas = despesas.order_by("-data", "-id")

    hoje = timezone.localdate()
    anos_disponiveis = despesas.dates('data', 'year', order='DESC')
    
    context = {
        "despesas": despesas,
        "opcoes_pagamento": FormaPagamento.choices, 
        "filtro_mes": mes,
        "filtro_ano": ano,
        "filtro_busca": busca,
        "filtro_pagamento": pagamento,
        "anos_disponiveis": anos_disponiveis,
        "hoje": hoje
    }

    return render(request, "despesas/despesa_lista.html", context)

@login_required
def criar_despesa(request):
    if request.method == 'GET' and not request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return redirect('listar_despesa')

    if not Categoria.objects.filter(user=request.user).exists():
        Categoria.objects.create(user=request.user, nome="Outros")

    if request.method == "POST":
        form = DespesaForm(request.POST, user=request.user)
        formset = ItemDespesaFormSet(request.POST)
        
        if form.is_valid() and formset.is_valid():
            try:
                with transaction.atomic():
                    dados_base = form.cleaned_data                    
                    try:
                        qtd_parcelas = int(dados_base.get('parcelas_selecao') or 1)
                    except (ValueError, TypeError):
                        qtd_parcelas = 1                        
                    valor_total_compra = dados_base.get('valor') 
                    data_inicial = dados_base.get('data')
                    total_centavos = int(valor_total_compra * 100)
                    base_centavos = total_centavos // qtd_parcelas
                    resto_centavos = total_centavos % qtd_parcelas
                    
                    for i in range(qtd_parcelas):
                        parcela_cents = base_centavos + (1 if i < resto_centavos else 0)
                        valor_parcela_atual = Decimal(parcela_cents) / 100
                        desc_parcela = dados_base.get('desconto', 0) if i == 0 else 0

                        nova_despesa = Despesa(
                            user=request.user,
                            categoria=dados_base['categoria'],
                            emitente_nome=dados_base['emitente_nome'],
                            emitente_cnpj=dados_base['emitente_cnpj'],
                            descricao=dados_base['descricao'],
                            forma_pagamento=dados_base['forma_pagamento'],
                            tipo=dados_base['tipo'],
                            observacoes=dados_base['observacoes'],
                            desconto=desc_parcela,                            
                            valor=valor_parcela_atual,
                            parcela_atual=i + 1,
                            total_parcelas=qtd_parcelas,
                            data=data_inicial + relativedelta(months=i)
                        )
                        nova_despesa.save()
                        itens_para_criar = []
                        for item_data in formset.cleaned_data:
                            if item_data and not item_data.get('DELETE') and item_data.get('nome'):                                
                                v_tot = item_data.get('valor_total') or 0
                                v_unit = item_data.get('valor_unitario') or 0                                
                                itens_para_criar.append(ItemDespesa(
                                    despesa=nova_despesa,
                                    nome=item_data.get('nome'),
                                    codigo=item_data.get('codigo'),
                                    quantidade=item_data.get('quantidade'),
                                    valor_unitario=v_unit / qtd_parcelas,
                                    valor_total=v_tot / qtd_parcelas
                                ))
                        
                        if itens_para_criar:
                            ItemDespesa.objects.bulk_create(itens_para_criar)
                            nova_despesa.qtd_total_itens = len(itens_para_criar)
                            nova_despesa.save()

                msg = f"Despesa salva em {qtd_parcelas}x com sucesso!"
                messages.success(request, msg)
                return JsonResponse({'success': True, 'message': msg})
            except Exception as e:
                return JsonResponse({'success': False, 'error': str(e)}, status=500)
        
        else:
            return render(request, "despesas/despesa_form/main.html", {"form": form, "formset": formset}, status=400)    
    else:
        form = DespesaForm(user=request.user, initial={"data": timezone.localdate()})
        formset = ItemDespesaFormSet(queryset=ItemDespesa.objects.none())
        if formset.total_form_count() == 0: 
            formset.extra = 1
        return render(request, "despesas/despesa_form/main.html", {"form": form, "formset": formset})

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
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                 return JsonResponse({'success': True})
            return redirect("listar_despesa")
    else:
        form = DespesaForm(instance=despesa, user=request.user)
        formset = ItemDespesaFormSet(instance=despesa)

    return render(request, "despesas/despesa_form/despesa_form.html", {
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