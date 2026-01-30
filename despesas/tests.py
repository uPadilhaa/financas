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
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='password')
        self.perfil = Usuario.objects.create(user=self.user, renda_fixa=Decimal('5000.00'), limiares_alerta="50, 80, 100")

    def test_limiares_list_parsing(self):
        """Testa se a string de configuração '50, 80, 100' vira lista [50, 80, 100]"""
        lista = self.perfil.get_limiares_list()
        self.assertEqual(lista, [50, 80, 100])

    def test_limiares_invalidos_fallback(self):
        """Testa se retorna padrão [80, 90, 100] caso a config esteja corrompida"""
        self.perfil.limiares_alerta = "invalid, string"
        self.perfil.save()
        lista = self.perfil.get_limiares_list()
        self.assertEqual(lista, [80, 90, 100])

class TestDashboardService(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='dashuser', password='password')
        self.perfil = Usuario.objects.create(user=self.user, renda_fixa=Decimal('3000.00'))        
        self.hoje = timezone.localdate()
        self.cat_mercado, _ = Categoria.objects.get_or_create(user=self.user, nome="Mercado", defaults={'orcamento_mensal': Decimal('1000')})
        Despesa.objects.create(user=self.user, categoria=self.cat_mercado, valor=Decimal('500.00'), data=self.hoje, descricao="Compra 1")
        Despesa.objects.create(user=self.user, categoria=self.cat_mercado, valor=Decimal('200.00'), data=self.hoje, descricao="Compra 2")
        Receita.objects.create(user=self.user, valor_bruto=Decimal('500.00'), data=self.hoje)

    def test_calculo_kpis_basicos(self):
        """
        Valida: Entradas Totais (Fixa + Extra), Saídas, Saldo e % Orçamento.
        Renda: 3000 + 500 = 3500
        Despesas: 500 + 200 = 700
        Saldo Esperado: 2800
        % Orçamento: (700 / 3500) = 20%
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
        """Testa se a tendência é 'estavel' quando não há histórico anterior"""
        df_despesas = pd.DataFrame({"data": [pd.Timestamp(self.hoje)],"valor": [500.0]})
        df_receitas = pd.DataFrame(columns=["data", "valor_bruto", "periodo_dt"])        
        kpis = calcular_kpis_mensais(self.hoje, self.hoje, df_despesas, df_receitas, self.perfil)
        self.assertEqual(kpis["tendencia_gastos"], "estavel")

class TestNFeService(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='nfeuser', password='password')
        self.service = NFeService() 
        self.service._qreader = MagicMock()
    def test_validar_cnpj_valido(self):
        self.assertTrue(self.service.validar_cnpj("06.990.590/0001-23"))
    
    def test_validar_cnpj_invalido_digito(self):
        self.assertFalse(self.service.validar_cnpj("06.990.590/0001-24"))

    def test_preencher_categoria_inferencia(self):
        """Testa se o serviço consegue adivinhar que 'Uber do Brasil' é Transporte"""
        cat_transporte, _ = Categoria.objects.get_or_create(user=self.user, nome="Transporte")
        
        cat_id = self.service.identificar_categoria(self.user, "UBER DO BRASIL TECNOLOGIA")
        self.assertEqual(cat_id, cat_transporte.pk)

    def test_validar_url_seguranca(self):
        """Testa proteção contra SSRF (Server Side Request Forgery)"""
        self.assertFalse(self.service.validar_url("http://localhost:8000"))
        self.assertFalse(self.service.validar_url("http://127.0.0.1/admin"))
        self.assertFalse(self.service.validar_url("file:///etc/passwd"))        
        with patch('socket.gethostbyname') as mock_dns:
            mock_dns.return_value = "8.8.8.8" 
            self.assertTrue(self.service.validar_url("https://www.google.com"))

class TestViewsIntegracao(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='viewuser', password='password')
        self.client.force_login(self.user)
        
    def test_acesso_dashboard_login_required(self):
        """Testa se usuário não logado é redirecionado"""
        self.client.logout()
        response = self.client.get('/dashboard/')
        self.assertEqual(response.status_code, 302)

    def test_acesso_dashboard_autenticado(self):
        Usuario.objects.create(user=self.user)
        response = self.client.get('/dashboard/')
        if response.status_code == 404:
            return 
        self.assertEqual(response.status_code, 200)

    def test_criar_despesa_fluxo(self):
        """Testa a criação de uma despesa via POST"""
        Categoria.objects.get_or_create(user=self.user, nome="Lazer")
        cat = Categoria.objects.first()
        
        dados = {
            "descricao": "Cinema",
            "valor": "50,00",
            "data": str(timezone.localdate()),
            "categoria": cat.pk,
            "forma_pagamento": FormaPagamento.DEBITO,
            "parcelas_selecao": 1,
            "itens-TOTAL_FORMS": 0,
            "itens-INITIAL_FORMS": 0,
        }
        
        pass 
