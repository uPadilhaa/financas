import json
from typing import Dict, Any, List
import pandas as pd
import plotly.graph_objects as go
import plotly.utils
from despesas.services.dashboard_dados import to_float
from despesas.models import Categoria

MAPA_MESES = {
    1: "Jan", 2: "Fev", 3: "Mar", 4: "Abr", 5: "Mai", 6: "Jun",
    7: "Jul", 8: "Ago", 9: "Set", 10: "Out", 11: "Nov", 12: "Dez",
}

def _formatar_moeda(valor: float) -> str:
    """Formata float para string de moeda brasileira (R$ 1.234,56)."""
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def layout_base(fig: go.Figure, altura: int = 320) -> go.Figure:
    """
    Layout padrão 'Clean UI' aplicado a todos os gráficos.
    Define fontes, cores, remoção de grids excessivos e comportamento responsivo.
    """
    fig.update_layout(
        margin=dict(t=30, b=30, l=20, r=20),
        height=altura,
        autosize=True,
        hovermode="x unified",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(
            family='Inter, system-ui, -apple-system, "Segoe UI", sans-serif',
            size=12,
            color="#64748b"
        ),
        xaxis=dict(
            showgrid=False,
            showline=True,
            linecolor="#e2e8f0",
            type='category',
            tickfont=dict(color="#64748b")
        ),
        yaxis=dict(
            showgrid=True,
            gridcolor="#f1f5f9",
            zeroline=False,
            showticklabels=False, 
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


def montar_grafico_evolucao_despesas(dados: Dict[str, Any]) -> str:
    """
    Gráfico de Área (Spline) mostrando a evolução das despesas.
    Utiliza a lista 'meses_ativos' para plotar apenas meses com dados relevantes.
    """
    df_despesas = dados["df_despesas"]
    meses_ativos = dados.get("meses_ativos", [])    
    figura = go.Figure()
    if not meses_ativos or df_despesas.empty:
        figura = layout_base(figura, altura=340)
        figura.add_annotation(
            text="Sem movimentação recente", 
            showarrow=False, 
            font=dict(size=14, color="#94a3b8")
        )
        return json.dumps(figura, cls=plotly.utils.PlotlyJSONEncoder)

    rotulos = []
    valores = []
    for dt_mes in meses_ativos:
        mes, ano = dt_mes.month, dt_mes.year
        rotulos.append(f"{MAPA_MESES[mes]}/{str(ano)[2:]}")        
        if "periodo_dt" in df_despesas.columns:
            mask = (df_despesas["periodo_dt"] == dt_mes)
            val = df_despesas.loc[mask, "valor"].sum()
        else:
            mask = (df_despesas["data"].dt.month == mes) & (df_despesas["data"].dt.year == ano)
            val = df_despesas.loc[mask, "valor"].sum()
            
        valores.append(float(val))

    line_shape = "spline" 
    marker_size = 8
    
    if len(valores) == 1:
        line_shape = "linear"
        marker_size = 12 

    figura.add_trace(go.Scatter(
        x=rotulos,
        y=valores,
        mode="lines+markers",
        name="Gastos",
        line=dict(width=3, color="#3b82f6", shape=line_shape),
        marker=dict(
            size=marker_size, 
            color="#2563eb", 
            line=dict(width=2, color="white")
        ),
        fill="tozeroy",
        fillcolor="rgba(59, 130, 246, 0.1)",
        hovertemplate="<b>%{x}</b><br>R$ %{y:.2f}<extra></extra>"
    ))

    figura = layout_base(figura, altura=340)
    figura.update_yaxes(rangemode="tozero") 
    return json.dumps(figura, cls=plotly.utils.PlotlyJSONEncoder)


def montar_grafico_entradas_vs_saidas(dados: Dict[str, Any]) -> str:
    """
    Gráfico de Barras comparando Entradas (Renda Fixa + Variável) vs Saídas.
    Substitui o antigo gráfico de Investimentos.
    """
    df_despesas = dados["df_despesas"]
    df_receitas = dados["df_receitas"]
    meses_ativos = dados.get("meses_ativos", [])
    renda_fixa = to_float(dados["perfil"].renda_fixa)
    figura = go.Figure()    
    if not meses_ativos:
        figura = layout_base(figura, altura=320)
        return json.dumps(figura, cls=plotly.utils.PlotlyJSONEncoder)

    rotulos = []
    val_entradas = []
    val_saidas = []

    for dt_mes in meses_ativos:
        mes, ano = dt_mes.month, dt_mes.year
        rotulos.append(f"{MAPA_MESES[mes]}/{str(ano)[2:]}")
        v_out = 0.0
        if not df_despesas.empty:
            if "periodo_dt" in df_despesas.columns:
                mask_d = (df_despesas["periodo_dt"] == dt_mes)
            else:
                mask_d = (df_despesas["data"].dt.month == mes) & (df_despesas["data"].dt.year == ano)
            v_out = df_despesas.loc[mask_d, "valor"].sum()
        
        v_in_var = 0.0
        if not df_receitas.empty:
            if "periodo_dt" in df_receitas.columns:
                mask_r = (df_receitas["periodo_dt"] == dt_mes)
            else:
                mask_r = (df_receitas["data"].dt.month == mes) & (df_receitas["data"].dt.year == ano)
            v_in_var = df_receitas.loc[mask_r, "valor_bruto"].sum()
            
        val_saidas.append(float(v_out))
        val_entradas.append(float(v_in_var + renda_fixa))

    figura.add_trace(go.Bar(
        name="Entradas", 
        x=rotulos, 
        y=val_entradas,
        marker=dict(color="#10b981", line=dict(width=0)),
        hovertemplate="Entradas<br><b>%{x}</b><br>R$ %{y:.2f}<extra></extra>"
    ))
    
    figura.add_trace(go.Bar(
        name="Saídas", 
        x=rotulos, 
        y=val_saidas,
        marker=dict(color="#ef4444", line=dict(width=0)),
        hovertemplate="Saídas<br><b>%{x}</b><br>R$ %{y:.2f}<extra></extra>"
    ))

    figura.update_layout(barmode='group', bargap=0.3)
    figura = layout_base(figura, altura=320)
    return json.dumps(figura, cls=plotly.utils.PlotlyJSONEncoder)


def montar_grafico_pizza_categorias(df_despesas_mes) -> str:
    """Gráfico de Donut: Distribuição de gastos do mês por categoria."""
    figura = go.Figure()
    if df_despesas_mes.empty:
        figura = layout_base(figura, altura=280)
        figura.add_shape(type="circle", x0=0.4, y0=0.4, x1=0.6, y1=0.6, line_color="#e2e8f0")
        return json.dumps(figura, cls=plotly.utils.PlotlyJSONEncoder)

    serie = df_despesas_mes.groupby("categoria__nome")["valor"].sum().sort_values(ascending=False)    
    cores = [
        "#10b981", "#3b82f6", "#f59e0b", "#f43f5e", "#8b5cf6", 
        "#06b6d4", "#84cc16", "#d946ef", "#64748b", "#f97316", 
        "#14b8a6", "#ec4899", "#6366f1", "#eab308", "#a855f7"
    ]

    figura.add_trace(go.Pie(
        labels=serie.index.tolist(), 
        values=serie.values.tolist(),
        hole=0.65, 
        marker=dict(
            colors=cores, 
            line=dict(color="#ffffff", width=2)
        ),
        textinfo="none", 
        hovertemplate="<b>%{label}</b><br>R$ %{value:.2f}<br>(%{percent})<extra></extra>",
        sort=False
    ))
    
    texto_centro = _formatar_moeda(serie.sum())
    figura.update_layout(
        annotations=[dict(
            text=texto_centro, 
            x=0.5, y=0.5, 
            showarrow=False, 
            font=dict(size=14, color="#1e293b", weight="bold")
        )]
    )

    figura = layout_base(figura, altura=280)
    return json.dumps(figura, cls=plotly.utils.PlotlyJSONEncoder)


def montar_grafico_top5_despesas(df_despesas) -> str:
    """Gráfico de Barras Horizontais: Top 5 categorias com mais gastos."""
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

    figura.add_trace(go.Bar(
        x=top5.values.tolist(),
        y=top5.index.tolist(),
        orientation="h",
        text=[_formatar_moeda(v) for v in top5.values],
        textposition="outside",
        marker=dict(color="#3b82f6", line=dict(width=0)),
        cliponaxis=False,
    ))
    
    figura.update_traces(
        hovertemplate="<b>%{y}</b><br>R$ %{x:.2f}<extra></extra>"
    )

    figura = layout_base(figura, altura=280)
    return json.dumps(figura, cls=plotly.utils.PlotlyJSONEncoder)


def montar_grafico_orcado_realizado(usuario, df_despesas_mes) -> str:
    """Gráfico de Barras Agrupadas: Orçado vs Realizado."""
    figura = go.Figure()

    categorias = Categoria.objects.filter(user=usuario).values("nome", "orcamento_mensal")
    nomes = [c["nome"] for c in categorias]
    valores_orcados = [float(c["orcamento_mensal"] or 0) for c in categorias]

    if not nomes:
        figura = layout_base(figura, altura=320)
        return json.dumps(figura, cls=plotly.utils.PlotlyJSONEncoder)

    valores_realizados = []
    if not df_despesas_mes.empty:
        gastos_por_cat = df_despesas_mes.groupby("categoria__nome")["valor"].sum()
        valores_realizados = [float(gastos_por_cat.get(n, 0.0)) for n in nomes]
    else:
        valores_realizados = [0.0 for _ in nomes]

    figura.add_trace(go.Bar(
        name="Orçado",
        x=nomes,
        y=valores_orcados,
        marker=dict(color="#cbd5e1"),
        hovertemplate="Orçado: R$ %{y:.2f}<extra></extra>"
    ))
    
    figura.add_trace(go.Bar(
        name="Realizado",
        x=nomes,
        y=valores_realizados,
        marker=dict(color="#3b82f6"),
        hovertemplate="Realizado: R$ %{y:.2f}<extra></extra>"
    ))

    figura.update_layout(barmode="group", bargap=0.3, bargroupgap=0.1)
    figura = layout_base(figura, altura=320)
    return json.dumps(figura, cls=plotly.utils.PlotlyJSONEncoder)

def montar_graficos_dashboard(dados: Dict[str, Any]) -> Dict[str, str]:
    """
    Função principal que gera todos os gráficos e retorna um dicionário de JSONs.
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
    
    graficos["entradas_vs_saidas"] = montar_grafico_entradas_vs_saidas(dados)

    return graficos