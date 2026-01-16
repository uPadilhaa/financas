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
    total_extra_bruto = Receita.objects.filter(user=usuario, data__year=ano, data__month=mes).aggregate(total=Sum("valor_bruto"))["total"] or 0    
    entradas_totais = renda_fixa + to_float(total_extra_bruto)
    orcamento = entradas_totais
    total_despesas = Despesa.objects.filter(user=usuario, data__year=ano, data__month=mes).aggregate(total=Sum("valor"))["total"] or 0
    total_despesas = to_float(total_despesas)

    if orcamento > 0:
        percentual_usado = (total_despesas / orcamento) * 100
    else:
        percentual_usado = 100.0 if total_despesas > 0 else 0.0

    return {
        "ano": ano,
        "mes": mes,
        "orcamento": float(orcamento),
        "total_despesas": float(total_despesas),
        "percentual_usado": float(percentual_usado),
    }