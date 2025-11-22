from decimal import Decimal
from django.conf import settings
from django.db import models

class Usuario(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="perfil")
    foto_url = models.URLField(blank=True, null=True)
    moeda = models.CharField(max_length=3, default="BRL")    
    renda_fixa = models.DecimalField("Renda Mensal Fixa (R$)", max_digits=10, decimal_places=2, default=Decimal('0'))
    investimento_fixo = models.DecimalField("Investimento Mensal Fixo (R$)", max_digits=10, decimal_places=2, default=Decimal('0'))    
    limite_mensal = models.DecimalField("Teto Máximo (Hard Cap)", max_digits=10, decimal_places=2, default=Decimal('0'))
    limite_aviso = models.DecimalField("Alerta de Gastos (Soft Cap)", max_digits=10, decimal_places=2, default=Decimal('0'), help_text="Valor para disparar notificações de aviso.")
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.user.get_full_name() or self.user.email