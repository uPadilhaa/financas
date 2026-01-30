import re
import requests
import logging
from bs4 import BeautifulSoup
from dateutil import parser as dateparser
from django.utils import timezone
from io import BytesIO
from urllib.parse import urlparse
import socket
import ipaddress


from despesas.models import Categoria
from despesas.enums.forma_pagamento_enum import FormaPagamento

logger = logging.getLogger(__name__)

_INSTANCIA_QREADER = None

class NFeService:
    def __init__(self):
        pass

    @property
    def qreader(self):
        """
        Retorna a instância do leitor QReader (Singleton).

        Inicializa o modelo QReader na primeira chamada para otimizar o uso de recursos.
        Utiliza o modelo 'nano' para compatibilidade com ambientes de memória limitada.

        Returns:
             QReader: Instância do objeto QReader inicializada ou None em caso de erro.
        """
        global _INSTANCIA_QREADER
        if _INSTANCIA_QREADER is None:
            try:
                from qreader import QReader
                _INSTANCIA_QREADER = QReader(model_size='n') 
            except ImportError:
                 logger.error("Biblioteca QReader não instalada.")
                 return None
            except Exception as e:
                logger.critical(f"Falha crítica ao carregar QReader: {e}")
                return None
        return _INSTANCIA_QREADER

    def validar_url(self, url: str) -> bool:
        """
        Valida se a URL é segura para requisição e previne ataques SSRF.

        Verifica se o esquema é HTTP/HTTPS e resolve o DNS do hostname para garantir
        que o IP de destino não pertença a redes privadas, locais ou de loopback.

        Args:
            url (str): A URL a ser verificada.

        Returns:
            bool: True se a URL for pública e segura, False caso contrário.
        """
        try:
            parsed = urlparse(url)
            if parsed.scheme not in ('http', 'https'):
                return False
            
            hostname = parsed.hostname
            if not hostname:
                return False

            try:
                ip = socket.gethostbyname(hostname)
            except socket.gaierror:
                return False

            ip_obj = ipaddress.ip_address(ip)

            if ip_obj.is_private or ip_obj.is_loopback or ip_obj.is_link_local:
                logger.warning(f"SSRF Attempt blocked for URL: {url} (IP: {ip})")
                return False
            
            return True
        except Exception as e:
            logger.error(f"URL Validation error: {e}")
            return False

    def decodificar_qr_code(self, img_bytes: bytes) -> str | None:
        """
        Decodifica o conteúdo de um QR Code presente em uma imagem.

        Processa os bytes da imagem utilizando OpenCV para pré-processamento e
        QReader para detecção e decodificação. Realiza redimensionamento e
        tratamento de limiar para melhorar a taxa de sucesso.

        Args:
            img_bytes (bytes): Conteúdo binário da imagem a ser processada.

        Returns:
            str | None: String contendo o dado decodificado ou None se falhar.
        """
        try:
            if self.qreader is None:
                logger.warning("QReader indisponível. Abortando decodificação.")
                return None

            import numpy as np
            import cv2
            nparr = np.frombuffer(img_bytes, np.uint8)
            imagem = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            if imagem is None: return None

            altura, largura = imagem.shape[:2]
            largura_maxima = 1500
            if largura > largura_maxima:
                escala = largura_maxima / largura
                nova_largura = int(largura * escala)
                nova_altura = int(altura * escala)
                imagem = cv2.resize(imagem, (nova_largura, nova_altura), interpolation=cv2.INTER_AREA)

            decodificado = self.qreader.detect_and_decode(image=imagem)
            if decodificado and decodificado[0]: return decodificado[0]    
            
            cinza = cv2.cvtColor(imagem, cv2.COLOR_BGR2GRAY)
            separacao = cv2.adaptiveThreshold(cinza, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 21, 11)
            decodificado = self.qreader.detect_and_decode(image=separacao)
            if decodificado and decodificado[0]: return decodificado[0]    
            return None
        except Exception as e:
            logger.error(f"Error decoding QR: {e}")
            return None

    def normalizar_float(self, s):
        """
        Converte uma string monetária brasileira ou americana para float.

        Lida com formatos como '1.234,56' e '1,234.56', removendo símbolos não numéricos
        e ajustando os separadores decimais.

        Args:
            s (str | float): O valor a ser convertido.

        Returns:
            float: O valor numérico convertido, ou 0.0 se a conversão falhar.
        """
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

    def limpar_descricao(self, desc: str) -> str:
        """
        Remove prefixos e sufixos irrelevantes da descrição do produto.

        Limpa termos técnicos como 'PRODUTO', 'CÓDIGO', 'QTD' que muitas vezes
        poluem a descrição extraída da nota fiscal.

        Args:
            desc (str): A descrição original do produto.

        Returns:
            str: A descrição limpa e formatada.
        """
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

    def validar_cnpj(self, cnpj: str) -> bool:
        """
        Valida a veracidade de um número de CNPJ aplicando o algoritmo de dígitos verificadores.

        Remove caracteres não numéricos antes da validação.

        Args:
            cnpj (str): O CNPJ a ser validado.

        Returns:
            bool: True se o CNPJ for matematicamente válido, False caso contrário.
        """
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

    def identificar_categoria(self, user, emitente_nome: str) -> int | None:
        """
        Identifica a categoria provável da despesa baseada no nome do emitente.

        Analisa o nome do estabelecimento comparando com uma lista de palavras-chave
        pré-definidas para sugerir uma categoria existente no perfil do usuário.

        Args:
            user (Usuario): O usuário para o qual a categoria será buscada.
            emitente_nome (str): Nome do estabelecimento ou emitente da nota.

        Returns:
            int | None: ID da categoria identificada ou None se não houver correspondência.
        """
        if not emitente_nome: return None
        txt = emitente_nome.lower()
        regras = {
            "Mercado": ["supermercado", "mercado", "zaffari", "carrefour", "big", "nacional", "atacado", "bistek", "center shop", "dia%", "stock center", "comercial zaffari", "maxxi", "kan", "macromix", "assai", "makro", "atacadao", "extra", "pao de acucar", "mambo", "condor", "angeloni", "fort atacadista", "savegnago", "bahamas", "guanabara", "zona sul", "mundial", "sonda", "festval", "gimba", "tenda", "todo dia"],
            "Farmácia": ["farmacia", "drogaria", "panvel", "são joão", "pague menos", "raia", "drogasil", "bifarma", "ultrafarma", "extrafarma", "farmacia popular", "pacheco", "drogasmil", "nissei", "farmasil", "paguemenos", "droga raia", "poupa tempo", "venancio"],
            "Transporte": ["posto", "combustivel", "ipiranga", "shell", "petrobras", "uber", "99pop", "abastecimento", "ale", "br distribuidora", "esso", "texaco", "raizen", "99", "cabify", "estacionamento", "pedagio", "sem parar", "veloe", "conectcar", "pneu", "borracharia", "mecanica"],
            "Alimentação": ["restaurante", "lancheria", "burger", "mcdonalds", "subway", "ifood", "bar", "padaria", "confeitaria", "pizzaria", "bobs", "burger king", "habib's", "giraffa", "spoleto", "pizza hut", "dominos", "outback", "china in box", "ragazzo", "vivenda", "madero", "giraffas", "rappi", "ze delivery", "lanchonete", "delivery", "sorveteria", "açai", "acai"],
            "Vestuário": ["lojas renner", "riachuelo", "c&a", "zara", "cea", "marisa", "pompéia", "shein", "hering", "farm", "shoulder", "forum", "polo wear", "nike", "adidas", "centauro", "decathlon", "pernambucanas", "leader", "magazine luiza roupa", "netshoes", "mercado livre moda", "track&field", "reserva"],
            "Casa": ["ferragem", "construção", "leroy", "cassol", "telhanorte", "eletrica", "comercial dalacorte", "leroy merlin", "dicico", "c&c", "obramax", "constrular", "sodimac", "tok stok", "etna", "camicado", "utilplast", "loja de moveis", "movida"],
            "Eletrônicos": ["kabum", "pichau", "terabyte", "kalunga", "dell", "samsung", "apple", "magazine luiza", "casas bahia", "ponto frio", "fast shop", "americanas", "extra eletrônicos", "ricardo eletro", "carrefour eletrônicos", "mercado livre", "amazon", "submarino", "shoptime", "multilaser", "positivo", "lenovo", "lg", "motorola", "xiaomi"],
            "Saúde": ["hospital", "clinica", "laboratorio", "consulta", "medico", "dentista", "odonto", "unimed", "hapvida", "amil", "sulamerica", "bradesco saude", "notredame", "intermedica", "lavoisier", "fleury", "delboni", "hermes pardini", "einstein", "sirio libanes"],
            "Educação": ["escola", "faculdade", "curso", "universidade", "kumon", "wizard", "ccaa", "fisk", "cultura inglesa", "cel lep", "cursinho", "etec", "senac", "senai", "sesi", "udemy", "hotmart", "eduzz"],
            "Lazer": ["cinema", "cinemark", "cinepolis", "uci", "kinoplex", "teatro", "show", "ingresso.com", "eventim", "sympla", "parque", "clube", "boliche", "brinquedoteca", "netflix", "spotify", "amazon prime", "disney+", "hbo", "globoplay"],
            "Pet Shop": ["pet shop", "petz", "cobasi", "petlove", "petco", "agropecuaria", "veterinaria", "clinica veterinaria", "banho e tosa", "petiscos", "racao"],
            "Serviços": ["salao", "barbearia", "estetica", "academia", "smartfit", "bluefit", "bio ritmo", "bodytech", "lavanderia", "lavagem", "costureira", "assistencia tecnica", "conserto", "reforma"],
            "Seguros": ["seguro", "porto seguro", "liberty", "azul seguros", "allianz", "itau seguros", "bradesco seguros", "mapfre", "tokio marine", "hdi seguros"]
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

    def identificar_forma_pagamento(self, text: str) -> str | None:
        """
        Identifica a forma de pagamento a partir de um texto descritivo.

        Analisa strings comuns em notas fiscais para determinar se o pagamento
        foi realizado em Crédito, Débito, Pix ou Dinheiro.

        Args:
            text (str): Texto descrevendo a forma de pagamento.

        Returns:
            str | None: Constante da classe FormaPagamento ou None.
        """
        t = text.lower()
        if "crédito" in t or "credito" in t: return FormaPagamento.CREDITO
        if "débito" in t or "debito" in t: return FormaPagamento.DEBITO
        if "pix" in t: return FormaPagamento.PIX
        if "dinheiro" in t: return FormaPagamento.DINHEIRO
        return None

    def extrair_itens_pdf(self, pdf_file) -> list[dict]:
        """
        Extrai a lista de itens e produtos de um arquivo PDF (DANFE).

        Utiliza a biblioteca pdfplumber para ler tabelas e textos do PDF,
        identificando colunas relevantes como descrição, quantidade, valor unitário
        e valor total.

        Args:
            pdf_file (file): Objeto de arquivo PDF aberto para leitura.

        Returns:
            list[dict]: Lista de dicionários representando os itens extraídos.
        """        
        pdf_bytes = pdf_file.read()
        itens: list[dict] = []

        try:
            import pdfplumber
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
                                    if "DESC" in v_up or "DESCR" in v_up: col_map['desc'] = idx
                                    elif "QTD" in v_up: col_map['qtd'] = idx
                                    elif "UNIT" in v_up: col_map['unit'] = idx
                                    elif "TOTAL" in v_up: col_map['total'] = idx
                                break

                        if header_idx != -1 and 'total' in col_map:
                            for row in table[header_idx + 1:]:
                                try:
                                    if not row[col_map.get('total', 0)]: continue
                                    desc_raw = row[col_map['desc']] if 'desc' in col_map else "Item"
                                    
                                    if len(str(desc_raw)) > 200: continue
                                    
                                    desc = self.limpar_descricao(str(desc_raw).replace('\n', ' '))
                                    total = self.normalizar_float(row[col_map['total']])
                                    if total <= 0: continue
                                    qtd = self.normalizar_float(row[col_map['qtd']]) if 'qtd' in col_map else 1.0
                                    unit = self.normalizar_float(row[col_map['unit']]) if 'unit' in col_map else total
                                    if qtd == 0: qtd = 1.0
                                    if unit == 0: unit = total / qtd
                                    itens.append({"nome": desc, "qtd": qtd, "vl_unit": unit, "vl_total": total, "unidade": "UN"})
                                except Exception: pass
            
            if not itens:
                full_text = ""
                import pdfplumber
                with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
                    for page in pdf.pages: full_text += "\n" + (page.extract_text() or "")
                
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
                            final_desc = self.limpar_descricao(" ".join(desc_parts))
                            if len(final_desc) < 250:
                                pending_item["nome"] = final_desc
                        buffer_desc = []
                        tail = line[ncm_match.end():]
                        tokens = tail.split()
                        numeric_tokens = []
                        for t in tokens:
                            if re.fullmatch(r"(UN|UNID\.?|PC|PÇ|PÇS|KG|G|UNIDADE)", t.upper()):
                                numeric_tokens.append(("UNIT_MARK", t))
                                continue
                            v = self.normalizar_float(t)
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
                            if len(line) < 150:
                                buffer_desc.append(line)

        except Exception as e:
            logger.error(f"PDF Parse Error: {e}")

        return itens

    def processar_danfe_pdf(self, uploaded_file) -> dict:
        """
        Processa um arquivo PDF de DANFE para extrair informações da nota fiscal.

        Coordena a extração de itens e metadados (emitente, CNPJ, data, totais)
        analisando tanto a estrutura tabular quanto o texto livre do documento.

        Args:
            uploaded_file (file): Arquivo PDF da nota fiscal enviado pelo usuário.

        Returns:
            dict: Dicionário contendo os dados estruturados da nota fiscal.
        """
        pdf_bytes = uploaded_file.read()    
        uploaded_file.seek(0)
        itens_estruturados = self.extrair_itens_pdf(uploaded_file)    
        uploaded_file.seek(0)
        full_text = ""
        try:
            import pdfplumber
            with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
                for page in pdf.pages: full_text += "\n" + (page.extract_text() or "")
        except: pass    
        
        emitente = "Consumidor"
        m_emit = re.search(r"RECEBEMOS\s+DE\s+(.*?)\s+(OS\s+PRODUTOS|AS\s+MERCADORIAS|CONSTANTES)", full_text, re.S | re.I)
        if m_emit: 
            candidate = m_emit.group(1).strip().replace("\n", " ")
            if len(candidate) > 100:
                candidate = candidate.split('\n')[0]            
            if len(candidate) < 100:
                emitente = candidate
        
        if emitente == "Consumidor":
             for l in full_text.split('\n')[:25]:
                if len(l) > 3 and len(l) < 100 and any(x in l.upper() for x in ["LTDA", "S.A.", "COMERCIO", "KABUM", "WEBSHOP", "EIRELI", "ME", "EPP"]):
                    clean_l = re.sub(r"^(IDENTIFICAÇÃO\s+DO\s+EMITENTE|DANFE)\s*", "", l, flags=re.I).strip()
                    if clean_l:
                        emitente = clean_l
                        break
        cnpj = None
        digits = re.sub(r'\D', '', full_text)
        keys = re.findall(r'(\d{44})', digits)
        for key in keys:
            sub = key[6:20]
            if self.validar_cnpj(sub):
                cnpj = f"{sub[:2]}.{sub[2:5]}.{sub[5:8]}/{sub[8:12]}-{sub[12:]}"; break
        if not cnpj:
            ms = re.findall(r"(\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2})", full_text[:3000])
            for m in ms:
                if self.validar_cnpj(m): cnpj = m; break
        
        data_emissao = timezone.localdate()
        m_data = re.search(r"EMISS[ÃA]O.*?\s+(\d{2}/\d{2}/\d{4})", full_text, re.I | re.S)
        if m_data:
            try: data_emissao = dateparser.parse(m_data.group(1), dayfirst=True).date()
            except: pass

        valor_total_nota = 0.0
        m_val = re.search(r"VALOR\s+TOTAL\s+DA\s+NOTA(.*)", full_text, re.I | re.S)
        if m_val:
            nums = re.findall(r"([\d\.]+,\d{2})", m_val.group(1))
            if nums: valor_total_nota = self.normalizar_float(nums[-1])
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

    def extrair_dados_url(self, url: str) -> dict:
        """
        Extrai dados de uma Nota Fiscal a partir da URL (Web Scraping).

        Realiza uma requisição HTTP segura para a URL fornecida e processa o HTML
        retornado para capturar dados da nota, emitente e itens.

        Args:
            url (str): URL pública da nota fiscal (QRCode).

        Returns:
            dict: Dicionário com as informações extraídas da página.
        """
        if not self.validar_url(url):
             logger.warning(f"Invalid URL rejected: {url}")
             return {}

        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0"}
        try:
            resp = requests.get(url, headers=headers, timeout=20)
            resp.raise_for_status()
        except Exception as e:
            logger.error(f"Request failed: {e}")
            return {}
            
        soup = BeautifulSoup(resp.text, "html.parser")    
        
        emitente = "Consumidor"
        cnpj = None
        div_topo = soup.find("div", class_="txtTopo")
        if div_topo: emitente = div_topo.get_text(strip=True)    
        texto = soup.get_text(" ", strip=True)    
        m_cnpj = re.search(r"CNPJ[:\s]*(\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2})", texto)
        if m_cnpj and self.validar_cnpj(m_cnpj.group(1)):
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
                    val = self.normalizar_float(valor_span.get_text(strip=True))                
                    if "descontos" in txt_lbl: desconto = val
                    elif "valor a pagar" in txt_lbl: valor_total_nota = val
                    elif "valor total" in txt_lbl and valor_total_nota == 0: valor_total_nota = val

        forma_pagamento_key = ''
        parcelas = 1    
        pagamentos_encontrados = []    
        if div_total:
            linha_forma = div_total.find("div", id="linhaForma")
            if linha_forma:
                for sibling in linha_forma.find_next_siblings("div", id="linhaTotal"):
                    lbl_tx = sibling.find("label", class_="tx")
                    if lbl_tx: pagamentos_encontrados.append(lbl_tx.get_text(strip=True))
        
        pagamentos_validos = []
        for pgto in pagamentos_encontrados:
            if re.search(r"troco", pgto, re.I): continue
            if not pgto.strip(): continue
            pagamentos_validos.append(pgto)

        if pagamentos_validos:
            parcelas = len(pagamentos_validos)
            forma_pagamento_key = self.identificar_forma_pagamento(pagamentos_validos[0])
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
                    qtd = self.normalizar_float(txt_qtd)
                
                span_un = row.find("span", class_="RUN")
                unidade = "UN"
                if span_un:
                    txt_un = span_un.get_text(strip=True).upper().replace("UN:", "").strip()
                    if txt_un: unidade = txt_un
                
                span_vunit = row.find("span", class_="RvlUnit")
                vl_unit = 0.0
                if span_vunit:
                    txt_vu = span_vunit.get_text(strip=True).replace("Vl. Unit.:", "").strip()
                    vl_unit = self.normalizar_float(txt_vu)            
                span_val = row.find("span", class_="valor")
                vl_total_item = 0.0
                if span_val:
                    vl_total_item = self.normalizar_float(span_val.get_text(strip=True))
                else:
                    row_text = row.get_text(" ", strip=True)
                    m_vt = re.search(r"Vl\.?\s*Total[:\s]*R?\$?\s*([\d.,]+)", row_text, re.I)
                    if m_vt: vl_total_item = self.normalizar_float(m_vt.group(1))
                    else: vl_total_item = qtd * vl_unit
                
                itens_estruturados.append({"nome": nome, "qtd": qtd, "unidade": unidade, "vl_unit": vl_unit, "vl_total": vl_total_item})

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
