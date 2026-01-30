from celery import shared_task
from despesas.models import Usuario
from despesas.services.notificacoes_orcamento import verificar_e_disparar_alertas_orcamento
import logging

logger = logging.getLogger(__name__)

@shared_task(bind=True, max_retries=3)
def task_verificar_alertas_orcamento(self, perfil_id, data_referencia=None):
    """
    Executa a verificação de alertas de orçamento em background.

    Utiliza uma thread separada para evitar bloqueio do Worker do Gunicorn,
    essencial para ambientes com Timeout agressivo como o Render.

    Args:
        perfil_id (int): ID do Usuário a ser verificado.
        data_referencia (date, optional): Data de referência para os cálculos.
    """
    import threading
    from django.db import connections
    
    def _execucao_background():
        """
        Função interna executada em Thread separada.

        Gerencia o ciclo de vida da conexão com o banco de dados para evitar
        leaks e erros de thread-safety do Django.
        """
        try:
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

    thread = threading.Thread(target=_execucao_background)
    thread.start()