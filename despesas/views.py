import io
import re
import requests
from qreader import QReader
import cv2
import numpy as np
from bs4 import BeautifulSoup
from PIL import Image
from pyzbar.pyzbar import decode as qr_decode
import requests
from urllib.parse import urlparse, parse_qsl
from dateutil import parser as dateparser
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .forms import DespesaForm, CategoriaForm, UploadNFCeForm
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


qreader = QReader()

def _decode_qr_from_bytes(img_bytes: bytes) -> str | None:
    nparr = np.frombuffer(img_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    
    # O QReader faz todo o trabalho pesado de detectar e decodificar
    decoded_text = qreader.detect_and_decode(image=img)
    
    if decoded_text and decoded_text[0]:
        return decoded_text[0]
    return None


def _parse_qr_nfce_url(url: str) -> dict:
    """
    Interpreta os parâmetros do QR da NFC-e.
    Lida com formatos: ?p=... (pipe) e/ou chNFe=..., vNF=..., dhEmi=...
    """
    out = {"url": url, "chave": None, "valor_total": None, "data_emissao": None, "uf": None}
    host = urlparse(url).netloc.lower()
    # tenta inferir UF a partir do host (ex.: sefaz.rs.gov.br -> RS)
    m = re.search(r"sefaz\.([a-z]{2})\.", host)
    if m:
        out["uf"] = m.group(1).upper()

    q = dict(parse_qsl(urlparse(url).query))
    if "p" in q and "|" in q["p"]:
        parts = q["p"].split("|")
        # Especificação comum: [0]=chNFe, [3]=dhEmi, [4]=vNF
        if len(parts) >= 5:
            out["chave"] = parts[0]
            out["data_emissao"] = parts[3]
            out["valor_total"] = parts[4].replace(",", ".")
    else:
        out["chave"] = q.get("chNFe") or q.get("chave") or out["chave"]
        out["data_emissao"] = q.get("dhEmi") or out["data_emissao"]
        vn = q.get("vNF")
        if vn:
            out["valor_total"] = vn.replace(",", ".")

    # Converte data, se vier em ISO ou epoch/offset
    if out["data_emissao"]:
        try:
            out["data_emissao"] = dateparser.parse(out["data_emissao"]).date()
        except Exception:
            out["data_emissao"] = None

    # Normaliza valor_total para decimal string segura
    if out["valor_total"]:
        try:
            out["valor_total"] = f"{float(out['valor_total']):.2f}"
        except Exception:
            out["valor_total"] = None

    return out

def _scrape_nfce_page(url: str) -> dict:
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    }
    try:
        resp = requests.get(url, headers=headers, timeout=20)
        resp.raise_for_status()
    except Exception:
        return {}

    soup = BeautifulSoup(resp.text, "html.parser")
    emitente = None
    div_topo = soup.find("div", class_="txtTopo")
    if div_topo:
        emitente = div_topo.get_text(strip=True)
    else:
        m = re.search(r"Raz[ãa]o Social[:\s]+(.+?)CNPJ", soup.get_text(), re.I)
        if m: emitente = m.group(1).strip()

    data_emissao = None
    for strong in soup.find_all("strong"):
        if "Emissão" in strong.get_text():
            texto_vizinho = strong.next_sibling
            if texto_vizinho and isinstance(texto_vizinho, str):
                match = re.search(r"(\d{2}/\d{2}/\d{4})", texto_vizinho)
                if match:
                    try:
                        data_emissao = dateparser.parse(match.group(1), dayfirst=True).date()
                        break 
                    except Exception:
                        pass
    
    if not data_emissao:
        full_text = soup.get_text(" ", strip=True)
        m = re.search(r"Emiss[ãa]o\s*:?\s*(\d{2}/\d{2}/\d{4})", full_text, re.I)
        if m:
            try:
                data_emissao = dateparser.parse(m.group(1), dayfirst=True).date()
            except Exception:
                pass

    def clean_float(s: str) -> str | None:
        if not s: return None
        clean = re.sub(r"[^0-9,]", "", s).replace(",", ".")
        try: return f"{float(clean):.2f}"
        except ValueError: return None

    total = None
    span_total = soup.find("span", class_="totalNumb txtMax") 
    if span_total:
        total = clean_float(span_total.get_text())
    
    if not total:
        m_total = re.search(r"Valor a pagar R\$:?\s*([0-9,.]+)", soup.get_text(), re.I)
        if m_total: total = clean_float(m_total.group(1))

    item_lines = []
    table = soup.find("table", id="tabResult")
    if table:
        for row in table.find_all("tr"):
            if not row.get("id", "").startswith("Item"): continue

            span_desc = row.find("span", class_="txtTit")
            desc = span_desc.get_text(strip=True) if span_desc else "Item"
            span_qtd = row.find("span", class_="Rqtd")
            qtd = "1"
            if span_qtd:
                m_qtd = re.search(r"Qtde\.:\s*([0-9,.]+)", span_qtd.get_text(), re.I)
                if m_qtd: qtd = m_qtd.group(1)

            span_vlu = row.find("span", class_="RvlUnit")
            vl_unit = ""
            if span_vlu:
                m_vlu = re.search(r"Unit\.:\s*([0-9,.]+)", span_vlu.get_text(), re.I)
                if m_vlu: vl_unit = m_vlu.group(1)

            span_tot = row.find("span", class_="valor")
            vl_tot = span_tot.get_text(strip=True) if span_tot else ""

            item_lines.append(f"{desc} (Qtd: {qtd} x R$ {vl_unit}) = R$ {vl_tot}")

    return {
        "emitente": emitente,
        "valor_total": total,
        "data_emissao": data_emissao,
        "itens_texto": "\n".join(item_lines) if item_lines else None,
    }


@login_required
def importar_nfce(request):
    if request.method == "POST":
        form = UploadNFCeForm(request.POST, request.FILES)
        if not form.is_valid():
            messages.error(request, "Envie uma imagem válida do QR-Code.")
            return redirect("despesa_importar_nfce")

        img_bytes = form.cleaned_data["imagem"].read()
        url = _decode_qr_from_bytes(img_bytes)

        if not url:
            messages.error(request, "Não consegui ler nenhum QR-Code. Tente uma foto mais nítida.")
            return redirect("despesa_importar_nfce")

        if "sefaz" not in url.lower() and "http" not in url.lower():
             messages.warning(request, "O código lido não parece ser uma URL válida de nota fiscal.")
        
        base = _parse_qr_nfce_url(url)
        scraped = _scrape_nfce_page(url)
        print(f"{scraped.get("data_emissao")}")
        valor = scraped.get("valor_total") or base.get("valor_total")
        data_obj = scraped.get("data_emissao") or base.get("data_emissao") or timezone.localdate()
        if hasattr(data_obj, 'strftime'):
            data = data_obj.strftime('%Y-%m-%d')
        else:
            data = str(data_obj)

        emitente = scraped.get("emitente") or "Compra NFC-e"
        itens_texto = scraped.get("itens_texto")
        obs = []
        if itens_texto:
            obs.append(itens_texto)
        
        obs.append("-" * 20)
        obs.append(f"Link: {base['url']}")
        
        initial = {
            "descricao": emitente,
            "valor": valor or "0.00",
            "data": data,  
            "observacoes": "\n".join(obs),
        }

        if not Categoria.objects.filter(user=request.user).exists():
            Categoria.objects.create(user=request.user, nome="Outros")

        form_desp = DespesaForm(user=request.user, initial=initial)
        messages.info(request, "Dados importados! Confira e salve.")
        return render(request, "despesas/despesa_form.html", {"form": form_desp})

    return render(request, "despesas/importar_nfce.html", {"form": UploadNFCeForm()})