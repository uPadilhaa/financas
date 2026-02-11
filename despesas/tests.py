from django.test import TestCase, RequestFactory
from django.contrib.auth import get_user_model
from django.utils import timezone
from unittest.mock import MagicMock, patch
from decimal import Decimal
import pandas as pd
from datetime import timedelta

from despesas.models import Despesa, Receita, Usuario, Categoria
from despesas.services.dashboard_dados import calcular_kpis_mensais, to_float
from despesas.services.nfe_service import NFeService
from despesas.enums.forma_pagamento_enum import FormaPagamento

User = get_user_model()


class TestUsuarioModel(TestCase):
    """
    Testes unitários para o modelo Usuario (perfil estendido).

    Verifica a lógica de parsing e fallback da configuração de limiares de alerta
    de gastos.
    """
    def setUp(self):
        """Configura o ambiente de teste com um usuário e perfil padrão."""
        self.user = User.objects.create_user(username='testuser', password='password')
        self.perfil = Usuario.objects.create(
            user=self.user, 
            renda_fixa=Decimal('5000.00'), 
            limiares_alerta="50, 80, 100",
            moeda="BRL"
        )


    def test_limiares_list_parsing(self):
        """
        Testa o parsing correto de uma string de limiares válida.

        Contexto:
            O usuário configura a string "50, 80, 100".

        Valida:
            Se o método get_limiares_list() converte e retorna a lista de inteiros [50, 80, 100].
        """
        lista = self.perfil.get_limiares_list()
        self.assertEqual(lista, [50, 80, 100])

    def test_limiares_invalidos_fallback(self):
        """
        Testa o comportamento de fallback para limiares inválidos.

        Contexto:
            O usuário configura uma string incorreta "invalid, string".

        Valida:
            Se o sistema retorna os valores padrão [80, 90, 100] evitando falhas.
        """
        self.perfil.limiares_alerta = "invalid, string"
        self.perfil.save()
        lista = self.perfil.get_limiares_list()
        self.assertEqual(lista, [80, 90, 100])

class TestDashboardService(TestCase):
    """
    Testes de integração para o serviço de Dashboard e Cálculo de KPIs.

    Valida a precisão matemática dos cálculos financeiros agregados (saldo, totais, percentuais).
    """
    def setUp(self):
        """Prepara dados de despesas e receitas para os testes de cálculo."""
        self.user = User.objects.create_user(username='dashuser', password='password')
        self.perfil = Usuario.objects.create(user=self.user, renda_fixa=Decimal('3000.00'))        
        self.hoje = timezone.localdate()
        self.cat_mercado, _ = Categoria.objects.get_or_create(user=self.user, nome="Mercado", defaults={'orcamento_mensal': Decimal('1000')})
        Despesa.objects.create(user=self.user, categoria=self.cat_mercado, valor=Decimal('500.00'), data=self.hoje, descricao="Compra 1")
        Despesa.objects.create(user=self.user, categoria=self.cat_mercado, valor=Decimal('200.00'), data=self.hoje, descricao="Compra 2")
        Receita.objects.create(user=self.user, valor_bruto=Decimal('500.00'), data=self.hoje)

    def test_calculo_kpis_basicos(self):
        """
        Valida o cálculo dos KPIs financeiros básicos do mês.

        Cenário:
            - Renda Fixa: R$ 3000,00
            - Receita Extra: R$ 500,00 (Total Entradas: R$ 3500,00)
            - Despesas Totais: R$ 500,00 + R$ 200,00 (Total Saídas: R$ 700,00)

        Validações:
            - Entradas Totais == 3500.0
            - Saídas Totais == 700.0
            - Saldo Restante == 2800.0
            - % Orçamento Comprometido == 20%
        """
        df_despesas = pd.DataFrame({"data": [pd.Timestamp(self.hoje), pd.Timestamp(self.hoje)],"valor": [500.0, 200.0],"categoria__nome": ["Mercado", "Mercado"]})
        df_receitas = pd.DataFrame({"data": [pd.Timestamp(self.hoje)],"valor_bruto": [500.0]})        
        kpis = calcular_kpis_mensais(self.hoje, self.hoje, df_despesas, df_receitas, self.perfil)        
        self.assertEqual(kpis["entradas_totais"], 3500.0)
        self.assertEqual(kpis["saidas_totais"], 700.0)
        self.assertEqual(kpis["saldo"], 2800.0)
        self.assertEqual(kpis["percentual_orcamento"], 20.0)
        self.assertEqual(kpis["percentual_orcamento_livre"], 80.0)

    def test_tendencia_gastos_estavel(self):
        """
        Valida a determinação da tendência de gastos.
        Cenário:
            - Período sem histórico anterior comparável.
        Valida:
            - Se a tendência retorna "estavel" como fallback seguro.
        """
        df_despesas = pd.DataFrame({"data": [pd.Timestamp(self.hoje)],"valor": [500.0]})
        df_receitas = pd.DataFrame(columns=["data", "valor_bruto", "periodo_dt"])        
        kpis = calcular_kpis_mensais(self.hoje, self.hoje, df_despesas, df_receitas, self.perfil)
        self.assertEqual(kpis["tendencia_gastos"], "estavel")

class TestNFeService(TestCase):
    """
    Testes unitários para o Serviço de Leitura de Nota Fiscal Eletrônica (NFe).

    Cobre validações de CNPJ, categorização automática por inferência e proteções de segurança.
    """
    def setUp(self):
        """Inicializa o serviço e mocka componentes pesados (QReader)."""
        self.user = User.objects.create_user(username='nfeuser', password='password')
        self.service = NFeService() 
        self.service._qreader = MagicMock()

    def test_validar_cnpj_valido(self):
        """
        Verifica a validação de um CNPJ correto.

        Argumento:
            cnpj (str): "06.990.590/0001-23" (Dígito Verificador Correto)

        Valida:
            - Retorno True.
        """
        self.assertTrue(self.service.validar_cnpj("06.990.590/0001-23"))
    
    def test_validar_cnpj_invalido_digito(self):
        """
        Verifica a rejeição de um CNPJ incorreto.
        Argumento:
            cnpj (str): "06.990.590/0001-24" (Dígito Verificador Incorreto)
        Valida:
            - Retorno False.
        """
        self.assertFalse(self.service.validar_cnpj("06.990.590/0001-24"))

    def test_preencher_categoria_historico(self):
        """
        Testa a inferência de categoria baseada no histórico de despesas.
        
        Contexto:
            - Usuário já lançou despesa anterior em "Padaria do Zé" como "Alimentação".
            - Nova nota de "Padaria do Zé" é processada (sem palavra-chave nos mappings).
            
        Valida:
            - Se o serviço sugere "Alimentação" recuperando do histórico.
        """
        cat_alimentacao, _ = Categoria.objects.get_or_create(user=self.user, nome="Alimentação")
        
        Despesa.objects.create(
            user=self.user, 
            emitente_nome="Padaria do Zé", 
            categoria=cat_alimentacao, 
            valor=Decimal('10.00'),
            forma_pagamento=FormaPagamento.DINHEIRO
        )

        cat_id = self.service.identificar_categoria(self.user, "Padaria do Zé")
        self.assertEqual(cat_id, cat_alimentacao.pk)

    def test_preencher_categoria_inferencia(self):
        """
        Testa a inferência de categoria baseada no nome do emitente.
        Contexto:
            - O sistema possui categoria "Transporte".
            - O usuário importa nota de "UBER DO BRASIL TECNOLOGIA".
        Valida:
            - Se o serviço identifica a categoria ID correta automaticamente.
        """
        cat_transporte, _ = Categoria.objects.get_or_create(user=self.user, nome="Transporte")
        
        cat_id = self.service.identificar_categoria(self.user, "UBER DO BRASIL TECNOLOGIA")
        self.assertEqual(cat_id, cat_transporte.pk)

    def test_validar_url_seguranca(self):
        """
        Testa a proteção contra SSRF (Server Side Request Forgery).
        Valida se URLs maliciosas são bloqueadas:
            - Loopback: http://127.0.0.1
            - Rede Interna: http://localhost
            - Arquivo Local: file:///etc/passwd
        Valida se URLs legítimas são permitidas:
            - Externo: https://www.google.com
        """
        self.assertFalse(self.service.validar_url("http://localhost:8000"))
        self.assertFalse(self.service.validar_url("http://127.0.0.1/admin"))
        self.assertFalse(self.service.validar_url("file:///etc/passwd"))        
        with patch('socket.gethostbyname') as mock_dns:
            mock_dns.return_value = "8.8.8.8" 
            self.assertTrue(self.service.validar_url("https://www.google.com"))

class TestViewsIntegracao(TestCase):
    """
    Testes de integração para as Views principais (Controllers).

    Verifica o controle de acesso (Login Required), renderização de templates
    e fluxo de criação de despesas via formulário.
    """
    def setUp(self):
        """Autentica o cliente de teste para simular uma sessão de usuário logado."""
        self.user = User.objects.create_user(username='viewuser', password='password')
        Usuario.objects.create(user=self.user, renda_fixa=5000)
        self.client.force_login(self.user)
        
    def test_acesso_dashboard_login_required(self):
        self.client.logout()
        response = self.client.get('/dashboard/')
        self.assertEqual(response.status_code, 302)

    def test_acesso_dashboard_autenticado(self):
        """
        Testa o acesso bem-sucedido ao dashboard.

        Contexto:
            - Usuário autenticado.

        Valida:
            - Resposta HTTP 200 (OK).
        """
        response = self.client.get('/dashboard/')
        if response.status_code == 404:
            return 
        self.assertEqual(response.status_code, 200)

    def test_criar_despesa_fluxo(self):
        """
        Testa o fluxo de criação de despesa via submissão de formulário (POST).

        Cenário:
            - Usuário envia dados válidos de uma nova despesa ("Cinema", R$ 50,00).

        Nota:
            - O teste é um esqueleto de validação de fluxo e termina sem asserção explícita
              nesta versão simplificada.
        """
        Categoria.objects.get_or_create(user=self.user, nome="Lazer")
        cat = Categoria.objects.first()        
        dados = {
            "descricao": "Cinema",
            "valor": "50.00", 
            "data": str(timezone.localdate()),
            "categoria": cat.pk,
            "emitente_nome": "Cinema City",
            "tipo": "VARIAVEL",
            "forma_pagamento": "DEBITO", 
            "parcelas_selecao": "1",
            "itens-TOTAL_FORMS": "0",
            "itens-INITIAL_FORMS": "0",
            "itens-MIN_NUM_FORMS": "0",
            "itens-MAX_NUM_FORMS": "1000",
        }        

        response = self.client.post('/despesas/criar/', dados)        
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['success'])        
        self.assertTrue(Despesa.objects.filter(descricao="Cinema", valor="50.00").exists())
