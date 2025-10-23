from django.conf import settings
from django.db import models
from django.utils import timezone

from .categoria import Categoria


class Despesa(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="despesas",)
    categoria = models.ForeignKey(Categoria, on_delete=models.SET_NULL, null=True, blank=True, related_name="despesas",)
    descricao = models.CharField("Descrição", max_length=200)
    valor = models.DecimalField(max_digits=10, decimal_places=2)
    data = models.DateField(default=timezone.localdate)
    observacoes = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ["-data", "-id"]
        verbose_name = "Despesa"
        verbose_name_plural = "Despesas"

    def __str__(self) -> str:
        return f"{self.descricao} - R$ {self.valor:.2f}"
