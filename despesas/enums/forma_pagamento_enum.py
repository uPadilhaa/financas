from django.db import models

class FormaPagamento(models.TextChoices):
    DINHEIRO = "DINHEIRO", "Dinheiro"
    CREDITO = "CREDITO", "Cartão de Crédito"
    DEBITO = "DEBITO", "Cartão de Débito"
    PIX = "PIX", "Pix"
    BOLETO = "BOLETO", "Boleto"
    VALE_ALIMENTACAO = "VALE_ALIMENTACAO", "Vale Alimentação"
    VALE_REFEICAO = "VALE_REFEICAO", "Vale Refeição"
    OUTROS = "OUTROS", "Outros"