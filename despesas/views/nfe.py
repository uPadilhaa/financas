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
from django import forms
import pdfplumber
from io import BytesIO
from despesas.models import ItemDespesa, Categoria, Despesa
from despesas.forms import DespesaForm, UploadNFeForm, ItemDespesaForm
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
        if s.rfind(',') > s.rfind('.'):
             s = s.replace('.', '').replace(',', '.')
        else:
             s = s.replace(',', '')
    elif ',' in s:
        s = s.replace(',', '.')    
    try:
        return float(s)
    except ValueError:
        return 0.0
    
def _clean_description(desc: str) -> str:
    garbage = [
        "PRODUTO", "DESCRIÇÃO", "CODIGO", "CÓDIGO", "SERVIÇO", "ICMS", "IPI", 
        "ALIQ", "VALOR", "UNIT", "TOTAL", "BC", "UNID", "QTD", "NCM", "CST", "CFOP"
    ]
    words = desc.split()
    while words and any(g in words[0].upper().replace('.', '') for g in garbage):
        words.pop(0)
    while words and any(g in words[-1].upper().replace('.', '') for g in garbage):
        words.pop()    
    return " ".join(words).strip() or "Item"

def _is_valid_cnpj(cnpj: str) -> bool:
    cnpj = re.sub(r'\D', '', str(cnpj))
    if len(cnpj) != 14 or len(set(cnpj)) == 1:
        return False

    weights1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    sum1 = sum(int(cnpj[i]) * weights1[i] for i in range(12))
    check1 = 11 - (sum1 % 11)
    if check1 >= 10: check1 = 0
    if int(cnpj[12]) != check1:
        return False

    weights2 = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    sum2 = sum(int(cnpj[i]) * weights2[i] for i in range(13))
    check2 = 11 - (sum2 % 11)
    if check2 >= 10: check2 = 0
    if int(cnpj[13]) != check2:
        return False
    return True

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
        "Eletrônicos": ["kabum", "pichau", "terabyte", "kalunga", "dell", "samsung", "apple"]
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

def _predict_payment_method(text: str) -> str | None:
    t = text.lower()
    if "crédito" in t or "credito" in t: return FormaPagamento.CREDITO
    if "débito" in t or "debito" in t: return FormaPagamento.DEBITO
    if "pix" in t: return FormaPagamento.PIX
    if "dinheiro" in t: return FormaPagamento.DINHEIRO
    return None
    
def _extract_items_hybrid(pdf_file) -> list[dict]:
    pdf_bytes = pdf_file.read()
    itens: list[dict] = []

    try:
        with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
            for page in pdf.pages:
                tables = page.extract_tables()
                for table in tables:
                    header_idx = -1
                    col_map: dict[str, int] = {}

                    for i, row in enumerate(table):
                        row_str = [str(c).upper() for c in row if c]
                        has_qtd_or_unit = any("UNIT" in c or "QTD" in c for c in row_str)
                        has_desc = any("DESC" in c or "DESCR" in c for c in row_str)
                        if has_qtd_or_unit and has_desc:
                            header_idx = i
                            for idx, val in enumerate(row):
                                v_up = str(val).upper() if val else ""
                                if "DESC" in v_up or "DESCR" in v_up:
                                    col_map['desc'] = idx
                                elif "QTD" in v_up:
                                    col_map['qtd'] = idx
                                elif "UNIT" in v_up:
                                    col_map['unit'] = idx
                                elif "TOTAL" in v_up:
                                    col_map['total'] = idx
                            break

                    if header_idx != -1 and 'total' in col_map:
                        for row in table[header_idx + 1:]:
                            try:
                                if not row[col_map.get('total', 0)]:
                                    continue

                                desc_raw = row[col_map['desc']] if 'desc' in col_map else "Item"
                                desc = _clean_description(str(desc_raw).replace('\n', ' '))

                                total = _clean_float(row[col_map['total']])
                                if total <= 0:
                                    continue

                                qtd = _clean_float(row[col_map['qtd']]) if 'qtd' in col_map else 1.0
                                unit = _clean_float(row[col_map['unit']]) if 'unit' in col_map else total

                                if qtd == 0: qtd = 1.0
                                if unit == 0: unit = total / qtd

                                itens.append({
                                    "nome": desc,
                                    "qtd": qtd,
                                    "vl_unit": unit,
                                    "vl_total": total,
                                    "unidade": "UN" # Default PDF
                                })
                            except Exception:
                                pass
            if not itens:
                full_text = ""
                for page in pdf.pages:
                    full_text += "\n" + (page.extract_text() or "")

                m_start = re.search(r"DADOS DO[S]? PRODUTO[S]?", full_text, re.I)
                if not m_start:
                    return itens
                search_area = full_text[m_start.end():]
                m_end = re.search(
                    r"(CÁLCULO DO ISSQN|DADOS ADICIONAIS|TRANSPORTADOR)",
                    search_area,
                    re.I
                )

                start = m_start.start()
                end = m_start.end() + m_end.start() if m_end else len(full_text)

                lines = [
                    l.strip()
                    for l in full_text[start:end].splitlines()
                    if l.strip()
                ]

                buffer_desc: list[str] = []
                pending_item: dict = {}
                waiting_values = False

                for line in lines:
                    if re.search(r"DADOS DO\S* PRODUTO", line, re.I):
                        continue
                    if re.match(r"^(CÓDIGO|PRODUTO|NCM/SH|NCM|SH|CST|CFOP|UNID|QTD|VLR|VALOR|BC|ICMS|IPI|ALIQ)", line, re.I,):
                        continue
                    ncm_match = re.search(r"\b\d{8}\b", line.replace(".", ""))
                    if ncm_match:
                        prefix = line[:ncm_match.start()].strip()
                        desc_parts = []
                        if buffer_desc:
                            desc_parts.append(" ".join(buffer_desc))
                        if prefix:
                            desc_parts.append(prefix)
                        pending_item = {}
                        if desc_parts:
                            pending_item["nome"] = _clean_description(" ".join(desc_parts))
                        buffer_desc = []
                        tail = line[ncm_match.end():]
                        tokens = tail.split()
                        numeric_tokens: list[tuple[str, float | str]] = []
                        for t in tokens:
                            if re.fullmatch(r"(UN|UNID\.?|PC|PÇ|PÇS|KG|G|UNIDADE)", t.upper()):
                                numeric_tokens.append(("UNIT_MARK", t))
                                continue
                            v = _clean_float(t)
                            if v > 0:
                                numeric_tokens.append(("NUM", v))

                        qtd = unit = total = None
                        try:
                            idx_unit = next(
                                i for i, (kind, _) in enumerate(numeric_tokens)
                                if kind == "UNIT_MARK"
                            )
                            nums_after = [
                                v for kind, v in numeric_tokens[idx_unit + 1:]
                                if kind == "NUM"
                            ]
                            if nums_after:
                                qtd = nums_after[0]
                                if len(nums_after) >= 2:
                                    unit = nums_after[1]
                                if len(nums_after) >= 3:
                                    total = nums_after[2]
                        except StopIteration:
                            nums_all = [v for kind, v in numeric_tokens if kind == "NUM"]
                            if nums_all:
                                total = nums_all[-1]
                                if len(nums_all) >= 2:
                                    unit = nums_all[-2]
                                if len(nums_all) >= 3:
                                    qtd = nums_all[-3]
                        if total is None and unit is not None and qtd is not None:
                            total = unit * qtd
                        if total is not None and qtd is not None and unit is None and qtd:
                            unit = total / qtd
                        if qtd is None and total is not None and unit is not None and unit:
                            qtd = total / unit
                        if pending_item.get("nome") and total is not None:
                            itens.append({
                                "nome": pending_item["nome"],
                                "qtd": float(qtd or 1.0),
                                "vl_unit": float(unit or 0.0),
                                "vl_total": float(total),
                                "unidade": "UN"
                            })
                            pending_item = {}
                            waiting_values = False
                        else:
                            waiting_values = True
                    else:
                        if waiting_values:
                            continue
                        if not re.match(r"^[\d\.,/\s-]+$", line):
                            buffer_desc.append(line)
    except Exception as e:
        print(f"Erro Parse PDF: {e}")

    return itens

def _parse_nfe_danfe_pdf(uploaded_file) -> dict:
    pdf_bytes = uploaded_file.read()    
    uploaded_file.seek(0)
    itens_estruturados = _extract_items_hybrid(uploaded_file)    
    uploaded_file.seek(0)
    full_text = ""
    try:
        with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
            for page in pdf.pages: full_text += "\n" + (page.extract_text() or "")
    except: pass    
    emitente = "Consumidor"
    m_emit = re.search(r"RECEBEMOS\s+DE\s+(.*?)\s+OS\s+PRODUTOS", full_text, re.S | re.I)
    if m_emit: emitente = m_emit.group(1).strip().replace("\n", " ")
    else:
        for l in full_text.split('\n')[:15]:
            if len(l) > 3 and any(x in l.upper() for x in ["LTDA", "S.A.", "COMERCIO", "KABUM", "WEBSHOP"]):
                emitente = l.strip(); break    
    cnpj = None
    digits = re.sub(r'\D', '', full_text)
    keys = re.findall(r'(\d{44})', digits)
    for key in keys:
        sub = key[6:20]
        if _is_valid_cnpj(sub):
            cnpj = f"{sub[:2]}.{sub[2:5]}.{sub[5:8]}/{sub[8:12]}-{sub[12:]}"; break
    if not cnpj:
        ms = re.findall(r"(\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2})", full_text[:3000])
        for m in ms:
            if _is_valid_cnpj(m): cnpj = m; break

    data_emissao = timezone.localdate()
    m_data = re.search(r"EMISS[ÃA]O.*?\s+(\d{2}/\d{2}/\d{4})", full_text, re.I | re.S)
    if m_data:
        try: data_emissao = dateparser.parse(m_data.group(1), dayfirst=True).date()
        except: pass

    valor_total_nota = 0.0
    m_val = re.search(r"VALOR\s+TOTAL\s+DA\s+NOTA(.*)", full_text, re.I | re.S)
    if m_val:
        nums = re.findall(r"([\d\.]+,\d{2})", m_val.group(1))
        if nums:
            valor_total_nota = _clean_float(nums[-1])  
    elif itens_estruturados:
        valor_total_nota = sum(i['vl_total'] for i in itens_estruturados)
    return {
        "emitente": emitente,
        "cnpj": cnpj,
        "data_emissao": data_emissao,
        "valor_total": valor_total_nota,
        "desconto": 0.0,
        "forma_pagamento_key": '', 
        "parcelas": 1,
        "itens": itens_estruturados,
    }

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
    texto = soup.get_text(" ", strip=True)    
    m_cnpj = re.search(r"CNPJ[:\s]*(\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2})", texto)
    if m_cnpj and _is_valid_cnpj(m_cnpj.group(1)):
        cnpj = m_cnpj.group(1)

    data_emissao = timezone.localdate()
    mensagem_data = re.search(r"Emiss[ãa]o\s*:?\s*(\d{2}/\d{2}/\d{4})", texto, re.I)
    if mensagem_data:
        try: data_emissao = dateparser.parse(mensagem_data.group(1), dayfirst=True).date()
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

    forma_pagamento_key = ''
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
    
    pagamentos_validos = []
    for pgto in pagamentos_encontrados:
        if re.search(r"troco", pgto, re.I): continue
        if not pgto.strip(): continue
        pagamentos_validos.append(pgto)

    if pagamentos_validos:
        parcelas = len(pagamentos_validos)
        forma_pagamento_key = _predict_payment_method(pagamentos_validos[0])
    else:
        txt_total = div_total.get_text(" ", strip=True) if div_total else texto
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
            span_qtd = row.find("span", class_="Rqtd")
            qtd = 1.0
            if span_qtd:
                txt_qtd = span_qtd.get_text(strip=True).replace("Qtde.:", "").strip()
                qtd = _clean_float(txt_qtd)
            
            span_un = row.find("span", class_="RUN")
            unidade = "UN"
            if span_un:
                txt_un = span_un.get_text(strip=True).upper().replace("UN:", "").strip()
                if txt_un:
                    unidade = txt_un
            
            span_vunit = row.find("span", class_="RvlUnit")
            vl_unit = 0.0
            if span_vunit:
                txt_vu = span_vunit.get_text(strip=True).replace("Vl. Unit.:", "").strip()
                vl_unit = _clean_float(txt_vu)            
            span_val = row.find("span", class_="valor")
            vl_total_item = 0.0
            if span_val:
                vl_total_item = _clean_float(span_val.get_text(strip=True))
            else:
                row_text = row.get_text(" ", strip=True)
                m_vt = re.search(r"Vl\.?\s*Total[:\s]*R?\$?\s*([\d.,]+)", row_text, re.I)
                if m_vt: vl_total_item = _clean_float(m_vt.group(1))
                else: vl_total_item = qtd * vl_unit
            
            itens_estruturados.append({
                "nome": nome,
                "qtd": qtd,
                "unidade": unidade,
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

        arquivo = form.cleaned_data["imagem"]
        content_type = (arquivo.content_type or "").lower()
        filename = (arquivo.name or "").lower()        
        scraped = {}
        url = None
        is_pdf = content_type == 'application/pdf' or filename.endswith('.pdf')
        
        if is_pdf:
            scraped = _parse_nfe_danfe_pdf(arquivo)
        else:
            img_bytes = arquivo.read()
            url = _decode_qr_from_bytes(img_bytes)
            if url:
                scraped = _scrape_NFe_page(url)
        
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
            "categoria": _predict_category(request.user, emitente or ""),
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