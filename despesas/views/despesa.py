from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from django.utils import timezone
from django.db.models import Q
from django.http import JsonResponse
from dateutil.relativedelta import relativedelta
from itertools import groupby

from despesas.models import Despesa, Categoria, ItemDespesa
from despesas.forms import DespesaForm, ItemDespesaFormSet
from despesas.enums.forma_pagamento_enum import FormaPagamento 

@login_required
def listar_despesa(request):
    """
    Exibe a listagem de despesas do usuário com opções de filtro e agrupamento.

    Suporta filtros por busca textual, mês, ano e forma de pagamento.
    As despesas são agrupadas visualmente por mês/ano na interface.

    Args:
        request (HttpRequest): A requisição HTTP.

    Returns:
        HttpResponse: A página HTML renderizada com a lista de despesas.
    """
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

    despesas_agrupadas = []    
    def get_mes_ano(d):
        return d.data.strftime('%Y-%m')
    
    for key, group in groupby(despesas, key=get_mes_ano):
        lista_do_mes = list(group)
        total_do_mes = sum(d.valor for d in lista_do_mes)
        
        data_referencia = lista_do_mes[0].data if lista_do_mes else None

        despesas_agrupadas.append({
            'grouper': data_referencia, 
            'list': lista_do_mes,       
            'total': total_do_mes       
        })

    hoje = timezone.localdate()
    anos_disponiveis = despesas.dates('data', 'year', order='DESC')
    
    context = {
        "despesas_agrupadas": despesas_agrupadas, 
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
    """
    Processa o formulário de criação de nova despesa.

    Gerencia transações atômicas para salvar a despesa e seus itens relacionados.
    Realiza a divisão de valores em caso de parcelamento, criando múltiplos registros
    de despesa (um para cada mês futuro), ajustando centavos na primeira parcela.
    Dispara alertas de orçamento (Signals) após a confirmação da transação.

    Args:
        request (HttpRequest): A requisição HTTP.

    Returns:
        JsonResponse | HttpResponse: Resposta JSON para AJAX ou redirecionamento/renderização HTML.
    """
    if request.method == 'GET' and not request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return redirect('listar_despesa')

    if not Categoria.objects.filter(user=request.user).exists():
        Categoria.objects.create(user=request.user, nome="Outros")

    if request.method == "POST":
        form = DespesaForm(request.POST, user=request.user)
        formset = ItemDespesaFormSet(request.POST, prefix="itens")
        
        if form.is_valid() and formset.is_valid():
            try:
                from django.db.models.signals import post_save
                from despesas.signals import disparar_alerta_orcamento_ao_salvar_despesa, _agendar_verificacao
            
                post_save.disconnect(disparar_alerta_orcamento_ao_salvar_despesa, sender=Despesa)
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
                        primeira_despesa_salva = None                        
                        datas_para_verificar = set()                        
                        for i in range(qtd_parcelas):
                            parcela_cents = base_centavos + (1 if i < resto_centavos else 0)
                            valor_parcela_atual = Decimal(parcela_cents) / 100
                            desc_parcela = dados_base.get('desconto', 0) if i == 0 else 0                            
                            data_parcela = data_inicial + relativedelta(months=i)                            
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
                                data=data_parcela
                            )
                            nova_despesa.save()                            
                            datas_para_verificar.add((data_parcela.year, data_parcela.month))
                            if i == 0:
                                primeira_despesa_salva = nova_despesa
                            
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
                    
                        if primeira_despesa_salva:
                            from datetime import date
                            for ano_v, mes_v in datas_para_verificar:
                                data_ref = date(ano_v, mes_v, 1) 
                                transaction.on_commit(lambda d=data_ref: _agendar_verificacao(request.user, d))

                finally:
                    post_save.connect(disparar_alerta_orcamento_ao_salvar_despesa, sender=Despesa)
                msg = f"Despesa salva em {qtd_parcelas}x com sucesso!"
                messages.success(request, msg)
                return JsonResponse({'success': True, 'message': msg})
            except Exception as e:
                return JsonResponse({'success': False, 'error': str(e)}, status=500)        
        else:
            print("FORM ERRORS:", form.errors, form.non_field_errors())
            print("FORMSET ERRORS:", formset.errors, formset.non_form_errors())

            return render(
                request,
                "despesas/despesa_form/main.html",
                {"form": form, "formset": formset},
                status=400,
            ) 
    else:
        form = DespesaForm(user=request.user, initial={"data": timezone.localdate()})
        formset = ItemDespesaFormSet(queryset=ItemDespesa.objects.none(), prefix="itens",)
        return render(request, "despesas/despesa_form/main.html", {"form": form, "formset": formset})


@login_required
def editar_despesa(request, pk: int):
    """
    Exibe e processa o formulário de edição de uma despesa existente.

    Permite alterar dados da despesa e de seus itens (adicionar/remover/editar).
    Atualiza o contador cacheado 'qtd_total_itens' após o salvamento.

    Args:
        request (HttpRequest): A requisição HTTP.
        pk (int): Chave primária da despesa a ser editada.

    Returns:
        JsonResponse | HttpResponse: Redirecionamento ou resposta JSON de sucesso.
    """
    despesa = get_object_or_404(Despesa, pk=pk, user=request.user)
    if request.method == "POST":
        form = DespesaForm(request.POST, instance=despesa, user=request.user)
        formset = ItemDespesaFormSet(request.POST, instance=despesa, prefix="itens")
        
        if form.is_valid() and formset.is_valid():
            with transaction.atomic():
                despesa_salva = form.save()
                formset.save()                
                qtd_itens = despesa_salva.itens.count()                
                if despesa_salva.qtd_total_itens != qtd_itens:
                    Despesa.objects.filter(pk=despesa_salva.pk).update(qtd_total_itens=qtd_itens)
            
            messages.success(request, "Despesa atualizada!", extra_tags="despesa")                    
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                 return JsonResponse({'success': True})
            
            return redirect("listar_despesa")
        else:
            print("ERRO DE VALIDAÇÃO:")
            print("Form:", form.errors)
            print("Formset:", formset.errors)
            pass
    else:
        form = DespesaForm(instance=despesa, user=request.user)
        formset = ItemDespesaFormSet(instance=despesa, prefix="itens")

    context = {
        "form": form, 
        "formset": formset, 
        "edicao": True, 
        "despesa_obj": despesa 
    }
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
         return render(request, "despesas/despesa_form/main.html", context)

    return render(request, "despesas/despesa_form/despesa_form_completo.html", context)

@login_required
def deletar_despesa(request, pk: int):
    """
    Exibe a confirmação e processa a exclusão de uma despesa.

    Args:
        request (HttpRequest): A requisição HTTP.
        pk (int): Chave primária da despesa a ser excluída.

    Returns:
        HttpResponse: Página de confirmação ou redirecionamento após exclusão.
    """
    despesa = get_object_or_404(Despesa, pk=pk, user=request.user)
    if request.method == "POST":
        despesa.delete()
        messages.success(request, "Despesa excluída com sucesso!")
        return redirect("listar_despesa")
    return render(request, "despesas/confirmar_exclusao.html", {"objeto": despesa, "tipo": "despesa"})