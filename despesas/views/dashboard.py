import json
import pandas as pd
import plotly.graph_objects as go
import plotly.utils
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from datetime import timedelta
from despesas.models import Receita, Despesa, Usuario, Categoria
from despesas.forms import LimitesGastosForm

def to_float(val):
    try:
        return float(val)
    except (ValueError, TypeError):
        return 0.0

@login_required
def dashboard(request):
    hoje = timezone.localdate()
    mes_atual = hoje.month
    ano_atual = hoje.year
    
    perfil, _ = Usuario.objects.get_or_create(user=request.user)
    renda_fixa = to_float(perfil.renda_fixa)
    investimento_fixo = to_float(perfil.investimento_fixo)
    
    data_inicio = hoje - timedelta(days=365)
    
    qs_despesas = Despesa.objects.filter(user=request.user, data__gte=data_inicio).values(
        'data', 'valor', 'categoria__nome', 'categoria__orcamento_mensal', 'tipo', 'emitente_nome'
    )
    df_d = pd.DataFrame(list(qs_despesas))

    qs_receitas = Receita.objects.filter(user=request.user, data__gte=data_inicio).values(
        'data', 'valor_bruto', 'valor_investimento'
    )
    df_r = pd.DataFrame(list(qs_receitas))

    if not df_d.empty:
        df_d['data'] = pd.to_datetime(df_d['data'])
        df_d['mes_ano'] = df_d['data'].dt.strftime('%Y-%m')
        df_d['dia'] = df_d['data'].dt.day
        df_d['valor'] = df_d['valor'].apply(to_float)
        df_d['dia_semana'] = df_d['data'].dt.day_name()
        dias_trad = {'Monday': 'Seg', 'Tuesday': 'Ter', 'Wednesday': 'Qua', 'Thursday': 'Qui', 'Friday': 'Sex', 'Saturday': 'Sáb', 'Sunday': 'Dom'}
        df_d['dia_semana'] = df_d['dia_semana'].map(dias_trad)
    else:
        df_d = pd.DataFrame(columns=['data', 'valor', 'mes_ano', 'dia', 'categoria__nome', 'emitente_nome', 'tipo'])

    if not df_r.empty:
        df_r['data'] = pd.to_datetime(df_r['data'])
        df_r['mes_ano'] = df_r['data'].dt.strftime('%Y-%m')
        df_r['valor_bruto'] = df_r['valor_bruto'].apply(to_float)
        df_r['valor_investimento'] = df_r['valor_investimento'].apply(to_float)
    else:
        df_r = pd.DataFrame(columns=['data', 'valor_bruto', 'valor_investimento', 'mes_ano'])

    if not df_d.empty:
        df_d_atual = df_d[(df_d['data'].dt.month == mes_atual) & (df_d['data'].dt.year == ano_atual)]
    else:
        df_d_atual = pd.DataFrame(columns=df_d.columns)

    if not df_r.empty:
        df_r_atual = df_r[(df_r['data'].dt.month == mes_atual) & (df_r['data'].dt.year == ano_atual)]
    else:
        df_r_atual = pd.DataFrame(columns=df_r.columns)

    total_extra_bruto = df_r_atual['valor_bruto'].sum()
    total_extra_inv = df_r_atual['valor_investimento'].sum()
    total_gasto = df_d_atual['valor'].sum()
    total_disponivel = (renda_fixa + total_extra_bruto) - (investimento_fixo + total_extra_inv)
    saldo = total_disponivel - total_gasto
    pct_orcamento = (total_gasto / total_disponivel * 100) if total_disponivel > 0 else 0

    graficos = {}

    def layout_base(fig, height=350):
        fig.update_layout(
            margin=dict(t=10, b=10, l=10, r=10), 
            height=height,
            autosize=True,
            hovermode="x unified",
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            xaxis=dict(title=None, fixedrange=True, automargin=True),
            yaxis=dict(title=None, fixedrange=True, automargin=True),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        return fig

    fig_pizza = go.Figure()
    if not df_d.empty:
        cat_global = df_d.groupby('categoria__nome')['valor'].sum()
        fig_pizza.add_trace(go.Pie(labels=cat_global.index.tolist(), values=cat_global.values.tolist(), hole=0.6, name='Global', visible=False))
    else:
        fig_pizza.add_trace(go.Pie(labels=[], values=[], hole=0.6, visible=False))

    if not df_d_atual.empty:
        cat_mensal = df_d_atual.groupby('categoria__nome')['valor'].sum()
        fig_pizza.add_trace(go.Pie(labels=cat_mensal.index.tolist(), values=cat_mensal.values.tolist(), hole=0.6, name='Mês Atual'))
    else:
        fig_pizza.add_trace(go.Pie(labels=[], values=[], hole=0.6))

    fig_pizza.update_traces(textposition='inside', textinfo='percent', hovertemplate='<b>%{label}</b><br>R$ %{value:.2f}<extra></extra>')
    graficos['pizza_mes'] = json.dumps(layout_base(fig_pizza, 300), cls=plotly.utils.PlotlyJSONEncoder)

    meses = sorted(list(set(df_d['mes_ano'].unique()) | set(df_r['mes_ano'].unique())))
    if meses:
        vals_rec, vals_desp, vals_inv = [], [], []
        for m in meses:
            d_m = df_d[df_d['mes_ano'] == m]['valor'].sum()
            r_bruto = df_r[df_r['mes_ano'] == m]['valor_bruto'].sum()
            r_inv = df_r[df_r['mes_ano'] == m]['valor_investimento'].sum()
            vals_rec.append(r_bruto + renda_fixa)
            vals_desp.append(d_m)
            vals_inv.append(r_inv + investimento_fixo)
        fig_comp = go.Figure(data=[
            go.Bar(name='Receita', x=meses, y=vals_rec, marker_color='#198754'),
            go.Bar(name='Despesa', x=meses, y=vals_desp, marker_color='#dc3545'),
            go.Bar(name='Investimento', x=meses, y=vals_inv, marker_color='#0d6efd')
        ])
        fig_comp.update_traces(hovertemplate='R$ %{y:.2f}<extra></extra>')
        graficos['comparativo'] = json.dumps(layout_base(fig_comp), cls=plotly.utils.PlotlyJSONEncoder)

    fig_top5 = go.Figure()
    
    top5_g = df_d.groupby('categoria__nome')['valor'].sum().sort_values(ascending=True).tail(5) if not df_d.empty else pd.Series()
    max_g = top5_g.max() if not top5_g.empty else 0
    
    top5_m = df_d_atual.groupby('categoria__nome')['valor'].sum().sort_values(ascending=True).tail(5) if not df_d_atual.empty else pd.Series()
    max_m = top5_m.max() if not top5_m.empty else 0

    fig_top5.add_trace(go.Bar(x=top5_g.values.tolist(), y=top5_g.index.tolist(), orientation='h', text=[f"R$ {v:.2f}" for v in top5_g.values], textposition='outside', marker_color='#0d6efd', visible=False))
    fig_top5.add_trace(go.Bar(x=top5_m.values.tolist(), y=top5_m.index.tolist(), orientation='h', text=[f"R$ {v:.2f}" for v in top5_m.values], textposition='outside', marker_color='#198754'))

    fig_top5.update_traces(hovertemplate='<b>%{y}</b><br>R$ %{x:.2f}<extra></extra>')
    layout_t5 = layout_base(fig_top5)
    layout_t5.update_layout(xaxis=dict(range=[0, max_m * 1.25], showticklabels=False, fixedrange=True))
    graficos['top5_cat'] = json.dumps(layout_t5, cls=plotly.utils.PlotlyJSONEncoder)

    qs_cats = Categoria.objects.filter(user=request.user).values('nome', 'orcamento_mensal')
    cats_dict = {c['nome']: to_float(c['orcamento_mensal']) for c in qs_cats}
    nomes = list(cats_dict.keys())
    vals_orcado = list(cats_dict.values()) 
    
    fig_orc = go.Figure()
    if cats_dict:
        real_g = df_d.groupby('categoria__nome')['valor'].sum().to_dict() if not df_d.empty else {}
        real_m = df_d_atual.groupby('categoria__nome')['valor'].sum().to_dict() if not df_d_atual.empty else {}
        num_meses = len(df_d['mes_ano'].unique()) if not df_d.empty else 1
        vals_orcado_global = [v * num_meses for v in vals_orcado]
        vals_real_global = [real_g.get(n, 0.0) for n in nomes]
        vals_real_mensal = [real_m.get(n, 0.0) for n in nomes]

        fig_orc.add_trace(go.Bar(name='Orçado (Total)', x=nomes, y=vals_orcado_global, marker_color='#adb5bd', visible=False))
        fig_orc.add_trace(go.Bar(name='Realizado', x=nomes, y=vals_real_global, marker_color='#0F6DB5', visible=False))
        fig_orc.add_trace(go.Bar(name='Orçado', x=nomes, y=vals_orcado, marker_color='#adb5bd'))
        fig_orc.add_trace(go.Bar(name='Realizado', x=nomes, y=vals_real_mensal, marker_color='#0F6DB5'))

    fig_orc.update_traces(hovertemplate='R$ %{y:.2f}<extra></extra>')
    graficos['orcado_realizado'] = json.dumps(layout_base(fig_orc), cls=plotly.utils.PlotlyJSONEncoder)

    order = ['Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb', 'Dom']
    fig_sem = go.Figure()    
    sem_g = df_d.groupby('dia_semana')['valor'].sum() if not df_d.empty else {}
    vals_g = [sem_g.get(d, 0.0) for d in order]
    fig_sem.add_trace(go.Bar(x=order, y=vals_g, marker_color='#0d6efd', visible=False))    
    sem_m = df_d_atual.groupby('dia_semana')['valor'].sum() if not df_d_atual.empty else {}
    vals_m = [sem_m.get(d, 0.0) for d in order]
    fig_sem.add_trace(go.Bar(x=order, y=vals_m, marker_color='#198754'))

    fig_sem.update_traces(hovertemplate='<b>%{x}</b><br>R$ %{y:.2f}<extra></extra>')
    graficos['dia_semana'] = json.dumps(layout_base(fig_sem), cls=plotly.utils.PlotlyJSONEncoder)
    fig_fixa = go.Figure()

    if not df_d.empty and 'tipo' in df_d.columns:
        tipo_g = df_d.groupby('tipo')['valor'].sum()
        fig_fixa.add_trace(go.Pie(labels=tipo_g.index.tolist(), values=tipo_g.values.tolist(), hole=0.6, visible=False))
    else:
        fig_fixa.add_trace(go.Pie(visible=False))
        
    if not df_d_atual.empty and 'tipo' in df_d_atual.columns:
        tipo_m = df_d_atual.groupby('tipo')['valor'].sum()
        fig_fixa.add_trace(go.Pie(labels=tipo_m.index.tolist(), values=tipo_m.values.tolist(), hole=0.6))
    else:
        fig_fixa.add_trace(go.Pie())

    fig_fixa.update_traces(textposition='inside', textinfo='percent', hovertemplate='<b>%{label}</b><br>R$ %{value:.2f}<extra></extra>')
    graficos['fixa_var'] = json.dumps(layout_base(fig_fixa, 300), cls=plotly.utils.PlotlyJSONEncoder)

    form_limites = LimitesGastosForm(instance=perfil)

    context = {
        "mes_atual": hoje,
        "perfil": perfil,
        "total_disponivel": total_disponivel,
        "total_gasto": total_gasto,
        "saldo": saldo,
        "pct_orcamento": pct_orcamento,
        "graficos": graficos,
        "total_bruto": renda_fixa + total_extra_bruto,
        "extra_bruto": total_extra_bruto,
        "total_investido": investimento_fixo + total_extra_inv,
        "tem_renda_extra": total_extra_bruto > 0,
        "form_limites": form_limites, # Adicione ao contexto
    }

    return render(request, "dashboard.html", context)