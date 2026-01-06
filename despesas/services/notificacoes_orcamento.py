import logging
from django.conf import settings
from django.core.mail import send_mail
from django.urls import reverse
from django.utils import timezone
from despesas.models import AlertaOrcamento, Usuario
from despesas.services.orcamento import calcular_orcamento_mensal

logger = logging.getLogger(__name__)
LIMIARES_PADRAO = [30, 50, 70, 80, 90, 100]
MESES_PT = {
    1: "janeiro", 2: "fevereiro", 3: "março", 4: "abril",
    5: "maio", 6: "junho", 7: "julho", 8: "agosto",
    9: "setembro", 10: "outubro", 11: "novembro", 12: "dezembro",
}

def formatar_real(valor: float) -> str:
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def barra_progresso(percentual: float) -> str:
    blocos = 10
    usados = max(0, min(blocos, round(percentual / 10)))
    return f"[{'█' * usados}{'░' * (blocos - usados)}] {percentual:.1f}%"

def _tom_mensagem(limiar: int) -> dict:
    if limiar <= 50:
        return {
            "emoji": "🌱" if limiar == 30 else "⚖️",
            "titulo": "Tudo sob controle (por enquanto)",
            "dicas": [
                "Se quiser manter o ritmo, dá uma olhada nas categorias que mais cresceram.",
                "Evite pequenas compras repetidas (elas somam rápido 😅).",
            ],
        }
    if limiar in (70, 80):
        return {
            "emoji": "🟡" if limiar == 70 else "🧡",
            "titulo": "Atenção — você está chegando perto do limite",
            "dicas": [
                "Segure compras não essenciais nos próximos dias.",
                "Se possível, revise assinaturas/recorrências do mês.",
            ],
        }
    return {
        "emoji": "🚨" if limiar == 90 else "🧾",
        "titulo": "Alerta forte — risco de estourar o orçamento",
        "dicas": [
            "Pausa estratégica: adie o que não for essencial.",
            "Revise despesas grandes do mês e veja o que dá para replanejar.",
            "Se foi parcelado, lembre: as parcelas já impactam os próximos meses também.",
        ],
    }

def montar_mensagem_percentual(perfil: Usuario, limiar: int, ano: int, mes: int, total_despesas: float, orcamento: float, percentual_atual: float, link_despesas: str, ) -> tuple[str, str]:
    nome_mes = f"{MESES_PT.get(mes, str(mes)).capitalize()}/{ano}"
    nome_usuario = perfil.user.first_name or perfil.user.username or "Olá"
    tom = _tom_mensagem(limiar)
    emoji = tom["emoji"]
    proximos = [p for p in LIMIARES_PADRAO if p > limiar]
    proximo_limiar = proximos[0] if proximos else None
    valor_limiar = orcamento * (limiar / 100)
    restante = orcamento - total_despesas
    bloco_proximo = ""
    if proximo_limiar:
        valor_proximo = orcamento * (proximo_limiar / 100)
        faltam = max(0.0, valor_proximo - total_despesas)
        bloco_proximo = (
            f"\n🎯 Próximo marco: {proximo_limiar}% ({formatar_real(valor_proximo)})"
            f"\nFaltam: {formatar_real(faltam)}"
        )
    hoje = timezone.localdate()
    if (ano, mes) > (hoje.year, hoje.month):
        contexto_mes = f"Você já tem despesas LANÇADAS para {nome_mes}."
    elif (ano, mes) < (hoje.year, hoje.month):
        contexto_mes = f"Este alerta é sobre o mês de {nome_mes} (um mês anterior)."
    else:
        contexto_mes = f"Este alerta é sobre o seu mês atual: {nome_mes}."

    assunto = f"[BpCash] {emoji} {limiar}% do orçamento em {nome_mes}"
    dicas = "\n".join([f"• {d}" for d in tom["dicas"]])
    corpo = f"""Olá, {nome_usuario}! {emoji}

{contexto_mes}

Você atingiu {limiar}% do seu orçamento disponível.

────────── 📌 Resumo do mês ──────────
Orçamento disponível: {formatar_real(orcamento)}
Despesas registradas: {formatar_real(total_despesas)}
Uso do orçamento:     {percentual_atual:.1f}%
Marco de referência:  {limiar}% ≈ {formatar_real(valor_limiar)}
Saldo estimado:       {formatar_real(restante)}

Progresso:
{barra_progresso(percentual_atual)}{bloco_proximo}

💡 Sugestões rápidas:
{dicas}

🔎 Ver despesas deste mês:
{link_despesas}

—  
BpCash • aviso automático (não responda)
"""
    return assunto, corpo

def verificar_e_disparar_alertas_orcamento(perfil: Usuario, data_referencia=None, base_url: str | None = None):
    logger.info()
    if not getattr(perfil, "alertas_email_ativos", True):
        return

    info = calcular_orcamento_mensal(perfil, data_referencia=data_referencia)
    orcamento = info["orcamento"]
    total_despesas = info["total_despesas"]
    percentual = info["percentual_usado"]
    ano = info["ano"]
    mes = info["mes"]
    if orcamento <= 0 or total_despesas <= 0:
        return

    limiares_atingidos = [p for p in LIMIARES_PADRAO if percentual >= p]
    if not limiares_atingidos:
        return

    limiar_escolhido = None
    for p in sorted(limiares_atingidos, reverse=True):
        if not AlertaOrcamento.objects.filter(perfil=perfil, ano=ano, mes=mes, percentual=p).exists():
            limiar_escolhido = p
            break

    if limiar_escolhido is None:
        return

    path = reverse("listar_despesa")
    qs = f"?mes={mes}&ano={ano}"
    if base_url:
        link_despesas = f"{base_url.rstrip('/')}{path}{qs}"
    else:
        site_url = getattr(settings, "SITE_URL", "").rstrip("/")
        link_despesas = f"{site_url}{path}{qs}" if site_url else f"{path}{qs}"

    assunto, corpo = montar_mensagem_percentual(
        perfil=perfil,
        limiar=limiar_escolhido,
        ano=ano,
        mes=mes,
        total_despesas=total_despesas,
        orcamento=orcamento,
        percentual_atual=percentual,
        link_despesas=link_despesas,
    )

    remetente = getattr(settings, "DEFAULT_FROM_EMAIL", None) or "nao-responda@bpcash.local"
    try:
        enviados = send_mail(
            subject=assunto,
            message=corpo,
            from_email=remetente,
            recipient_list=[perfil.user.email],
            fail_silently=False,  
        )
    except Exception:
        logger.exception("Falha ao enviar e-mail de alerta de orçamento.")
        return

    if enviados:
        AlertaOrcamento.objects.get_or_create(
            perfil=perfil, ano=ano, mes=mes, percentual=limiar_escolhido
        )
