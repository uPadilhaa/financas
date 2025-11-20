from django.db import models
from .despesa import Despesa


class ItemDespesa(models.Model):
    despesa = models.ForeignKey(Despesa, on_delete=models.CASCADE, related_name="itens")
    nome = models.CharField(max_length=200)
    codigo = models.CharField(max_length=50, blank=True, null=True)
    # 3 casas decimais para suportar kg (ex: 0.500 kg)
    quantidade = models.DecimalField(max_digits=10, decimal_places=3) 
    unidade = models.CharField(max_length=10, blank=True, null=True)
    valor_unitario = models.DecimalField(max_digits=10, decimal_places=2)
    valor_total = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.nome} ({self.quantidade})"