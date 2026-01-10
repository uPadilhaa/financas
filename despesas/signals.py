import threading
import logging
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.db import transaction
from despesas.models import Despesa, Usuario

logger = logging.getLogger(__name__)

def _executar_verificacao_background(perfil_id, data_ref):
    """
    Função que roda em segundo plano (background).
    Ela abre sua própria conexão com o banco e faz o envio do e-mail
    sem travar o usuário.
    """
    from despesas.services.notificacoes_orcamento import verificar_e_disparar_alertas_orcamento
    from despesas.models import Usuario

    try:
        perfil = Usuario.objects.get(id=perfil_id)
        verificar_e_disparar_alertas_orcamento(perfil=perfil, data_referencia=data_ref)
    except Exception as e:
        logger.error(f"Erro ao processar alerta em background: {e}")

@receiver(post_save, sender=Despesa)
def disparar_alerta_orcamento_ao_salvar_despesa(sender, instance: Despesa, **kwargs):
    if not instance.user:
        return
    perfil, _ = Usuario.objects.get_or_create(user=instance.user)
    perfil_id = perfil.id
    data_ref = instance.data
    transaction.on_commit(lambda: threading.Thread(
        target=_executar_verificacao_background,
        args=(perfil_id, data_ref),
        daemon=True 
    ).start())

@receiver(post_delete, sender=Despesa)
def disparar_alerta_orcamento_ao_excluir_despesa(sender, instance: Despesa, **kwargs):
    if not instance.user:
        return

    perfil, _ = Usuario.objects.get_or_create(user=instance.user)
    perfil_id = perfil.id
    data_ref = instance.data

    transaction.on_commit(lambda: threading.Thread(
        target=_executar_verificacao_background,
        args=(perfil_id, data_ref),
        daemon=True
    ).start())