from django.db import models
from .usuario import Usuario

class AlertaOrcamento(models.Model):
    """
    Registra que um alerta de X% já foi enviado
    para (perfil, ano, mês), para não repetir.
    """
    perfil = models.ForeignKey(Usuario, on_delete=models.CASCADE)
    ano = models.IntegerField()
    mes = models.IntegerField()
    percentual = models.PositiveIntegerField()  # 30, 50, 70, 80, 90, 100
    enviado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("perfil", "ano", "mes", "percentual")

    def __str__(self):
        return f"{self.perfil} - {self.mes:02d}/{self.ano} - {self.percentual}%"