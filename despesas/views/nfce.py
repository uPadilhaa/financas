import re
import requests
import cv2
import numpy as np
from bs4 import BeautifulSoup
from qreader import QReader
from urllib.parse import urlparse, parse_qsl
from dateutil import parser as dateparser

from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone

from despesas.models import ItemDespesa, Categoria
from despesas.forms import DespesaForm, ItemDespesaFormSet, UploadNFCeForm
from despesas.enums.forma_pagamento_enum import FormaPagamento

qreader = QReader()

# --- Funções Auxiliares (Helpers) ---

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

def _parse_qr_nfce_url(url: str) -> dict:
    out = {"url": url, "chave": None, "valor_total": None, "data_emissao": None, "uf": None}
    host = urlparse(url).netloc.lower()
    m = re.search(r"sefaz\.([a-z]{2})\.", host)
    if m: out["uf"] = m.group(1).upper()
    q = dict(parse_qsl(urlparse(url).query))
    if "p" in q and "|" in q["p"]:
        parts = q["p"].split("|")
        if len(parts) >= 5:
            out["chave"] = parts[0]
            out["data_emissao"] = parts[3]
            out["valor_total"] = parts[4].replace(",", ".")
    else:
        out["chave"] = q.get("chNFe") or q.get("chave") or out["chave"]
        out["data_emissao"] = q.get("dhEmi") or out["data_emissao"]
        vn = q.get("vNF")
        if vn: out["valor_total"] = vn.replace(",", ".")
    if out["data_emissao"]:
        try: out["data_emissao"] = dateparser.parse(out["data_emissao"]).date()
        except: out["data_emissao"] = None
    if out["valor_total"]:
        try: out["valor_total"] = f"{float(out['valor_total']):.2f}"
        except: out["valor_total"] = None
    return out

def _scrape_nfce_page(url: str) -> dict:
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0"}
    try:
        resp = requests.get(url, headers=headers, timeout=20)
        resp.raise_for_status()
    except Exception: return {}
    
    soup = BeautifulSoup(resp.text, "html.parser")
    full_text = soup.get_text(" ", strip=True)
    
    def clean_float(s):
        if not s: return 0.0
        return float(re.sub(r"[^0-9,]", "", s).replace(",", "."))
    
    emitente = None
    cnpj = None
    div_topo = soup.find("div", class_="txtTopo")
    if div_topo: emitente = div_topo.get_text(strip=True)
    else:
        m = re.search(r"Raz[ãa]o Social[:\s]+(.+?)CNPJ", full_text, re.I)
        if m: emitente = m.group(1).strip()
    
    for div in soup.find_all("div", class_="text"):
        texto_div = div.get_text(strip=True)
        if "CNPJ" in texto_div:
            m_cnpj = re.search(r"(\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2})", texto_div)
            if m_cnpj:
                cnpj = m_cnpj.group(1)
                break
    if not cnpj:
        m_cnpj_geral = re.search(r"CNPJ[:\s]*(\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2})", full_text, re.I)
        if m_cnpj_geral: cnpj = m_cnpj_geral.group(1)
        
    data_emissao = None
    for strong in soup.find_all("strong"):
        if "Emissão" in strong.get_text():
            nxt = strong.next_sibling
            if nxt and isinstance(nxt, str):
                m = re.search(r"(\d{2}/\d{2}/\d{4})", nxt)
                if m:
                    try: data_emissao = dateparser.parse(m.group(1), dayfirst=True).date()
                    except: pass
                    break
    if not data_emissao:
        m = re.search(r"Emiss[ãa]o\s*:?\s*(\d{2}/\d{2}/\d{4})", full_text, re.I)
        if m:
            try: data_emissao = dateparser.parse(m.group(1), dayfirst=True).date()
            except: pass
            
    valor_total = 0.0
    span_total = soup.find("span", class_="totalNumb txtMax")
    if span_total: valor_total = clean_float(span_total.get_text())
    else:
        m_total = re.search(r"Valor a pagar R\$:?\s*([0-9,.]+)", full_text, re.I)
        if m_total: valor_total = clean_float(m_total.group(1))
        
    forma_pagamento = None
    lbl_pgto = soup.find("label", class_="tx")
    if lbl_pgto: forma_pagamento = lbl_pgto.get_text(strip=True)
    if not forma_pagamento:
        lbl_titulo = soup.find(lambda tag: tag.name in ["label", "div", "span"] and "Forma de pagamento" in tag.get_text())
        if lbl_titulo:
            container_atual = lbl_titulo.find_parent("div")
            if container_atual:
                proximo_container = container_atual.find_next_sibling("div")
                if proximo_container:
                    texto_bruto = proximo_container.get_text(" ", strip=True)
                    forma_pagamento = re.sub(r"\s*[0-9,.]+$", "", texto_bruto).strip()
    
    itens_estruturados = []
    table = soup.find("table", id="tabResult")
    if table:
        rows = table.find_all("tr")
        for row in rows:
            if not row.get("id", "").startswith("Item"): continue
            
            span_desc = row.find("span", class_="txtTit")
            nome = span_desc.get_text(strip=True) if span_desc else "Item"
            
            span_cod = row.find("span", class_="RCod")
            codigo = ""
            if span_cod: codigo = span_cod.get_text(strip=True).replace("(Código:", "").replace(")", "").strip()
            
            qtd = 1.0
            span_qtd = row.find("span", class_="Rqtd")
            if span_qtd:
                m_q = re.search(r"Qtde\.:\s*([0-9,.]+)", span_qtd.get_text(strip=True))
                if m_q: qtd = clean_float(m_q.group(1))
            
            un = "UN"
            span_un = row.find("span", class_="RUN")
            if span_un:
                m_u = re.search(r"UN:\s*([a-zA-Z]+)", span_un.get_text(strip=True))
                if m_u: un = m_u.group(1)
            
            vl_unit = 0.0
            span_vlu = row.find("span", class_="RvlUnit")
            if span_vlu:
                m_vu = re.search(r"Unit\.:\s*([0-9,.]+)", span_vlu.get_text(strip=True))
                if m_vu: vl_unit = clean_float(m_vu.group(1))
            
            vl_total_item = 0.0
            span_vlt = row.find("span", class_="valor")
            if span_vlt: vl_total_item = clean_float(span_vlt.get_text(strip=True))
            
            itens_estruturados.append({"nome": nome, "codigo": codigo, "qtd": qtd, "un": un, "vl_unit": vl_unit, "vl_total": vl_total_item})
            
    qtd_total_itens = len(itens_estruturados)
    return {"emitente": emitente, "cnpj": cnpj, "data_emissao": data_emissao, "valor_total": valor_total, "forma_pagamento": forma_pagamento, "itens": itens_estruturados, "qtd_total_itens": qtd_total_itens}

def _predict_category(user, emitente_nome: str) -> int | None:
    if not emitente_nome: return None
    txt = emitente_nome.lower()
    regras = {
        "Mercado": ["supermercado", "mercado", "zaffari", "carrefour", "big", "nacional", "atacado", "bistek", "center shop", "dia%", "stock center", "comercial zaffari", "maxxi"],
        "Farmácia": ["farmacia", "drogaria", "panvel", "são joão", "pague menos", "raia", "drogasil", "bifarma", "ultrafarma"],
        "Transporte": ["posto", "combustivel", "ipiranga", "shell", "petrobras", "uber", "99pop", "abastecimento"],
        "Alimentação": ["restaurante", "lancheria", "burger", "mcdonalds", "subway", "ifood", "bar", "padaria", "confeitaria", "pizzaria"],
        "Vestuário": ["lojas renner", "riachuelo", "c&a", "zara", "cea", "marisa", "pompéia", "shein"],
        "Casa": ["ferragem", "construção", "leroy", "cassol", "telhanorte"],
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
    if not text: return FormaPagamento.OUTROS
    t = text.lower()
    if "crédito" in t or "credito" in t: return FormaPagamento.CREDITO
    if "débito" in t or "debito" in t: return FormaPagamento.DEBITO
    if "pix" in t: return FormaPagamento.PIX
    if "dinheiro" in t or "espécie" in t: return FormaPagamento.DINHEIRO
    if "boleto" in t: return FormaPagamento.BOLETO
    if "alimentação" in t or "alimentacao" in t: return FormaPagamento.VALE_ALIMENTACAO
    if "refeição" in t or "refeicao" in t: return FormaPagamento.VALE_REFEICAO
    return FormaPagamento.OUTROS

# --- View Principal de Importação ---

@login_required
def importar_nfce(request):
    if request.method == "POST":
        form = UploadNFCeForm(request.POST, request.FILES)
        if not form.is_valid():
            messages.error(request, "Envie uma imagem válida.")
            return redirect("despesa_importar_nfce")

        img_bytes = form.cleaned_data["imagem"].read()
        url = _decode_qr_from_bytes(img_bytes)
        if not url:
            messages.error(request, "Não foi possível ler o QR Code.")
            return redirect("despesa_importar_nfce")
        
        base = _parse_qr_nfce_url(url)
        scraped = _scrape_nfce_page(url)
        
        emitente = scraped.get("emitente") or "Compra NFC-e"
        categoria_id = _predict_category(request.user, emitente)
        
        data_obj = scraped.get("data_emissao") or base.get("data_emissao") or timezone.localdate()
        data_str = data_obj.strftime('%Y-%m-%d') if hasattr(data_obj, 'strftime') else str(data_obj)
        
        valor = scraped.get("valor_total") or base.get("valor_total") or 0.0
        
        texto_pgto = scraped.get("forma_pagamento") or ""
        forma_pgto_key = _predict_payment_method(texto_pgto)

        lista_itens = scraped.get("itens", [])
        
        initial_itens = []
        for item in lista_itens:
            initial_itens.append({
                'nome': item['nome'],
                'codigo': item['codigo'],
                'quantidade': int(item['qtd']), 
                'valor_unitario': f"{item['vl_unit']:.2f}",
                'valor_total': f"{item['vl_total']:.2f}"
            })

        initial = {
            "emitente_nome": emitente,
            "emitente_cnpj": scraped.get("cnpj"),
            "descricao": emitente, 
            "valor": valor,
            "data": data_str,
            "forma_pagamento": forma_pgto_key,
            "qtd_total_itens": len(initial_itens),
            "categoria": categoria_id,
            "observacoes": f"Importado via QR Code.\n\nLink SEFAZ: {url}"
        }

        form_desp = DespesaForm(user=request.user, initial=initial)
        formset = ItemDespesaFormSet(queryset=ItemDespesa.objects.none(), initial=initial_itens)
        formset.extra = len(initial_itens)

        return render(request, "despesas/despesa_form.html", {
            "form": form_desp, 
            "formset": formset
        })

    return render(request, "despesas/importar_nfce.html", {"form": UploadNFCeForm()})