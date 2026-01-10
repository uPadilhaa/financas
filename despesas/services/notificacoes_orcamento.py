import logging
from django.conf import settings
from django.core.mail import send_mail
from django.urls import reverse
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from despesas.models import AlertaOrcamento, Usuario
from despesas.services.orcamento import calcular_orcamento_mensal

logger = logging.getLogger(__name__)
LIMIARES_PADRAO = list(range(15, 501, 15))

MESES_PT = {
    1: "Janeiro", 2: "Fevereiro", 3: "Março", 4: "Abril",
    5: "Maio", 6: "Junho", 7: "Julho", 8: "Agosto",
    9: "Setembro", 10: "Outubro", 11: "Novembro", 12: "Dezembro",
}

def formatar_real(valor: float) -> str:
    """Formata float para moeda BRL (ex: R$ 1.230,50)"""
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def _obter_configuracao_mensagem(limiar: int) -> dict:
    """Retorna a 'personalidade' da mensagem (cores, textos) baseada no uso."""
    if limiar <= 45:
        return {
            "cor": "#3dc944",  
            "emoji": "🌱",
            "titulo": "Tudo fluindo bem!",
            "subtitulo": f"Você utilizou {limiar}% do orçamento. Segue o plano!",
            "dicas": [
                "Ótimo controle! Continue acompanhando suas metas.",
                "Que tal verificar se seus investimentos mensais já foram feitos?",
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
                "Verifique se ainda existem contas fixas para cair este mês.",
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
                "Revise o extrato: tem algo que pode ser cancelado ou adiado?",
                "Se ultrapassar 100%, você começará a usar suas reservas."
            ]
        }
    else:
        return {
            "cor": "#dc3545",  
            "emoji": "🔥",
            "titulo": "Orçamento Estourado!",
            "subtitulo": f"Você atingiu {limiar}% do planejado. Atenção máxima!",
            "dicas": [
                "Você está gastando mais do que planejou ganhar/gastar.",
                "Não faça novas dívidas. O foco agora é contenção de danos.",
                "Ajuste seu orçamento do próximo mês para cobrir este furo."
            ]
        }

def enviar_email_alerta(perfil: Usuario, limiar: int, dados_orcamento: dict, link_despesas: str):
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
    except Exception:
        html_body = f"<h1>{config['titulo']}</h1><p>Você atingiu {limiar}% do orçamento.</p>"
        texto_puro = f"Você atingiu {limiar}% do orçamento."
    
    assunto = f"[BpCash] {config['emoji']} Alerta: {limiar}% do orçamento de {mes_nome}"
    try:
        send_mail(
            subject=assunto,
            message=texto_puro,
            html_message=html_body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[perfil.user.email],
            fail_silently=False,
        )
        return True
    except Exception as e:
        logger.error(f"Erro ao enviar email para {perfil.user.email}: {e}")
        return False

def verificar_e_disparar_alertas_orcamento(perfil: Usuario, data_referencia=None, base_url: str | None = None):
    if not getattr(perfil, "alertas_email_ativos", True):
        return

    info = calcular_orcamento_mensal(perfil, data_referencia=data_referencia)    
    orcamento = info["orcamento"]
    percentual = info["percentual_usado"]
    ano = info["ano"]
    mes = info["mes"]
    if orcamento <= 0:
        return

    AlertaOrcamento.objects.filter(
        perfil=perfil, 
        ano=ano, 
        mes=mes, 
        percentual__gt=percentual  
    ).delete()

    limiares_atingidos = [p for p in LIMIARES_PADRAO if percentual >= p]    
    if not limiares_atingidos:
        return

    limiar_maximo = max(limiares_atingidos)
    ja_enviado = AlertaOrcamento.objects.filter(
        perfil=perfil, 
        ano=ano, 
        mes=mes, 
        percentual__gte=limiar_maximo
    ).exists()

    if ja_enviado:
        return

    path = reverse("listar_despesa")
    qs = f"?mes={mes}&ano={ano}"
    if base_url:
        link_despesas = f"{base_url.rstrip('/')}{path}{qs}"
    else:
        site_url = getattr(settings, "SITE_URL", "http://127.0.0.1:8000").rstrip("/")
        link_despesas = f"{site_url}{path}{qs}"

    sucesso = enviar_email_alerta(perfil, limiar_maximo, info, link_despesas)

    if sucesso:
        AlertaOrcamento.objects.create(
            perfil=perfil, ano=ano, mes=mes, percentual=limiar_maximo
        )