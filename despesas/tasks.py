from celery import shared_task
from despesas.models import Usuario
from despesas.services.notificacoes_orcamento import verificar_e_disparar_alertas_orcamento
import logging

logger = logging.getLogger(__name__)

@shared_task(bind=True, max_retries=3)
def task_verificar_alertas_orcamento(self, perfil_id, data_referencia=None):
    """
    Task assíncrona para verificar e enviar alertas.
    Se falhar (ex: erro de rede), tenta de novo automaticamente (max_retries=3).
    """
    try:
        try:
            perfil = Usuario.objects.get(id=perfil_id)
        except Usuario.DoesNotExist:
            logger.warning(f"Task abortada: Perfil ID {perfil_id} não encontrado.")
            return

        verificar_e_disparar_alertas_orcamento(perfil, data_referencia)

    except Exception as exc:
        logger.error(f"Erro na task de alerta para perfil {perfil_id}: {exc}")
        raise self.retry(exc=exc, countdown=60)