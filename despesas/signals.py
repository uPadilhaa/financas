# despesas/signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.db import transaction
from despesas.models import Despesa, Usuario
from despesas.services.notificacoes_orcamento import verificar_e_disparar_alertas_orcamento

@receiver(post_save, sender=Despesa)
def disparar_alerta_orcamento_ao_salvar_despesa(sender, instance: Despesa, **kwargs):
    perfil, _ = Usuario.objects.get_or_create(user=instance.user)
    dt_ref = instance.data
    transaction.on_commit(lambda: verificar_e_disparar_alertas_orcamento(perfil=perfil, data_referencia=dt_ref))
