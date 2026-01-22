from django.db.models.signals import post_save, post_delete, pre_save
from django.dispatch import receiver
from django.db import transaction
from despesas.models import Despesa, Usuario
from despesas.tasks import task_verificar_alertas_orcamento 

@receiver(pre_save, sender=Despesa)
def capturar_data_antiga_antes_de_salvar(sender, instance: Despesa, **kwargs):
    if instance.pk:
        try:
            despesa_banco = Despesa.objects.get(pk=instance.pk)
            instance._data_antiga = despesa_banco.data
        except Despesa.DoesNotExist:
            pass

@receiver(post_save, sender=Despesa)
def disparar_alerta_orcamento_ao_salvar_despesa(sender, instance: Despesa, **kwargs):
    if not instance.user:
        return
    transaction.on_commit(lambda: _agendar_verificacao(instance.user, instance.data))
    if hasattr(instance, '_data_antiga'):
        data_velha = instance._data_antiga
        nova_data = instance.data
        if data_velha.month != nova_data.month or data_velha.year != nova_data.year:
            transaction.on_commit(lambda: _agendar_verificacao(instance.user, data_velha))

@receiver(post_delete, sender=Despesa)
def disparar_alerta_orcamento_ao_excluir_despesa(sender, instance: Despesa, **kwargs):
    if not instance.user:
        return
    transaction.on_commit(lambda: _agendar_verificacao(instance.user, instance.data))

def _agendar_verificacao(user, data_ref):
    perfil, _ = Usuario.objects.get_or_create(user=user)
    task_verificar_alertas_orcamento.delay(perfil.id, data_ref)