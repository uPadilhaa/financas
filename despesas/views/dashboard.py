# despesas/views/dashboard.py

import json
from datetime import timedelta

import pandas as pd
import plotly.graph_objects as go
import plotly.utils
from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.shortcuts import render
from django.utils import timezone

from despesas.models import Receita, Despesa, Usuario, Categoria
from despesas.forms import LimitesGastosForm


def to_float(val):
    try:
        return float(val)
    except (TypeError, ValueError):
        return 0.0


@login_required
def dashboard(request):
    hoje = timezone.localdate()
    mes_atual = hoje.month
    ano_atual = hoje.year

    perfil, _ = Usuario.objects.get_or_create(user=request.user)
    renda_fixa = to_float(perfil.renda_fixa)
    investimento_fixo = to_float(perfil.investimento_fixo)

    # Último ano para histórico
    data_inicio = hoje - timedelta(days=365)

    qs_despesas = (
        Despesa.objects.filter(user=request.user, data__gte=data_inicio)
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
    df_d = pd.DataFrame(list(qs_despesas))

    qs_receitas = (
        Receita.objects.filter(user=request.user, data__gte=data_inicio)
        .values("data", "valor_bruto", "valor_investimento")
    )
    df_r = pd.DataFrame(list(qs_receitas))

    # Normaliza despesas
    if not df_d.empty:
        df_d["data"] = pd.to_datetime(df_d["data"])
        df_d["mes_ano"] = df_d["data"].dt.to_period("M").astype(str)
        df_d["dia"] = df_d["data"].dt.day
        df_d["valor"] = df_d["valor"].apply(to_float)
        df_d["dia_semana"] = df_d["data"].dt.day_name()
        dias_trad = {
            "Monday": "Seg",
            "Tuesday": "Ter",
            "Wednesday": "Qua",
            "Thursday": "Qui",
            "Friday": "Sex",
            "Saturday": "Sáb",
            "Sunday": "Dom",
        }
        df_d["dia_semana"] = df_d["dia_semana"].map(dias_trad)
    else:
        df_d = pd.DataFrame(
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

    # Normaliza receitas
    if not df_r.empty:
        df_r["data"] = pd.to_datetime(df_r["data"])
        df_r["mes_ano"] = df_r["data"].dt.to_period("M").astype(str)
        df_r["valor_bruto"] = df_r["valor_bruto"].apply(to_float)
        df_r["valor_investimento"] = df_r["valor_investimento"].apply(to_float)
    else:
        df_r = pd.DataFrame(
            columns=["data", "valor_bruto", "valor_investimento", "mes_ano"]
        )

    # Recortes do mês atual
    if not df_d.empty:
        df_d_atual = df_d[
            (df_d["data"].dt.month == mes_atual) & (df_d["data"].dt.year == ano_atual)
        ]
    else:
        df_d_atual = pd.DataFrame(columns=df_d.columns)

    if not df_r.empty:
        df_r_atual = df_r[
            (df_r["data"].dt.month == mes_atual) & (df_r["data"].dt.year == ano_atual)
        ]
    else:
        df_r_atual = pd.DataFrame(columns=df_r.columns)

    # ===== KPIs do mês =====
    total_extra_bruto = df_r_atual["valor_bruto"].sum()
    total_extra_inv = df_r_atual["valor_investimento"].sum()

    entradas_totais = renda_fixa + total_extra_bruto
    investimentos_totais = investimento_fixo + total_extra_inv
    saidas_totais = df_d_atual["valor"].sum()

    total_disponivel = entradas_totais - investimentos_totais
    saldo = total_disponivel - saidas_totais

    pct_orcamento = (saidas_totais / total_disponivel * 100) if total_disponivel > 0 else 0
    pct_orcamento_gasto = max(0, min(pct_orcamento, 100))
    pct_orcamento_livre = max(0, 100 - pct_orcamento_gasto)

    # Tendência de gastos vs mês anterior
    gasto_anterior = 0.0
    tendencia_gastos = "sem_base"
    pct_diff_gastos = 0.0

    if not df_d.empty:
        primeiro_dia_mes = hoje.replace(day=1)
        ultimo_dia_mes_passado = primeiro_dia_mes - timedelta(days=1)
        mes_passado = ultimo_dia_mes_passado.month
        ano_passado = ultimo_dia_mes_passado.year

        df_mes_passado = df_d[
            (df_d["data"].dt.month == mes_passado)
            & (df_d["data"].dt.year == ano_passado)
        ]
        gasto_anterior = df_mes_passado["valor"].sum()

        if gasto_anterior > 0:
            pct_diff_gastos = ((saidas_totais - gasto_anterior) / gasto_anterior) * 100
            if pct_diff_gastos > 3:
                tendencia_gastos = "aumento"
            elif pct_diff_gastos < -3:
                tendencia_gastos = "queda"
            else:
                tendencia_gastos = "estavel"

    # Lançamentos futuros (após hoje)
    lancamentos_futuros = (
        Despesa.objects.filter(user=request.user, data__gt=hoje).aggregate(
            total=Sum("valor")
        )["total"]
        or 0
    )

    graficos = {}

    def layout_base(fig, height=320):
        fig.update_layout(
            margin=dict(t=20, b=20, l=10, r=10),
            height=height,
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

    # ===== Evolução mensal (Entradas x Saídas x Investimentos) =====
    meses = sorted(list(set(df_d["mes_ano"].unique()) | set(df_r["mes_ano"].unique())))
    if meses:
        vals_rec, vals_desp, vals_inv = [], [], []
        for m in meses:
            d_m = df_d[df_d["mes_ano"] == m]["valor"].sum()
            r_bruto = df_r[df_r["mes_ano"] == m]["valor_bruto"].sum()
            r_inv = df_r[df_r["mes_ano"] == m]["valor_investimento"].sum()
            vals_rec.append(r_bruto + renda_fixa)
            vals_desp.append(d_m)
            vals_inv.append(r_inv + investimento_fixo)

        fig_comp = go.Figure(
            data=[
                go.Bar(
                    name="Entradas",
                    x=meses,
                    y=vals_rec,
                    marker=dict(color="#78f07e"),
                ),
                go.Bar(
                    name="Saídas",
                    x=meses,
                    y=vals_desp,
                    marker=dict(color="#dc3545"),
                ),
                go.Bar(
                    name="Investimentos",
                    x=meses,
                    y=vals_inv,
                    marker=dict(color="#4552f5"),
                ),
            ]
        )
        fig_comp.update_traces(hovertemplate="R$ %{y:.2f}<extra></extra>")
        fig_comp = layout_base(fig_comp, height=360)
        fig_comp.update_layout(barmode="group", bargap=0.35, bargroupgap=0.18)
        graficos["comparativo"] = json.dumps(
            fig_comp, cls=plotly.utils.PlotlyJSONEncoder
        )

    # ===== Donut por categoria (mês atual) – estilo 2ª imagem =====
    fig_pizza = go.Figure()
    if not df_d_atual.empty:
        cat_mensal = (
            df_d_atual.groupby("categoria__nome")["valor"]
            .sum()
            .sort_values(ascending=False)
        )
        total_mes = cat_mensal.sum()

        cores_base = ["#4552f5", "#78f07e", "#dc3545", "#f2c94c", "#9b51e0", "#00bcd4"]

        fig_pizza.add_trace(
            go.Pie(
                labels=cat_mensal.index.tolist(),
                values=cat_mensal.values.tolist(),
                hole=0.72,
                marker=dict(
                    colors=[cores_base[i % len(cores_base)] for i in range(len(cat_mensal))],
                    line=dict(color="#f3f9ff", width=5),
                ),
                sort=False,
                textinfo="none",
                hovertemplate="<b>%{label}</b><br>R$ %{value:.2f}<extra></extra>",
                showlegend=False,
            )
        )

        total_text = f"R$ {total_mes:,.2f}".replace(",", "X").replace(".", ",").replace(
            "X", "."
        )

        fig_pizza.update_layout(
            annotations=[
                dict(
                    text=total_text,
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

    graficos["pizza_mes"] = json.dumps(
        layout_base(fig_pizza, height=280), cls=plotly.utils.PlotlyJSONEncoder
    )

    # ===== Top 5 categorias do mês =====
    fig_top5 = go.Figure()
    if not df_d_atual.empty:
        top5_m = (
            df_d_atual.groupby("categoria__nome")["valor"]
            .sum()
            .sort_values(ascending=True)
            .tail(5)
        )
        fig_top5.add_trace(
            go.Bar(
                x=top5_m.values.tolist(),
                y=top5_m.index.tolist(),
                orientation="h",
                text=[f"R$ {v:.2f}" for v in top5_m.values],
                textposition="outside",
                marker=dict(color="#4552f5"),
            )
        )
        fig_top5.update_traces(
            hovertemplate="<b>%{y}</b><br>R$ %{x:.2f}<extra></extra>"
        )

    graficos["top5_cat"] = json.dumps(
        layout_base(fig_top5, height=280), cls=plotly.utils.PlotlyJSONEncoder
    )

    # ===== Orçado x realizado (mês atual) =====
    qs_cats = Categoria.objects.filter(user=request.user).values("nome", "orcamento_mensal")
    cats_dict = {c["nome"]: to_float(c["orcamento_mensal"]) for c in qs_cats}
    nomes = list(cats_dict.keys())
    vals_orcado = list(cats_dict.values())

    fig_orc = go.Figure()
    if nomes:
        real_m = (
            df_d_atual.groupby("categoria__nome")["valor"].sum().to_dict()
            if not df_d_atual.empty
            else {}
        )
        vals_real_mensal = [real_m.get(n, 0.0) for n in nomes]

        fig_orc.add_trace(
            go.Bar(
                name="Orçado",
                x=nomes,
                y=vals_orcado,
                marker=dict(color="#e5e7eb"),
            )
        )
        fig_orc.add_trace(
            go.Bar(
                name="Realizado",
                x=nomes,
                y=vals_real_mensal,
                marker=dict(color="#4552f5"),
            )
        )
        fig_orc.update_traces(hovertemplate="R$ %{y:.2f}<extra></extra>")
        fig_orc.update_layout(barmode="group", bargap=0.3, bargroupgap=0.15)

    graficos["orcado_realizado"] = json.dumps(
        layout_base(fig_orc, height=320), cls=plotly.utils.PlotlyJSONEncoder
    )

    # ===== Gastos por dia da semana (mês atual) =====
    order = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]
    fig_sem = go.Figure()
    if not df_d_atual.empty:
        sem_m = df_d_atual.groupby("dia_semana")["valor"].sum()
        vals_m = [sem_m.get(d, 0.0) for d in order]
    else:
        vals_m = [0] * len(order)

    fig_sem.add_trace(
        go.Bar(
            x=order,
            y=vals_m,
            marker=dict(color="#78f07e"),
        )
    )
    fig_sem.update_traces(
        hovertemplate="<b>%{x}</b><br>R$ %{y:.2f}<extra></extra>"
    )
    graficos["dia_semana"] = json.dumps(
        layout_base(fig_sem, height=260), cls=plotly.utils.PlotlyJSONEncoder
    )

    form_limites = LimitesGastosForm(instance=perfil)

    context = {
        "hoje": hoje,
        "perfil": perfil,
        "entradas_totais": entradas_totais,
        "renda_fixa": renda_fixa,
        "renda_extra": total_extra_bruto,
        "investimentos_totais": investimentos_totais,
        "saidas_totais": saidas_totais,
        "total_disponivel": total_disponivel,
        "saldo": saldo,
        "pct_orcamento": pct_orcamento,
        "pct_orcamento_livre": pct_orcamento_livre,
        "tendencia_gastos": tendencia_gastos,
        "pct_diff_gastos": pct_diff_gastos,
        "lancamentos_futuros": lancamentos_futuros,
        "graficos": graficos,
        "form_limites": form_limites,
    }

    return render(request, "dashboard.html", context)