from django.conf import settings
from django.db import models
from django.utils import timezone
from decimal import Decimal
from .categoria import Categoria
from despesas.enums.forma_pagamento_enum import FormaPagamento
from despesas.enums.tipo_despesa_enum import TipoDespesa

class Despesa(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="despesas")
    categoria = models.ForeignKey(Categoria, on_delete=models.SET_NULL, null=True, blank=True, related_name="despesas")
    emitente_nome = models.CharField("Emitente / Loja", max_length=200)
    emitente_cnpj = models.CharField("CNPJ do Emitente", max_length=20, blank=True, null=True)
    descricao = models.CharField("Descrição Resumida", max_length=200, blank=True, null=True)    
    valor = models.DecimalField("Valor da Parcela / Líquido", max_digits=10, decimal_places=2)
    valor_total_compra = models.DecimalField("Valor Total da Compra", max_digits=10, decimal_places=2, null=True, blank=True)
    desconto = models.DecimalField("Descontos", max_digits=10, decimal_places=2, default=Decimal(0))   
    parcela_atual = models.IntegerField("Parcela Atual", default=1)
    total_parcelas = models.IntegerField("Total Parcelas", default=1)    
    qtd_total_itens = models.IntegerField("Qtd. Itens", default=0)
    forma_pagamento = models.CharField("Forma de Pagamento", max_length=20, choices=FormaPagamento.choices, default=FormaPagamento.OUTROS)
    tipo = models.CharField("Tipo de Despesa", max_length=10, choices=TipoDespesa.choices, default=TipoDespesa.VARIAVEL)
    data = models.DateField(default=timezone.localdate)
    observacoes = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ["-data", "-id"]
        verbose_name = "Despesa"
        verbose_name_plural = "Despesas"

    def __str__(self) -> str:
        if self.total_parcelas > 1:
            return f"{self.emitente_nome} ({self.parcela_atual}/{self.total_parcelas}) - R$ {self.valor:.2f}"
        return f"{self.emitente_nome} - R$ {self.valor:.2f}"