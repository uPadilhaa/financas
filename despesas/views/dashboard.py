import json
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import plotly.utils
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.utils import timezone
from despesas.models import Receita, Despesa, Usuario

@login_required
def dashboard(request):
    hoje = timezone.localdate()
    mes_atual = hoje.month
    ano_atual = hoje.year
    perfil, _ = Usuario.objects.get_or_create(user=request.user)
    renda_fixa = float(perfil.renda_fixa or 0)
    investimento_fixo = float(perfil.investimento_fixo or 0)
    limite_mensal_global = float(perfil.limite_mensal or 0)
    data_inicio = hoje - timezone.timedelta(days=365)
    
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
        df_d['valor'] = df_d['valor'].astype(float)        
        df_d['dia_semana'] = df_d['data'].dt.day_name()
        dias_trad = {'Monday': 'Seg', 'Tuesday': 'Ter', 'Wednesday': 'Qua', 'Thursday': 'Qui', 'Friday': 'Sex', 'Saturday': 'Sáb', 'Sunday': 'Dom'}
        df_d['dia_semana'] = df_d['dia_semana'].map(dias_trad)
    else:
        df_d = pd.DataFrame(columns=['data', 'valor', 'mes_ano', 'dia', 'categoria__nome', 'emitente_nome', 'tipo'])

    if not df_r.empty:
        df_r['data'] = pd.to_datetime(df_r['data'])
        df_r['mes_ano'] = df_r['data'].dt.strftime('%Y-%m')
        df_r['valor_bruto'] = df_r['valor_bruto'].astype(float)
        df_r['valor_investimento'] = df_r['valor_investimento'].astype(float)
    else:
        df_r = pd.DataFrame(columns=['data', 'valor_bruto', 'valor_investimento', 'mes_ano'])

    if not df_d.empty:
        df_d_atual = df_d[(df_d['data'].dt.month == mes_atual) & (df_d['data'].dt.year == ano_atual)]
    else:
        df_d_atual = pd.DataFrame()

    if not df_r.empty:
        df_r_atual = df_r[(df_r['data'].dt.month == mes_atual) & (df_r['data'].dt.year == ano_atual)]
    else:
        df_r_atual = pd.DataFrame()

    total_extra_bruto = df_r_atual['valor_bruto'].sum() if not df_r_atual.empty else 0
    total_extra_inv = df_r_atual['valor_investimento'].sum() if not df_r_atual.empty else 0
    total_gasto = df_d_atual['valor'].sum() if not df_d_atual.empty else 0

    total_disponivel = (renda_fixa + total_extra_bruto) - (investimento_fixo + total_extra_inv)
    saldo = total_disponivel - total_gasto
    
    pct_orcamento = 0
    if total_disponivel > 0:
        pct_orcamento = (total_gasto / total_disponivel * 100)

    graficos = {}

    def layout_config(fig, height=350):
        fig.update_layout(
            margin=dict(t=30, b=30, l=40, r=40),
            height=height,
            hovermode="x unified",
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            xaxis_title=None,
            yaxis_title=None
        )
        return fig

    meses_d = df_d['mes_ano'].unique() if not df_d.empty else []
    meses_r = df_r['mes_ano'].unique() if not df_r.empty else []
    all_months = sorted(list(set(meses_d) | set(meses_r)))
    
    if all_months:
        hist_data = pd.DataFrame({'mes_ano': all_months})
        
        if not df_d.empty:
            hist_desp = df_d.groupby('mes_ano')['valor'].sum().reset_index().rename(columns={'valor': 'Despesa'})
            hist_data = pd.merge(hist_data, hist_desp, on='mes_ano', how='left').fillna(0)
        else:
            hist_data['Despesa'] = 0

        if not df_r.empty:
            hist_rec = df_r.groupby('mes_ano')[['valor_bruto', 'valor_investimento']].sum().reset_index()
            hist_data = pd.merge(hist_data, hist_rec, on='mes_ano', how='left').fillna(0)
        else:
            hist_data['valor_bruto'] = 0
            hist_data['valor_investimento'] = 0
            
        hist_data['Receita'] = hist_data['valor_bruto'] + renda_fixa
        hist_data['Investimento'] = hist_data['valor_investimento'] + investimento_fixo
        
        fig_comp = px.bar(hist_data, x='mes_ano', y=['Receita', 'Despesa', 'Investimento'],
                          barmode='group', color_discrete_map={'Receita': '#198754', 'Despesa': '#dc3545', 'Investimento': '#0d6efd'})
        fig_comp.update_traces(hovertemplate='R$ %{y:.2f}')
        graficos['comparativo'] = json.dumps(layout_config(fig_comp), cls=plotly.utils.PlotlyJSONEncoder)

    if not df_d_atual.empty:
        cat_atual = df_d_atual.groupby('categoria__nome')['valor'].sum().reset_index()
        cat_atual['valor'] = cat_atual['valor'].astype(float)
        
        fig_pizza = px.pie(cat_atual, values='valor', names='categoria__nome', hole=0.5, color_discrete_sequence=px.colors.qualitative.Set2)
        fig_pizza.update_traces(textposition='inside', textinfo='percent+label', hovertemplate='%{label}: R$ %{value:.2f}')
        graficos['pizza_mes'] = json.dumps(layout_config(fig_pizza, 300), cls=plotly.utils.PlotlyJSONEncoder)

    if not df_d_atual.empty:
        df_meta = df_d_atual.sort_values('data').copy()
        df_meta = df_meta.groupby('dia')['valor'].sum().reset_index()
        df_meta['Acumulado'] = df_meta['valor'].cumsum()
        
        fig_meta = go.Figure()
        fig_meta.add_trace(go.Scatter(x=df_meta['dia'], y=df_meta['Acumulado'], mode='lines+markers', name='Gasto Real', line=dict(color='#dc3545', width=3)))
        
        if limite_mensal_global > 0:
            df_meta['Meta Ideal'] = (limite_mensal_global / 30) * df_meta['dia']
            fig_meta.add_trace(go.Scatter(x=df_meta['dia'], y=df_meta['Meta Ideal'], mode='lines', name='Ritmo Ideal', line=dict(color='green', dash='dot')))
            fig_meta.add_hline(y=limite_mensal_global, line_dash="dash", line_color="red", annotation_text="Teto")

        fig_meta.update_traces(hovertemplate='R$ %{y:.2f}')
        graficos['gasto_acumulado'] = json.dumps(layout_config(fig_meta), cls=plotly.utils.PlotlyJSONEncoder)

    if not df_d.empty:
        top5 = df_d.groupby('categoria__nome')['valor'].sum().sort_values(ascending=True).tail(5).reset_index()
        fig_top5 = px.bar(top5, x='valor', y='categoria__nome', orientation='h', text='valor', title="")
        fig_top5.update_traces(texttemplate='R$ %{text:.2f}', textposition='outside', hovertemplate='R$ %{x:.2f}')
        graficos['top5_cat'] = json.dumps(layout_config(fig_top5), cls=plotly.utils.PlotlyJSONEncoder)

    if not df_d_atual.empty and 'categoria__orcamento_mensal' in df_d_atual.columns:
        orc_real = df_d_atual.groupby('categoria__nome').agg(
            Realizado=('valor', 'sum'),
            Orcado=('categoria__orcamento_mensal', 'first')
        ).reset_index()
        orc_real['Orcado'] = orc_real['Orcado'].fillna(0).astype(float)
        
        fig_orc = go.Figure()
        fig_orc.add_trace(go.Bar(x=orc_real['categoria__nome'], y=orc_real['Orcado'], name='Orçado', marker_color='#adb5bd'))
        fig_orc.add_trace(go.Bar(x=orc_real['categoria__nome'], y=orc_real['Realizado'], name='Realizado', marker_color='#0F6DB5'))
        fig_orc.update_traces(hovertemplate='R$ %{y:.2f}')
        graficos['orcado_realizado'] = json.dumps(layout_config(fig_orc), cls=plotly.utils.PlotlyJSONEncoder)
        
    if not df_d.empty:
        pareto_df = df_d.groupby('categoria__nome')['valor'].sum().reset_index().sort_values('valor', ascending=False)
        pareto_df['accum_pct'] = pareto_df['valor'].cumsum() / pareto_df['valor'].sum() * 100
        
        fig_pareto = go.Figure()
        fig_pareto.add_trace(go.Bar(x=pareto_df['categoria__nome'], y=pareto_df['valor'], name='Valor', marker_color='#0F6DB5'))
        fig_pareto.add_trace(go.Scatter(x=pareto_df['categoria__nome'], y=pareto_df['accum_pct'], name='%', yaxis='y2', mode='lines+markers', line=dict(color='orange')))
        fig_pareto.update_layout(
            yaxis2=dict(overlaying='y', side='right', range=[0, 110], showgrid=False),
            showlegend=False
        )
        graficos['pareto'] = json.dumps(layout_config(fig_pareto), cls=plotly.utils.PlotlyJSONEncoder)

    if not df_d.empty:
        maior_cat = df_d.groupby('categoria__nome')['valor'].sum().idxmax()
        df_cat_evo = df_d[df_d['categoria__nome'] == maior_cat].groupby('mes_ano')['valor'].sum().reset_index()
        fig_evo_cat = px.line(df_cat_evo, x='mes_ano', y='valor', markers=True, title=f"Evolução: {maior_cat}")
        fig_evo_cat.update_traces(hovertemplate='R$ %{y:.2f}')
        graficos['evolucao_cat'] = json.dumps(layout_config(fig_evo_cat), cls=plotly.utils.PlotlyJSONEncoder)

    if not df_d.empty:
        dia_sem_order = ['Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb', 'Dom']
        df_sem = df_d.groupby('dia_semana')['valor'].sum().reindex(dia_sem_order).fillna(0).reset_index()
        fig_sem = px.bar(df_sem, x='dia_semana', y='valor', color='valor', color_continuous_scale='Blues')
        fig_sem.update_layout(coloraxis_showscale=False)
        graficos['dia_semana'] = json.dumps(layout_config(fig_sem), cls=plotly.utils.PlotlyJSONEncoder)

    if not df_d.empty and 'tipo' in df_d.columns:
            df_tipo = df_d.groupby('tipo')['valor'].sum().reset_index()
            fig_tipo = px.pie(df_tipo, values='valor', names='tipo', hole=0.6, color_discrete_sequence=['#0d6efd', '#ffc107'])
            fig_tipo.update_traces(textposition='inside', textinfo='percent+label', hovertemplate='%{label}: R$ %{value:.2f}')
            graficos['fixa_var'] = json.dumps(layout_config(fig_tipo, 300), cls=plotly.utils.PlotlyJSONEncoder)

    if not df_d.empty:
        df_heat = df_d.groupby(['mes_ano', 'dia'])['valor'].sum().reset_index()
        fig_heat = px.density_heatmap(df_heat, x='dia', y='mes_ano', z='valor', color_continuous_scale='Reds', nbinsx=31)
        fig_heat.update_layout(xaxis_title="Dia", yaxis_title="Mês")
        graficos['heatmap'] = json.dumps(layout_config(fig_heat), cls=plotly.utils.PlotlyJSONEncoder)

    if not df_d.empty:
        fig_box = px.box(df_d, x='categoria__nome', y='valor', color='categoria__nome')
        fig_box.update_layout(showlegend=False)
        graficos['boxplot'] = json.dumps(layout_config(fig_box), cls=plotly.utils.PlotlyJSONEncoder)

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
        "tem_renda_extra": total_extra_bruto > 0
    }

    return render(request, "dashboard.html", context)