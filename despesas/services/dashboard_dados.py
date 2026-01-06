from datetime import timedelta
from typing import Dict, Any, Tuple
import pandas as pd
from dateutil.relativedelta import relativedelta
from django.db.models import Sum
from django.utils import timezone
from despesas.models import Despesa, Receita, Usuario, Categoria

def to_float(valor) -> float:
    """Converte valores numéricos ou texto para float com fallback em 0.0."""
    try:
        return float(valor)
    except (TypeError, ValueError):
        return 0.0


def carregar_bases_ultimo_ano(usuario) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Carrega receitas e despesas do último ano para o usuário informado
    e retorna dois DataFrames normalizados (df_despesas, df_receitas).
    """
    hoje = timezone.localdate()
    data_inicio = hoje - timedelta(days=365)
    qs_despesas = (
        Despesa.objects.filter(user=usuario, data__gte=data_inicio)
        .select_related("categoria")
        .values(
            "data",
            "valor",
            "categoria__nome",
            "categoria__orcamento_mensal",
            "tipo",
            "emitente_nome",
        )
    )
    df_despesas = pd.DataFrame(list(qs_despesas))
    if not df_despesas.empty:
        df_despesas["data"] = pd.to_datetime(df_despesas["data"])
        df_despesas["valor"] = df_despesas["valor"].map(to_float)
        df_despesas["mes_ano"] = df_despesas["data"].dt.to_period("M").astype(str)
        df_despesas["dia"] = df_despesas["data"].dt.day
        df_despesas["dia_semana"] = df_despesas["data"].dt.day_name()

        mapa_dias = {
            "Monday": "Seg",
            "Tuesday": "Ter",
            "Wednesday": "Qua",
            "Thursday": "Qui",
            "Friday": "Sex",
            "Saturday": "Sáb",
            "Sunday": "Dom",
        }
        df_despesas["dia_semana"] = df_despesas["dia_semana"].map(mapa_dias)
    else:
        df_despesas = pd.DataFrame(
            columns=[
                "data",
                "valor",
                "mes_ano",
                "dia",
                "categoria__nome",
                "emitente_nome",
                "tipo",
                "dia_semana",
            ]
        )

    qs_receitas = (
        Receita.objects.filter(user=usuario, data__gte=data_inicio)
        .values("data", "valor_bruto", "valor_investimento")
    )
    df_receitas = pd.DataFrame(list(qs_receitas))

    if not df_receitas.empty:
        df_receitas["data"] = pd.to_datetime(df_receitas["data"])
        df_receitas["mes_ano"] = df_receitas["data"].dt.to_period("M").astype(str)
        df_receitas["valor_bruto"] = df_receitas["valor_bruto"].map(to_float)
        df_receitas["valor_investimento"] = df_receitas["valor_investimento"].map(
            to_float
        )
    else:
        df_receitas = pd.DataFrame(
            columns=["data", "valor_bruto", "valor_investimento", "mes_ano"]
        )

    return df_despesas, df_receitas


def calcular_kpis_mensais(
    hoje,
    data_referencia,
    df_despesas: pd.DataFrame,
    df_receitas: pd.DataFrame,
    perfil: Usuario,
) -> Dict[str, Any]:
    """
    Calcula todos os indicadores (KPIs) usados no dashboard
    para o mês de referência.
    """
    mes_ref = data_referencia.month
    ano_ref = data_referencia.year
    if not df_despesas.empty:
        df_despesas_mes = df_despesas[
            (df_despesas["data"].dt.month == mes_ref)
            & (df_despesas["data"].dt.year == ano_ref)
        ]
    else:
        df_despesas_mes = pd.DataFrame(columns=df_despesas.columns)

    if not df_receitas.empty:
        df_receitas_mes = df_receitas[
            (df_receitas["data"].dt.month == mes_ref)
            & (df_receitas["data"].dt.year == ano_ref)
        ]
    else:
        df_receitas_mes = pd.DataFrame(columns=df_receitas.columns)

    renda_fixa = to_float(perfil.renda_fixa)
    investimento_fixo = to_float(perfil.investimento_fixo)
    total_extra_bruto = df_receitas_mes["valor_bruto"].sum()
    total_extra_inv = df_receitas_mes["valor_investimento"].sum()
    entradas_totais = renda_fixa + total_extra_bruto
    investimentos_totais = investimento_fixo + total_extra_inv
    saidas_totais = df_despesas_mes["valor"].sum()

    total_disponivel = entradas_totais - investimentos_totais
    saldo = total_disponivel - saidas_totais

    if total_disponivel > 0:
        percentual_orcamento = saidas_totais / total_disponivel * 100
    else:
        percentual_orcamento = 0

    percentual_orcamento_gasto = max(0, min(percentual_orcamento, 100))
    percentual_orcamento_livre = max(0, 100 - percentual_orcamento_gasto)
    tendencia_gastos = "sem_base"
    percentual_diferenca_gastos = 0.0

    if not df_despesas.empty:
        primeiro_dia_mes = data_referencia
        ultimo_dia_mes_anterior = primeiro_dia_mes - timedelta(days=1)
        mes_anterior = ultimo_dia_mes_anterior.month
        ano_anterior = ultimo_dia_mes_anterior.year

        df_mes_anterior = df_despesas[
            (df_despesas["data"].dt.month == mes_anterior)
            & (df_despesas["data"].dt.year == ano_anterior)
        ]
        gasto_anterior = df_mes_anterior["valor"].sum()
        if gasto_anterior > 0:
            percentual_diferenca_gastos = (
                (saidas_totais - gasto_anterior) / gasto_anterior * 100
            )
            if percentual_diferenca_gastos > 3:
                tendencia_gastos = "aumento"
            elif percentual_diferenca_gastos < -3:
                tendencia_gastos = "queda"
            else:
                tendencia_gastos = "estavel"

    lancamentos_futuros = (
        Despesa.objects.filter(user=perfil.user, data__gt=hoje).aggregate(
            total=Sum("valor")
        )["total"]
        or 0
    )

    return {
        "df_despesas_mes": df_despesas_mes,
        "df_receitas_mes": df_receitas_mes,
        "renda_fixa": renda_fixa,
        "investimento_fixo": investimento_fixo,
        "total_extra_bruto": total_extra_bruto,
        "total_extra_inv": total_extra_inv,
        "entradas_totais": entradas_totais,
        "investimentos_totais": investimentos_totais,
        "saidas_totais": saidas_totais,
        "total_disponivel": total_disponivel,
        "saldo": saldo,
        "percentual_orcamento": percentual_orcamento,
        "percentual_orcamento_gasto": percentual_orcamento_gasto,
        "percentual_orcamento_livre": percentual_orcamento_livre,
        "tendencia_gastos": tendencia_gastos,
        "percentual_diferenca_gastos": percentual_diferenca_gastos,
        "lancamentos_futuros": lancamentos_futuros,
    }


def carregar_categorias_orcamento(usuario) -> Dict[str, float]:
    """
    Retorna um dicionário {nome_categoria: orcamento_mensal_float}
    para o usuário informado.
    """
    qs_categorias = Categoria.objects.filter(user=usuario).values(
        "nome", "orcamento_mensal"
    )
    return {c["nome"]: to_float(c["orcamento_mensal"]) for c in qs_categorias}


def obter_dados_dashboard(request) -> Dict[str, Any]:
    """
    Orquestra o carregamento de dados, cálculo de KPIs e demais
    estruturas necessárias para o dashboard.
    Retorna um dicionário que será consumido pelas views e
    pelo módulo de gráficos.
    """
    hoje = timezone.localdate()
    intervalo_bruto = request.GET.get("range", "6m")
    if intervalo_bruto == "1y":
        intervalo_bruto = "12m"

    intervalo = intervalo_bruto if intervalo_bruto in ("6m", "12m", "future") else "6m"

    if intervalo == "6m":
        titulo_evolucao = "Despesas dos últimos 6 meses"
    elif intervalo == "12m":
        titulo_evolucao = "Despesas do último ano"
    else:
        titulo_evolucao = "Lançamentos futuros (próximos meses)"

    escopo_mes = request.GET.get("scope", "atual")
    if escopo_mes not in ("anterior", "atual", "proximo"):
        escopo_mes = "atual"

    primeiro_dia_mes_atual = hoje.replace(day=1)
    if escopo_mes == "anterior":
        data_referencia = primeiro_dia_mes_atual - relativedelta(months=1)
    elif escopo_mes == "proximo":
        data_referencia = primeiro_dia_mes_atual + relativedelta(months=1)
    else:
        data_referencia = primeiro_dia_mes_atual

    perfil, _ = Usuario.objects.get_or_create(user=request.user)
    df_despesas, df_receitas = carregar_bases_ultimo_ano(request.user)
    kpis = calcular_kpis_mensais(
        hoje=hoje,
        data_referencia=data_referencia,
        df_despesas=df_despesas,
        df_receitas=df_receitas,
        perfil=perfil,
    )

    categorias_orcamento = carregar_categorias_orcamento(request.user)

    contexto = {
        "hoje": hoje,
        "data_referencia": data_referencia,
        "escopo_mes": escopo_mes,
        "periodo_filtro": intervalo,
        "titulo_evo": titulo_evolucao,
        "perfil": perfil,
        "entradas_totais": kpis["entradas_totais"],
        "renda_fixa": kpis["renda_fixa"],
        "renda_extra": kpis["total_extra_bruto"],
        "investimentos_totais": kpis["investimentos_totais"],
        "saidas_totais": kpis["saidas_totais"],
        "total_disponivel": kpis["total_disponivel"],
        "saldo": kpis["saldo"],
        "pct_orcamento": kpis["percentual_orcamento"],
        "pct_orcamento_livre": kpis["percentual_orcamento_livre"],
        "tendencia_gastos": kpis["tendencia_gastos"],
        "pct_diff_gastos": kpis["percentual_diferenca_gastos"],
        "lancamentos_futuros": kpis["lancamentos_futuros"],
    }

    return {
        "contexto": contexto,
        "df_despesas": df_despesas,
        "df_receitas": df_receitas,
        "df_despesas_mes": kpis["df_despesas_mes"],
        "df_receitas_mes": kpis["df_receitas_mes"],
        "categorias_orcamento": categorias_orcamento,
        "intervalo": intervalo,
        "data_referencia": data_referencia,
        "perfil": perfil,
        "hoje": hoje,
    }