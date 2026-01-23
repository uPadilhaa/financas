from celery import shared_task
from despesas.models import Usuario
from despesas.services.notificacoes_orcamento import verificar_e_disparar_alertas_orcamento
import logging

logger = logging.getLogger(__name__)

@shared_task(bind=True, max_retries=3)
def task_verificar_alertas_orcamento(self, perfil_id, data_referencia=None):
    """
    Task executada em Thread para evitar bloquear o Worker do Gunicorn no Render (Timeout).
    """
    import threading
    from django.db import connections
    
    def _execucao_background():
        try:
            # Garante que a thread tenha conexão limpa com o banco
            connections.close_all()
            
            try:
                perfil = Usuario.objects.get(id=perfil_id)
                verificar_e_disparar_alertas_orcamento(perfil, data_referencia)
            except Usuario.DoesNotExist:
                logger.warning(f"Task abortada: Perfil ID {perfil_id} não encontrado.")
            except Exception as e:
                logger.error(f"Erro na execução background do alerta: {e}")
                
        finally:
            connections.close_all()

    # Inicia a thread e deixa rodando (Fire-and-forget)
    thread = threading.Thread(target=_execucao_background)
    thread.start()