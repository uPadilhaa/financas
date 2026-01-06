import json
from typing import Dict, Any, List
import pandas as pd
import plotly.graph_objects as go
import plotly.utils
from despesas.services.dashboard_dados import to_float
from despesas.models import Categoria


MAPA_MESES = {
    1: "Jan",
    2: "Fev",
    3: "Mar",
    4: "Abr",
    5: "Mai",
    6: "Jun",
    7: "Jul",
    8: "Ago",
    9: "Set",
    10: "Out",
    11: "Nov",
    12: "Dez",
}


def layout_base(fig: go.Figure, altura: int = 320) -> go.Figure:
    """Layout padrão para todos os gráficos do dashboard."""
    fig.update_layout(
        margin=dict(t=20, b=20, l=10, r=60),
        height=altura,
        autosize=True,
        hovermode="x unified",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(
            family='Orev Edge, system-ui, -apple-system, "Segoe UI", sans-serif',
            size=12,
            color="#111827",
        ),
        xaxis=dict(
            title=None,
            fixedrange=True,
            automargin=True,
            showgrid=False,
        ),
        yaxis=dict(
            title=None,
            fixedrange=True,
            automargin=True,
            gridcolor="rgba(148, 163, 184, 0.18)",
            zeroline=False,
        ),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
            bgcolor="rgba(255,255,255,0.7)",
            borderwidth=0,
        ),
    )
    return fig


def _formatar_moeda(valor: float) -> str:
    """Formata número float em string moeda estilo brasileiro."""
    return (
        f"R$ {valor:,.2f}"
        .replace(",", "X")
        .replace(".", ",")
        .replace("X", ".")
    )


def montar_grafico_evolucao_despesas(dados: Dict[str, Any]) -> str:
    """Gráfico de linha com evolução das despesas (6m / 1y / futuro)."""
    df_despesas = dados["df_despesas"]
    intervalo = dados["intervalo"]
    data_referencia = dados["data_referencia"]
    hoje = dados["hoje"]

    figura = go.Figure()

    if df_despesas.empty:
        figura = layout_base(figura, altura=360)
        return json.dumps(figura, cls=plotly.utils.PlotlyJSONEncoder)

    if intervalo in ("6m", "12m"):
        quantidade_meses = 6 if intervalo == "6m" else 12

        ts_ref = pd.Timestamp(data_referencia)
        primeiro_mes = (ts_ref - pd.DateOffset(months=quantidade_meses - 1)).replace(
            day=1
        )
        proximo_mes = (ts_ref + pd.DateOffset(months=1)).replace(day=1)

        df_intervalo = df_despesas[
            (df_despesas["data"] >= primeiro_mes)
            & (df_despesas["data"] < proximo_mes)
        ]
    else:  
        df_intervalo = df_despesas[df_despesas["data"] > pd.to_datetime(hoje)]

    if df_intervalo.empty:
        figura = layout_base(figura, altura=360)
        return json.dumps(figura, cls=plotly.utils.PlotlyJSONEncoder)

    serie = (
        df_intervalo.groupby(df_intervalo["data"].dt.to_period("M"))["valor"]
        .sum()
        .sort_index()
    )

    idx = serie.index.to_timestamp()
    rotulos_x = [f"{MAPA_MESES[d.month]}/{str(d.year)[2:]}" for d in idx]
    valores_y = serie.values.tolist()

    figura.add_trace(
        go.Scatter(
            x=rotulos_x,
            y=valores_y,
            mode="lines+markers",
            name="Despesas",
            line=dict(width=3, color="#dc3545"),
            fill="tozeroy",
            fillcolor="rgba(220, 53, 69, 0.12)",
            hovertemplate="R$ %{y:.2f}<extra></extra>",
        )
    )

    figura = layout_base(figura, altura=360)
    return json.dumps(figura, cls=plotly.utils.PlotlyJSONEncoder)


def montar_grafico_pizza_categorias(df_despesas_mes) -> str:
    """Pizza (donut) de distribuição de despesas por categoria no mês selecionado."""
    figura = go.Figure()

    if df_despesas_mes.empty:
        figura = layout_base(figura, altura=280)
        return json.dumps(figura, cls=plotly.utils.PlotlyJSONEncoder)

    serie_categoria = (
        df_despesas_mes.groupby("categoria__nome")["valor"]
        .sum()
        .sort_values(ascending=False)
    )
    total_mes = serie_categoria.sum()

    cores_base = ["#4552f5", "#78f07e", "#dc3545", "#f2c94c", "#9b51e0", "#00bcd4"]

    figura.add_trace(
        go.Pie(
            labels=serie_categoria.index.tolist(),
            values=serie_categoria.values.tolist(),
            hole=0.72,
            marker=dict(
                colors=[
                    cores_base[i % len(cores_base)]
                    for i in range(len(serie_categoria))
                ],
                line=dict(color="#f3f9ff", width=5),
            ),
            sort=False,
            textinfo="none",
            hovertemplate="<b>%{label}</b><br>R$ %{value:.2f}<extra></extra>",
            showlegend=False,
        )
    )

    texto_total = _formatar_moeda(total_mes)

    figura.update_layout(
        annotations=[
            dict(
                text=texto_total,
                x=0.5,
                y=0.52,
                showarrow=False,
                font=dict(
                    size=16,
                    family='Orev Edge, system-ui, -apple-system, "Segoe UI", sans-serif',
                    color="#111827",
                ),
            ),
            dict(
                text="Gastos do mês",
                x=0.5,
                y=0.34,
                showarrow=False,
                font=dict(size=11, color="#6b7280"),
            ),
        ]
    )

    figura = layout_base(figura, altura=280)
    return json.dumps(figura, cls=plotly.utils.PlotlyJSONEncoder)


def montar_grafico_top5_despesas(df_despesas) -> str:
    """Top 5 maiores gastos por categoria (últimos 12 meses)."""
    figura = go.Figure()

    if df_despesas.empty:
        figura = layout_base(figura, altura=280)
        return json.dumps(figura, cls=plotly.utils.PlotlyJSONEncoder)

    top5 = (
        df_despesas.groupby("categoria__nome")["valor"]
        .sum()
        .sort_values(ascending=True)
        .tail(5)
    )

    figura.add_trace(
        go.Bar(
            x=top5.values.tolist(),
            y=top5.index.tolist(),
            orientation="h",
            text=[_formatar_moeda(v) for v in top5.values],
            textposition="outside",
            marker=dict(color="#4552f5"),
            cliponaxis=False,
        )
    )
    figura.update_traces(
        hovertemplate="<b>%{y}</b><br>R$ %{x:.2f}<extra></extra>"
    )

    figura = layout_base(figura, altura=280)
    return json.dumps(figura, cls=plotly.utils.PlotlyJSONEncoder)


def montar_grafico_orcado_realizado(usuario, df_despesas_mes) -> str:
    """Gráfico de barras Orçado x Realizado por categoria (mês)."""
    figura = go.Figure()

    categorias = Categoria.objects.filter(user=usuario).values(
        "nome", "orcamento_mensal"
    )
    nomes: List[str] = [c["nome"] for c in categorias]
    valores_orcados: List[float] = [
        float(c["orcamento_mensal"] or 0) for c in categorias
    ]

    if not nomes:
        figura = layout_base(figura, altura=320)
        return json.dumps(figura, cls=plotly.utils.PlotlyJSONEncoder)

    if not df_despesas_mes.empty:
        gastos_por_cat = df_despesas_mes.groupby("categoria__nome")["valor"].sum()
        valores_realizados = [float(gastos_por_cat.get(n, 0.0)) for n in nomes]
    else:
        valores_realizados = [0.0 for _ in nomes]

    figura.add_trace(
        go.Bar(
            name="Orçado",
            x=nomes,
            y=valores_orcados,
            marker=dict(color="#e5e7eb"),
        )
    )
    figura.add_trace(
        go.Bar(
            name="Realizado",
            x=nomes,
            y=valores_realizados,
            marker=dict(color="#4552f5"),
        )
    )

    figura.update_traces(hovertemplate="R$ %{y:.2f}<extra></extra>")
    figura.update_layout(barmode="group", bargap=0.3, bargroupgap=0.15)

    figura = layout_base(figura, altura=320)
    return json.dumps(figura, cls=plotly.utils.PlotlyJSONEncoder)


def montar_grafico_investimentos_vs_despesas(dados: Dict[str, Any]) -> str:
    """
    Gráfico em barras empilhadas com % de investimentos x despesas
    nos últimos 6 meses (sempre relativos ao mês em vigência),
    com o valor TOTAL (R$) acima de cada grupo.

    Aqui somamos:
      - investimento (perfil) + valor_investimento das receitas
      para cada mês da janela.
    """
    df_despesas = dados["df_despesas"]
    df_receitas = dados["df_receitas"]
    data_referencia = dados["data_referencia"]
    perfil = dados["perfil"]
    investimento_fixo = to_float(getattr(perfil, "investimento_fixo", 0))
    figura = go.Figure()
    if df_despesas.empty and df_receitas.empty and investimento_fixo == 0:
        figura = layout_base(figura, altura=320)
        return json.dumps(figura, cls=plotly.utils.PlotlyJSONEncoder)

    ts_ref = pd.Timestamp(data_referencia.replace(day=1))
    corte_12m = ts_ref - pd.DateOffset(months=11)

    if not df_despesas.empty:
        df_d_12 = df_despesas[df_despesas["data"] >= corte_12m].copy()
        df_d_12["data"] = pd.to_datetime(df_d_12["data"])
    else:
        df_d_12 = df_despesas.copy()

    if not df_receitas.empty:
        df_r_12 = df_receitas[df_receitas["data"] >= corte_12m].copy()
        df_r_12["data"] = pd.to_datetime(df_r_12["data"])
    else:
        df_r_12 = df_receitas.copy()

    rotulos = []
    perc_investimentos = []
    perc_despesas = []
    totais_reais = []

    for i in range(5, -1, -1):
        ts_mes = ts_ref - pd.DateOffset(months=i)
        dt_mes = ts_mes.to_pydatetime()
        mes = dt_mes.month
        ano = dt_mes.year
        if not df_d_12.empty:
            mascara_d = (df_d_12["data"].dt.month == mes) & (
                df_d_12["data"].dt.year == ano
            )
            valor_d = float(df_d_12.loc[mascara_d, "valor"].sum())
        else:
            valor_d = 0.0

        if not df_r_12.empty:
            mascara_r = (df_r_12["data"].dt.month == mes) & (
                df_r_12["data"].dt.year == ano
            )
            valor_i_variavel = float(
                df_r_12.loc[mascara_r, "valor_investimento"].sum()
            )
        else:
            valor_i_variavel = 0.0

        valor_i = valor_i_variavel + investimento_fixo

        total = valor_d + valor_i
        totais_reais.append(total)

        if total > 0:
            p_d = valor_d / total * 100
            p_i = valor_i / total * 100
        else:
            p_d = p_i = 0.0

        perc_despesas.append(p_d)
        perc_investimentos.append(p_i)
        rotulos.append(f"{MAPA_MESES[mes]}/{str(ano)[2:]}")

    if rotulos:
        figura.add_trace(
            go.Bar(
                name="Investimentos",
                x=rotulos,
                y=perc_investimentos,
                marker=dict(color="#4552f5"),
                hovertemplate="Investimentos<br>%{y:.1f}%<extra></extra>",
            )
        )
        figura.add_trace(
            go.Bar(
                name="Despesas",
                x=rotulos,
                y=perc_despesas,
                marker=dict(color="#dc3545"),
                hovertemplate="Despesas<br>%{y:.1f}%<extra></extra>",
            )
        )

        figura.update_layout(barmode="stack")
        figura.update_yaxes(range=[0, 120], ticksuffix="%", dtick=20)
        for x, total in zip(rotulos, totais_reais):
            figura.add_annotation(
                x=x,
                y=104,
                text=_formatar_moeda(total),
                showarrow=False,
                yanchor="bottom",
                font=dict(size=11, color="#374151"),
            )

    figura = layout_base(figura, altura=320)
    return json.dumps(figura, cls=plotly.utils.PlotlyJSONEncoder)



def montar_graficos_dashboard(dados: Dict[str, Any]) -> Dict[str, str]:
    """
    Função orquestradora usada pela view.
    Retorna um dicionário com todos os gráficos serializados como JSON.
    """
    df_despesas_mes = dados["df_despesas_mes"]

    graficos: Dict[str, str] = {}

    graficos["evolucao_despesas"] = montar_grafico_evolucao_despesas(dados)
    graficos["pizza_mes"] = montar_grafico_pizza_categorias(df_despesas_mes)
    graficos["top5_cat"] = montar_grafico_top5_despesas(dados["df_despesas"])
    graficos["orcado_realizado"] = montar_grafico_orcado_realizado(
        usuario=dados["perfil"].user,
        df_despesas_mes=df_despesas_mes,
    )
    graficos["invest_despesas_pct"] = montar_grafico_investimentos_vs_despesas(dados)

    return graficos
