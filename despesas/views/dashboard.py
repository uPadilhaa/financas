import json
import pandas as pd
import plotly.express as px
import plotly.utils
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.utils import timezone
from despesas.models import Receita, Despesa

@login_required
def dashboard(request):
    hoje = timezone.localdate()
    mes_atual = hoje.month
    ano_atual = hoje.year
    receitas_mes = Receita.objects.filter(user=request.user, data__month=mes_atual, data__year=ano_atual)
    despesas_mes = Despesa.objects.filter(user=request.user, data__month=mes_atual, data__year=ano_atual)
    total_bruto = receitas_mes.aggregate(Sum('valor_bruto'))['valor_bruto__sum'] or 0
    total_investido = receitas_mes.aggregate(Sum('valor_investimento'))['valor_investimento__sum'] or 0
    perfil = request.user.perfil
    renda_fixa = perfil.renda_fixa or 0
    investimento_fixo = perfil.investimento_fixo or 0
    total_disponivel = (renda_fixa + total_bruto) - (investimento_fixo + total_investido)
    total_gasto = despesas_mes.aggregate(Sum('valor'))['valor__sum'] or 0
    saldo = total_disponivel - total_gasto
    qs_despesas = Despesa.objects.filter(user=request.user).values('data', 'valor', 'categoria__nome', 'emitente_nome')
    df = pd.DataFrame(list(qs_despesas))

    graficos_json = {}

    if not df.empty:
        df['data'] = pd.to_datetime(df['data'])
        df['mes_ano'] = df['data'].dt.strftime('%Y-%m') 
        
        df_atual = df[
            (df['data'].dt.month == mes_atual) & 
            (df['data'].dt.year == ano_atual)
        ]
        
        if not df_atual.empty:
            # Agrupa os dados
            df_agrupado = df_atual.groupby('categoria__nome')['valor'].sum().reset_index()
            
            # Cria gráfico de barras
            fig_bar_mes = px.bar(
                df_agrupado, 
                x='categoria__nome', 
                y='valor', 
                title='', 
                text_auto='.2s',
                color='categoria__nome' # Opcional: cores diferentes por categoria
            )
            
            fig_bar_mes.update_layout(
                margin=dict(t=20, b=20, l=20, r=20), 
                height=300,
                xaxis_title=None, # Remove label X para limpar
                yaxis_title="Valor (R$)",
                showlegend=False  # Remove legenda pois o eixo X já diz o nome
            )
            graficos_json['pizza_cat'] = json.dumps(fig_bar_mes, cls=plotly.utils.PlotlyJSONEncoder)

    context = {
        "mes_atual": hoje,
        "perfil": perfil,
        "total_disponivel": total_disponivel,
        "total_gasto": total_gasto,
        "saldo": saldo,
        "graficos": graficos_json, 
    }
    return render(request, "dashboard.html", context)