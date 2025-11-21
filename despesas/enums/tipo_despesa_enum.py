from django.db import models

class TipoDespesa(models.TextChoices):
    FIXA = "FIXA", "Fixa"
    VARIAVEL = "VARIAVEL", "Variável"