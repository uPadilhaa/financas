import re
import requests
import cv2
import numpy as np
from bs4 import BeautifulSoup
from qreader import QReader
from dateutil import parser as dateparser
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.utils import timezone

from despesas.models import ItemDespesa, Categoria
from despesas.forms import DespesaForm, ItemDespesaFormSet, UploadNFeForm
from despesas.enums.forma_pagamento_enum import FormaPagamento

qreader = QReader()

def _decode_qr_from_bytes(img_bytes: bytes) -> str | None:
    nparr = np.frombuffer(img_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if img is None: return None    
    decoded = qreader.detect_and_decode(image=img)
    if decoded and decoded[0]: return decoded[0]    
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    thresh = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 21, 11)
    decoded = qreader.detect_and_decode(image=thresh)
    if decoded and decoded[0]: return decoded[0]
    
    return None

def _clean_float(s):
    if not s: return 0.0
    s = str(s).strip()
    s = re.sub(r'[^\d,.-]', '', s)
    if ',' in s and '.' in s:
        s = s.replace('.', '').replace(',', '.')
    elif ',' in s:
        s = s.replace(',', '.')
    
    try:
        return float(s)
    except ValueError:
        return 0.0

def _predict_category(user, emitente_nome: str) -> int | None:
    if not emitente_nome: return None
    txt = emitente_nome.lower()
    regras = {
        "Mercado": ["supermercado", "mercado", "zaffari", "carrefour", "big", "nacional", "atacado", "bistek", "center shop", "dia%", "stock center", "comercial zaffari", "maxxi", "kan", "macromix"],
        "Farmácia": ["farmacia", "drogaria", "panvel", "são joão", "pague menos", "raia", "drogasil", "bifarma", "ultrafarma"],
        "Transporte": ["posto", "combustivel", "ipiranga", "shell", "petrobras", "uber", "99pop", "abastecimento"],
        "Alimentação": ["restaurante", "lancheria", "burger", "mcdonalds", "subway", "ifood", "bar", "padaria", "confeitaria", "pizzaria"],
        "Vestuário": ["lojas renner", "riachuelo", "c&a", "zara", "cea", "marisa", "pompéia", "shein"],
        "Casa": ["ferragem", "construção", "leroy", "cassol", "telhanorte", "eletrica", "comercial dalacorte"],
    }
    sugestao = None
    for categoria_chave, keywords in regras.items():
        for kw in keywords:
            if kw in txt:
                sugestao = categoria_chave
                break
        if sugestao: break
    if sugestao:
        cat = Categoria.objects.filter(user=user, nome__icontains=sugestao).first()
        if cat: return cat.pk
    return None

def _predict_payment_method(text: str) -> str:
    t = text.lower()
    if "crédito" in t: return FormaPagamento.CREDITO
    if "débito" in t: return FormaPagamento.DEBITO
    if "pix" in t: return FormaPagamento.PIX
    if "dinheiro" in t: return FormaPagamento.DINHEIRO
    return FormaPagamento.OUTROS

def _scrape_NFe_page(url: str) -> dict:
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0"}
    try:
        resp = requests.get(url, headers=headers, timeout=20)
        resp.raise_for_status()
    except Exception: return {}
    
    soup = BeautifulSoup(resp.text, "html.parser")    
    emitente = "Consumidor"
    cnpj = None
    div_topo = soup.find("div", class_="txtTopo")
    if div_topo: emitente = div_topo.get_text(strip=True)    
    full_text = soup.get_text(" ", strip=True)
    m_cnpj = re.search(r"CNPJ[:\s]*(\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2})", full_text)
    if m_cnpj: cnpj = m_cnpj.group(1)
    data_emissao = timezone.localdate()
    m_data = re.search(r"Emiss[ãa]o\s*:?\s*(\d{2}/\d{2}/\d{4})", full_text, re.I)
    if m_data:
        try: data_emissao = dateparser.parse(m_data.group(1), dayfirst=True).date()
        except: pass
    valor_total_nota = 0.0
    desconto = 0.0
    
    div_total = soup.find("div", id="totalNota")
    if div_total:
        linhas = div_total.find_all("div", id="linhaTotal")
        for linha in linhas:
            label = linha.find("label")
            valor_span = linha.find("span", class_="totalNumb")            
            if label and valor_span:
                txt_lbl = label.get_text(strip=True).lower()
                val = _clean_float(valor_span.get_text(strip=True))                
                if "descontos" in txt_lbl:
                    desconto = val
                elif "valor a pagar" in txt_lbl:
                    valor_total_nota = val
                elif "valor total" in txt_lbl and valor_total_nota == 0:
                    valor_total_nota = val

    forma_pagamento_key = FormaPagamento.OUTROS
    parcelas = 1    
    pagamentos_encontrados = []
    
    if div_total:
        linha_forma = div_total.find("div", id="linhaForma")
        if linha_forma:
            for sibling in linha_forma.find_next_siblings("div", id="linhaTotal"):
                lbl_tx = sibling.find("label", class_="tx")
                if lbl_tx:
                    pgto_nome = lbl_tx.get_text(strip=True)
                    pagamentos_encontrados.append(pgto_nome)
    
    if pagamentos_encontrados:
        parcelas = len(pagamentos_encontrados)
        forma_pagamento_key = _predict_payment_method(pagamentos_encontrados[0])
    
    if not pagamentos_encontrados:
        txt_total = div_total.get_text(" ", strip=True) if div_total else full_text
        count_credito = len(re.findall(r"Cartão de Crédito", txt_total, re.I))
        if count_credito > 0:
            parcelas = count_credito
            forma_pagamento_key = FormaPagamento.CREDITO

    itens_estruturados = []
    table = soup.find("table", id="tabResult")
    if table:
        rows = table.find_all("tr")
        for row in rows:
            if not row.get("id", "").startswith("Item"): continue
            
            span_desc = row.find("span", class_="txtTit")
            nome = span_desc.get_text(strip=True) if span_desc else "Item"
            
            row_text = row.get_text(" ", strip=True)
            
            qtd = 1.0
            m_q = re.search(r"Qtde\.?:?\s*([\d.,]+)", row_text)
            if m_q: qtd = _clean_float(m_q.group(1))
            
            vl_unit = 0.0
            m_vu = re.search(r"Vl\.? Unit\.?:?\s*([\d.,]+)", row_text)
            if m_vu: vl_unit = _clean_float(m_vu.group(1))
            
            vl_total_item = 0.0
            span_val = row.find("span", class_="valor")
            if span_val:
                vl_total_item = _clean_float(span_val.get_text())
            else:
                vl_total_item = qtd * vl_unit
            
            itens_estruturados.append({
                "nome": nome,
                "qtd": qtd,
                "vl_unit": vl_unit,
                "vl_total": vl_total_item
            })

    return {
        "emitente": emitente,
        "cnpj": cnpj,
        "data_emissao": data_emissao,
        "valor_total": valor_total_nota,
        "desconto": desconto,
        "forma_pagamento_key": forma_pagamento_key,
        "parcelas": parcelas,
        "itens": itens_estruturados,
    }

@login_required
def importar_NFe(request):
    if request.method == "POST":
        form = UploadNFeForm(request.POST, request.FILES)
        if not form.is_valid():
            return render(request, "despesas/importar_NFe.html", {"form": form})

        img_bytes = form.cleaned_data["imagem"].read()
        url = _decode_qr_from_bytes(img_bytes)
        
        scraped = {}
        if url:
            scraped = _scrape_NFe_page(url)
        
        initial_data = {
            "emitente_nome": scraped.get("emitente"),
            "emitente_cnpj": scraped.get("cnpj"),
            "descricao": scraped.get("emitente"),
            "valor": scraped.get("valor_total"), 
            "desconto": scraped.get("desconto"),
            "parcelas_selecao": scraped.get("parcelas", 1),
            "forma_pagamento": scraped.get("forma_pagamento_key"),
            "data": scraped.get("data_emissao"),
            "categoria": _predict_category(request.user, scraped.get("emitente") or "Outros"),
            "observacoes": f"Importado via QR Code.\nLink SEFAZ: {url}" if url else "Importado via imagem."
        }

        form_desp = DespesaForm(user=request.user, initial=initial_data)
        
        initial_itens = []
        for item in scraped.get("itens", []):
            initial_itens.append({
                'nome': item['nome'],
                'quantidade': item['qtd'],
                'valor_unitario': item['vl_unit'],
                'valor_total': item['vl_total']
            })
            
        formset = ItemDespesaFormSet(queryset=ItemDespesa.objects.none(), initial=initial_itens)
        formset.extra = len(initial_itens)

        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return render(request, "despesas/despesa_form/main.html", {
                "form": form_desp, 
                "formset": formset
            })

        return render(request, "despesas/despesa_form/despesa_form.html", {"form": form_desp, "formset": formset})

    return render(request, "despesas/importar_NFe.html", {"form": UploadNFeForm()})