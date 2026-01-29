from django.conf import settings
from django.db import models
from django.utils.text import slugify
from django.db.models.signals import post_save
from django.dispatch import receiver

class Categoria(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="categorias")
    nome = models.CharField(max_length=100)
    slug = models.SlugField(max_length=120, blank=True)
    nome_normalizado = models.CharField(max_length=120, editable=False, db_index=True)
    orcamento_mensal = models.DecimalField("Orçamento Mensal (R$)", max_digits=10, decimal_places=2, default=0)

    class Meta:
        ordering = ["nome"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "nome_normalizado"],
                name="uniq_categoria_por_usuario_normalizada",
            )
        ]

    def save(self, *args, **kwargs):
        self.nome_normalizado = slugify(self.nome or "", allow_unicode=False)
        self.slug = slugify(self.nome or "", allow_unicode=True)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.nome

@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def criar_categorias_padrao(sender, instance, created, **kwargs):
    if created:
        padroes = ["Mercado", "Farmácia", "Transporte", "Alimentação", "Vestuário", "Casa", "Outros", "Eletrônicos", "Saúde", "Lazer", "Educação", "Pet Shop", "Serviços"]
        objetos = []
        for nome in padroes:
            c = Categoria(user=instance, nome=nome)
            c.nome_normalizado = slugify(nome, allow_unicode=False)
            c.slug = slugify(nome, allow_unicode=True)
            objetos.append(c)

        Categoria.objects.bulk_create(objetos)