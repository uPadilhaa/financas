from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django import forms
from despesas.models import ItemDespesa, Despesa
from despesas.forms import DespesaForm, UploadNFeForm, ItemDespesaForm
from despesas.services.nfe_service import NFeService
import logging

logger = logging.getLogger(__name__)

@login_required
def importar_NFe(request):
    """
    Controlador para o processo de importação de NFe (Nota Fiscal Eletrônica).

    Recebe o upload de imagem (QR Code) ou PDF. Delega o processamento ao NFeService,
    captura os dados retornados (emitente, totais, itens) e prepara o formulário
    de despesa pré-preenchido para revisão do usuário.

    Args:
        request (HttpRequest): A requisição HTTP contendo o arquivo 'imagem'.

    Returns:
        HttpResponse: Renderiza o formulário de despesa preenchido ou a página de upload.
    """
    if request.method == "POST":
        form = UploadNFeForm(request.POST, request.FILES)
        if not form.is_valid():
            return render(request, "despesas/importar_NFe.html", {"form": form})

        arquivo = form.cleaned_data["imagem"]
        content_type = (arquivo.content_type or "").lower()
        filename = (arquivo.name or "").lower()        
        scraped = {}
        url = None
        is_pdf = content_type == 'application/pdf' or filename.endswith('.pdf')
        
        service = NFeService()

        try:
            if is_pdf:
                scraped = service.parse_nfe_danfe_pdf(arquivo)
            else:
                img_bytes = arquivo.read()
                url = service.transform_qr_pra_bytes(img_bytes)
                if url:
                    scraped = service.scrape_nfe_url(url)
        except Exception as e:
            logger.error(f"Error importing NFe: {e}")

        
        emitente = scraped.get("emitente") or ""
        pagamento_detectado = scraped.get("forma_pagamento_key")        
        initial_data = {
            "emitente_nome": emitente,
            "emitente_cnpj": scraped.get("cnpj") or "",
            "descricao": emitente,
            "valor": scraped.get("valor_total") or 0, 
            "desconto": scraped.get("desconto") or 0,
            "parcelas_selecao": scraped.get("parcelas") or 1,
            "forma_pagamento": pagamento_detectado if pagamento_detectado else None,
            "data": scraped.get("data_emissao") or timezone.localdate(),
            "categoria": service.prever_categoria(request.user, emitente or ""),
            "observacoes": f"Importado via QR Code.\nLink SEFAZ: {url}" if (url and not is_pdf) else "Importado via arquivo."
        }

        form_desp = DespesaForm(user=request.user, initial=initial_data)        
        initial_itens = []
        for item in scraped.get("itens", []):
            initial_itens.append({
                'nome': item['nome'],
                'quantidade': str(item['qtd']).replace('.', ','), 
                'unidade': item.get('unidade', 'UN'), 
                'valor_unitario': str(item['vl_unit']).replace('.', ','),
                'valor_total': str(item['vl_total']).replace('.', ',')
            })
            
        qtd_itens = len(initial_itens) or 1
        
        ItemDespesaNFeFormSet = forms.inlineformset_factory(
            Despesa, 
            ItemDespesa, 
            form=ItemDespesaForm,
            extra=qtd_itens, 
            min_num=0, 
            validate_min=False,
            can_delete=True
        )
        
        formset = ItemDespesaNFeFormSet(
            queryset=ItemDespesa.objects.none(), 
            initial=initial_itens,
            prefix='itens' 
        )

        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return render(request, "despesas/despesa_form/main.html", {
                "form": form_desp, 
                "formset": formset
            })

        return render(request, "despesas/despesa_form/despesa_form_completo.html", {"form": form_desp, "formset": formset})

    return render(request, "despesas/importar_NFe.html", {"form": UploadNFeForm()})