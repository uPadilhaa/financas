from datetime import timedelta
from typing import Dict, Any, Tuple, List
import pandas as pd
from dateutil.relativedelta import relativedelta
from django.db.models import Sum
from django.utils import timezone
from despesas.models import Despesa, Receita, Usuario, Categoria

def to_float(valor) -> float:
    """
    Converte um valor arbitrário para float de forma segura.

    Args:
        valor (Any): O valor a ser convertido.

    Returns:
        float: O valor convertido ou 0.0 em caso de erro.
    """
    try:
        return float(valor)
    except (TypeError, ValueError):
        return 0.0

def carregar_bases_ultimo_ano(usuario) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Carrega o histórico financeiro (Despesas e Receitas) dos últimos 2 anos.

    O período estendido de 2 anos é utilizado para garantir histórico suficiente
    para a análise de tendências, mesmo com meses sem movimentação.

    Args:
        usuario (User): O usuário logado.

    Returns:
        Tuple[pd.DataFrame, pd.DataFrame]: DataFrames de Despesas e Receitas normalizados.
    """

    hoje = timezone.localdate()
    data_inicio = hoje - timedelta(days=730)
    
    qs_despesas = (
        Despesa.objects.filter(user=usuario, data__gte=data_inicio)
        .select_related("categoria")
        .values("data", "valor", "categoria__nome", "categoria__orcamento_mensal", "tipo", "emitente_nome")
    )
    df_despesas = pd.DataFrame(list(qs_despesas))
    
    if not df_despesas.empty:
        df_despesas["data"] = pd.to_datetime(df_despesas["data"])
        df_despesas["valor"] = df_despesas["valor"].map(to_float)
        df_despesas["periodo_dt"] = df_despesas["data"].dt.to_period("M").dt.to_timestamp()
    else:
        df_despesas = pd.DataFrame(columns=["data", "valor", "periodo_dt", "categoria__nome"])

    qs_receitas = (
        Receita.objects.filter(user=usuario, data__gte=data_inicio)
        .values("data", "valor_bruto")
    )
    df_receitas = pd.DataFrame(list(qs_receitas))

    if not df_receitas.empty:
        df_receitas["data"] = pd.to_datetime(df_receitas["data"])
        df_receitas["valor_bruto"] = df_receitas["valor_bruto"].map(to_float)
        df_receitas["periodo_dt"] = df_receitas["data"].dt.to_period("M").dt.to_timestamp()
    else:
        df_receitas = pd.DataFrame(columns=["data", "valor_bruto", "periodo_dt"])

    return df_despesas, df_receitas

def obter_meses_ativos(df_despesas: pd.DataFrame, data_ref, limite=6) -> List[pd.Timestamp]:
    """
    Identifica os meses mais recentes que possuem movimentação financeira.

    Args:
        df_despesas (pd.DataFrame): DataFrame contendo as despesas.
        data_ref (date): A data de referência (mês atual visualizado).
        limite (int): Número máximo de meses a retornar (padrão 6).

    Returns:
        List[pd.Timestamp]: Lista de timestamps dos meses ativos encontrados.
    """

    if df_despesas.empty:
        return []
    
    mask = df_despesas["data"] <= pd.Timestamp(data_ref) + pd.offsets.MonthEnd(0)
    df_filtered = df_despesas[mask]
    
    if df_filtered.empty:
        return []

    meses_unicos = df_filtered["periodo_dt"].unique()    
    meses_ordenados = sorted(meses_unicos, reverse=True)    
    meses_finais = sorted(meses_ordenados[:limite])
    
    return meses_finais

def calcular_kpis_mensais(hoje, data_referencia, df_despesas, df_receitas, perfil) -> Dict[str, Any]:
    """
    Calcula os indicadores chave de performance (KPIs) financeiros do mês.

    Calcula totais de entradas, saídas, saldo, percentual de orçamento comprometido
    e tendências de gastos em relação ao mês anterior.

    Args:
        hoje (date): Data atual.
        data_referencia (date): Mês cujos KPIs serão calculados.
        df_despesas (pd.DataFrame): Base de despesas.
        df_receitas (pd.DataFrame): Base de receitas.
        perfil (Usuario): Perfil do usuário contendo renda fixa e configurações.

    Returns:
        Dict[str, Any]: Dicionário com todos os KPIs calculados.
    """
    mes_ref = data_referencia.month
    ano_ref = data_referencia.year

    if not df_despesas.empty:
        df_despesas_mes = df_despesas[
            (df_despesas["data"].dt.month == mes_ref) & (df_despesas["data"].dt.year == ano_ref)
        ]
    else:
        df_despesas_mes = pd.DataFrame(columns=df_despesas.columns)

    if not df_receitas.empty:
        df_receitas_mes = df_receitas[
            (df_receitas["data"].dt.month == mes_ref) & (df_receitas["data"].dt.year == ano_ref)
        ]
    else:
        df_receitas_mes = pd.DataFrame(columns=df_receitas.columns)

    renda_fixa = to_float(perfil.renda_fixa)
    total_extra_bruto = df_receitas_mes["valor_bruto"].sum()
    entradas_totais = renda_fixa + total_extra_bruto
    saidas_totais = df_despesas_mes["valor"].sum()
    saldo = entradas_totais - saidas_totais

    if entradas_totais > 0:
        percentual_orcamento = (saidas_totais / entradas_totais) * 100
    else:
        percentual_orcamento = 0

    percentual_orcamento_livre = max(0, 100 - percentual_orcamento)    
    tendencia_gastos = "estavel"
    percentual_diferenca_gastos = 0.0
    
    if not df_despesas.empty:
        primeiro_dia_mes = data_referencia.replace(day=1)
        mes_anterior_dt = primeiro_dia_mes - relativedelta(months=1)
        
        df_mes_anterior = df_despesas[
            (df_despesas["data"].dt.month == mes_anterior_dt.month) & 
            (df_despesas["data"].dt.year == mes_anterior_dt.year)
        ]
        gasto_anterior = df_mes_anterior["valor"].sum()
        
        if gasto_anterior > 0:
            percentual_diferenca_gastos = ((saidas_totais - gasto_anterior) / gasto_anterior * 100)
            if percentual_diferenca_gastos > 5: tendencia_gastos = "aumento"
            elif percentual_diferenca_gastos < -5: tendencia_gastos = "queda"

    lancamentos_futuros = (
        Despesa.objects.filter(user=perfil.user, data__gt=hoje).aggregate(total=Sum("valor"))["total"] or 0
    )

    return {
        "df_despesas_mes": df_despesas_mes,
        "df_receitas_mes": df_receitas_mes,
        "renda_fixa": renda_fixa,
        "total_extra_bruto": total_extra_bruto,
        "entradas_totais": entradas_totais,
        "saidas_totais": saidas_totais,
        "saldo": saldo,
        "percentual_orcamento": percentual_orcamento,
        "percentual_orcamento_livre": percentual_orcamento_livre,
        "tendencia_gastos": tendencia_gastos,
        "percentual_diferenca_gastos": percentual_diferenca_gastos,
        "lancamentos_futuros": lancamentos_futuros,
    }

def carregar_categorias_orcamento(usuario) -> Dict[str, float]:
    """
    Carrega o mapa de orçamentos definidos por categoria pelo usuário.

    Args:
        usuario (User): O usuário logado.

    Returns:
        Dict[str, float]: Dicionário {NomeCategoria: ValorOrcamento}.
    """
    qs_categorias = Categoria.objects.filter(user=usuario).values("nome", "orcamento_mensal")
    return {c["nome"]: to_float(c["orcamento_mensal"]) for c in qs_categorias}

def obter_dados_dashboard(request) -> Dict[str, Any]:
    """
    Orquestrador principal da obtenção de dados para o Dashboard.

    Gerencia o carregamento de bases, definição do escopo temporal (mês atual/anterior)
    e cálculo de todos os KPIs necessários para a view.

    Args:
        request (HttpRequest): A requisição HTTP contendo o usuário e parâmetros GET.

    Returns:
        Dict[str, Any]: Contexto completo pronto para ser renderizado pelo Template ou consumido por gráficos.
    """
    hoje = timezone.localdate()
    escopo_mes = request.GET.get("scope", "atual")
    primeiro_dia_mes_atual = hoje.replace(day=1)

    if escopo_mes == "anterior":
        data_referencia = primeiro_dia_mes_atual - relativedelta(months=1)
    elif escopo_mes == "proximo":
        data_referencia = primeiro_dia_mes_atual + relativedelta(months=1)
    else:
        data_referencia = primeiro_dia_mes_atual
    perfil, _ = Usuario.objects.get_or_create(user=request.user)
    df_despesas, df_receitas = carregar_bases_ultimo_ano(request.user)    
    meses_ativos = obter_meses_ativos(df_despesas, data_referencia, limite=6)
    kpis = calcular_kpis_mensais(hoje, data_referencia, df_despesas, df_receitas, perfil)
    categorias_orcamento = carregar_categorias_orcamento(request.user)

    contexto = {
        "hoje": hoje,
        "data_referencia": data_referencia,
        "escopo_mes": escopo_mes,
        "perfil": perfil,
        "entradas_totais": kpis["entradas_totais"],
        "renda_fixa": kpis["renda_fixa"],
        "renda_extra": kpis["total_extra_bruto"],
        "saidas_totais": kpis["saidas_totais"],
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
        "meses_ativos": meses_ativos, 
        "data_referencia": data_referencia,
        "perfil": perfil,
    }