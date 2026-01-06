from __future__ import annotations
from datetime import date
from typing import Optional, Dict, Any
from django.db.models import Sum
from django.utils import timezone
from despesas.models import Usuario, Receita, Despesa


def to_float(valor) -> float:
    try:
        return float(valor or 0)
    except (TypeError, ValueError):
        return 0.0


def calcular_orcamento_mensal(perfil: Usuario, data_referencia: Optional[date] = None) -> Dict[str, Any]:   
    if data_referencia is None:
        hoje = timezone.localdate()
    else:
        hoje = data_referencia.date() if hasattr(data_referencia, "date") else data_referencia

    ano = hoje.year
    mes = hoje.month
    usuario = perfil.user
    renda_fixa = to_float(getattr(perfil, "renda_fixa", 0))
    investimento_fixo = to_float(getattr(perfil, "investimento_fixo", 0))
    receitas_mes = Receita.objects.filter(user=usuario, data__year=ano, data__month=mes)
    agregados_receitas = receitas_mes.aggregate(
        total_bruto=Sum("valor_bruto"),
        total_invest=Sum("valor_investimento"),
    )
    total_extra_bruto = to_float(agregados_receitas.get("total_bruto"))
    total_extra_invest = to_float(agregados_receitas.get("total_invest"))
    entradas_totais = renda_fixa + total_extra_bruto
    investimentos_totais = investimento_fixo + total_extra_invest
    orcamento = max(0.0, entradas_totais - investimentos_totais)
    despesas_mes = Despesa.objects.filter(user=usuario, data__year=ano, data__month=mes)
    total_despesas = to_float(despesas_mes.aggregate(total=Sum("valor")).get("total"))

    if orcamento > 0:
        percentual_usado = (total_despesas / orcamento) * 100
    else:
        percentual_usado = 0.0

    return {
        "ano": ano,
        "mes": mes,
        "orcamento": float(orcamento),
        "total_despesas": float(total_despesas),
        "percentual_usado": float(percentual_usado),
    }
