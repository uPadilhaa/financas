import logging
from django.conf import settings
from django.core.mail import send_mail
from django.urls import reverse
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from despesas.models import AlertaOrcamento, Usuario
from despesas.services.orcamento import calcular_orcamento_mensal

logger = logging.getLogger(__name__)

MESES_PT = {
    1: "Janeiro", 2: "Fevereiro", 3: "Março", 4: "Abril",
    5: "Maio", 6: "Junho", 7: "Julho", 8: "Agosto",
    9: "Setembro", 10: "Outubro", 11: "Novembro", 12: "Dezembro",
}

def formatar_real(valor: float) -> str:
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def _obter_configuracao_mensagem(limiar: int) -> dict:
    """
    Retorna a configuração visual/textual do e-mail baseada no nível de alerta.

    Args:
        limiar (int): A porcentagem do orçamento atingida (ex: 80, 90, 100).

    Returns:
        dict: Dicionário contendo cor, emoji, títulos e dicas personalizadas.
    """
    if limiar <= 50:
        return {
            "cor": "#3dc944",  
            "emoji": "🌱",
            "titulo": "Tudo sob controle!",
            "subtitulo": f"Você utilizou {limiar}% do orçamento. Segue o plano!",
            "dicas": [
                "Ótimo controle! Continue acompanhando.",
                "Verifique se todas as contas do mês já foram lançadas.",
            ]
        }
    elif limiar <= 75:
        return {
            "cor": "#ffc107",  
            "emoji": "⚠️",
            "titulo": "Sinal de Atenção",
            "subtitulo": f"Opa! Você chegou a {limiar}% do limite.",
            "dicas": [
                "Hora de pisar no freio com gastos supérfluos.",
                "Evite novas compras parceladas por enquanto."
            ]
        }
    elif limiar < 100:
        return {
            "cor": "#fd7e14",  
            "emoji": "🚨",
            "titulo": "Zona de Risco!",
            "subtitulo": f"Cuidado! {limiar}% tomado. O orçamento vai fechar?",
            "dicas": [
                "Pare gastos não essenciais IMEDIATAMENTE.",
                "Revise o extrato: tem algo que pode ser cancelado?",
            ]
        }
    else:
        return {
            "cor": "#dc3545",  
            "emoji": "🔥",
            "titulo": "Orçamento Estourado!",
            "subtitulo": f"Você atingiu {limiar}% do planejado.",
            "dicas": [
                "Você está gastando mais do que planejou.",
                "Não faça novas dívidas. O foco agora é contenção.",
                "Ajuste seu orçamento do próximo mês."
            ]
        }

def enviar_email_alerta(perfil: Usuario, limiar: int, dados_orcamento: dict, link_despesas: str):
    """
    Renderiza e envia o e-mail de alerta de orçamento para o usuário.

    Utiliza template HTML (emails/alerta_orcamento.html) e dados de contexto
    como saldo, gastos atuais e dicas financeiras.

    Args:
        perfil (Usuario): O destinatário do alerta.
        limiar (int): O nível de alerta disparado (ex: 80).
        dados_orcamento (dict): Dados calculados sobre o orçamento do mês.
        link_despesas (str): Link direto para o painel de despesas do mês.

    Returns:
        bool: True se o envio foi bem sucedido, False caso contrário.
    """
    orcamento = dados_orcamento["orcamento"]
    total_despesas = dados_orcamento["total_despesas"]
    saldo = orcamento - total_despesas
    mes_nome = MESES_PT.get(dados_orcamento["mes"])
    ano = dados_orcamento["ano"]    
    config = _obter_configuracao_mensagem(limiar)
    percentual_css = f"{min(dados_orcamento['percentual_usado'], 100):.1f}".replace(",", ".")
    
    context = {
        'titulo': config['titulo'],
        'subtitulo': config['subtitulo'],
        'emoji': config['emoji'],
        'cor': config['cor'],
        'dicas': config['dicas'],        
        'nome_usuario': perfil.user.first_name or perfil.user.username,
        'mes_nome': mes_nome,
        'ano': ano,        
        'orcamento_fmt': formatar_real(orcamento),
        'total_despesas_fmt': formatar_real(total_despesas),
        'saldo_fmt': formatar_real(saldo),
        'saldo_negativo': saldo < 0,        
        'percentual_usado': dados_orcamento['percentual_usado'], 
        'percentual_barra': percentual_css,                      
        'link_despesas': link_despesas
    }
    try:
        html_body = render_to_string('emails/alerta_orcamento.html', context)
        texto_puro = strip_tags(html_body)
    except Exception as e:
        logger.warning(f"Erro renderizando template de email: {e}")
        html_body = f"<h1>{config['titulo']}</h1><p>Você atingiu {limiar}% do orçamento.</p>"
        texto_puro = f"Você atingiu {limiar}% do orçamento."
    
    assunto = f"[BpCash] {config['emoji']} Alerta: {limiar}% do orçamento de {mes_nome}"
    try:
        send_mail(subject=assunto, message=texto_puro, html_message=html_body, from_email=settings.DEFAULT_FROM_EMAIL, recipient_list=[perfil.user.email], fail_silently=False)
        return True
    except Exception as e:
        logger.error(f"Erro ao enviar email para {perfil.user.email}: {e}")
        return False

def verificar_e_disparar_alertas_orcamento(perfil: Usuario, data_referencia=None, base_url: str | None = None):
    """
    Verifica se o usuário atingiu algum limiar de alerta configurado e dispara notificação.

    Calcula o gasto atual vs renda fixa. Se, por exemplo, o gasto ultrapassar 80%
    e o usuário tiver configurado alerta para 80%, um e-mail é enviado.
    Cria registro em AlertaOrcamento para evitar envio duplicado no mesmo mês.

    Args:
        perfil (Usuario): O usuário a ser verificado.
        data_referencia (date, optional): Data para verificação (default: hoje).
        base_url (str, optional): Base URL para construção de links no e-mail.
    """
    if not getattr(perfil, "alertas_email_ativos", True):
        return

    info = calcular_orcamento_mensal(perfil, data_referencia=data_referencia)    
    orcamento = info["orcamento"]
    percentual_atual = info["percentual_usado"]
    ano = info["ano"]
    mes = info["mes"]    
    if orcamento <= 0:
        return

    AlertaOrcamento.objects.filter(perfil=perfil, ano=ano, mes=mes, percentual__gt=percentual_atual).delete()
    if hasattr(perfil, 'get_limiares_list'):
        limiares_usuario = perfil.get_limiares_list()
    else:
        limiares_usuario = [80, 90, 100] 

    limiares_atingidos = [p for p in limiares_usuario if percentual_atual >= p]    
    if not limiares_atingidos:
        return

    limiar_maximo = max(limiares_atingidos)
    if AlertaOrcamento.objects.filter(perfil=perfil, ano=ano, mes=mes, percentual__gt=limiar_maximo).exists():
        return

    try:
        alerta, created = AlertaOrcamento.objects.get_or_create(
            perfil=perfil, 
            ano=ano, 
            mes=mes, 
            percentual=limiar_maximo
        )
    except Exception:
        return

    if not created:
        return
    
    path_url = reverse("listar_despesa")
    qs = f"?mes={mes}&ano={ano}"
    if base_url:
        link_despesas = f"{base_url.rstrip('/')}{path_url}{qs}"
    else:
        site_url = getattr(settings, "SITE_URL", "http://127.0.0.1:8000").rstrip("/")
        link_despesas = f"{site_url}{path_url}{qs}"

    sucesso = enviar_email_alerta(perfil, limiar_maximo, info, link_despesas)    
    if not sucesso:
        alerta.delete()
        logger.warning(f"Falha ao enviar email para {perfil.user.email}. Alerta de {limiar_maximo}% removido para nova tentativa.")
    else:
        logger.info(f"Alerta de orçamento ({limiar_maximo}%) enviado para {perfil.user.email}")