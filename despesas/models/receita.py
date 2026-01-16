from django.conf import settings
from django.db import models
from django.utils import timezone
from decimal import Decimal

class Receita(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="receitas")
    descricao = models.CharField("Descrição", max_length=200)
    valor_bruto = models.DecimalField("Valor Bruto (R$)", max_digits=10, decimal_places=2)
    # valor_investimento = models.DecimalField("Investimentos / Retenções (R$)", max_digits=10, decimal_places=2, default=0)    
    data = models.DateField("Data de Recebimento", default=timezone.localdate)
    observacoes = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ["-data", "-id"]
        verbose_name = "Receita"
        verbose_name_plural = "Receitas"

    def __str__(self):
        return f"{self.descricao} - {self.data.strftime('%m/%Y')}"

    @property
    def valor_disponivel(self):
        return self.valor_bruto 