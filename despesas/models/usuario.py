from decimal import Decimal
from django.conf import settings
from django.db import models

class Usuario(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="perfil")
    foto_url = models.URLField(blank=True, null=True)
    moeda = models.CharField(max_length=3, default="BRL")    
    renda_fixa = models.DecimalField("Renda Mensal Fixa (R$)", max_digits=10, decimal_places=2, default=Decimal('0'))
    alertas_email_ativos = models.BooleanField("Receber alertas por e-mail", default=True)  
    limiares_alerta = models.CharField("Porcentagens de alerta", max_length=50, default="80, 90, 100", help_text="Separe as porcentagens por vírgula. Ex: 80, 90, 100")  
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.user.get_full_name() or self.user.email

    def get_limiares_list(self):
        """Retorna uma lista de inteiros ex: [80, 90, 100]"""
        try:
            return sorted([int(x.strip()) for x in self.limiares_alerta.split(",") if x.strip().isdigit()])
        except:
            return [80, 90, 100]