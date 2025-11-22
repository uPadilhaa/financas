let charts = {}; 

document.addEventListener('DOMContentLoaded', function() {
    
    function renderChart(chartId, dataKey) {
        const container = document.getElementById(chartId);
        const script = document.getElementById('d-' + dataKey);

        if (container && script) {
            try {
                const json = JSON.parse(script.textContent);
                const config = { responsive: true, displayModeBar: false, scrollZoom: false, doubleClick: false, showTips: false };
                
                Plotly.newPlot(chartId, json.data, json.layout, config).then(gd => {
                    charts[chartId] = gd;
                });
            } catch (e) { console.error(`Erro render ${chartId}`, e); }
        }
    }

    renderChart('chart-pizza', 'pizza_mes');
    renderChart('chart-comp', 'comparativo');
    renderChart('chart-orc', 'orcado_realizado');
    renderChart('chart-top5', 'top5_cat');
    renderChart('chart-semana', 'dia_semana');
    renderChart('chart-tipo', 'fixa_var');
    document.querySelectorAll('.accordion-collapse').forEach(el => {
        el.addEventListener('shown.bs.collapse', () => window.dispatchEvent(new Event('resize')));
    });
});

window.toggleChart = function(chartId, tipo) {
    const gd = charts[chartId];
    if (!gd) return;

    let update = {};
    let layoutUpdate = {};

    if (chartId === 'chart-orc') {
        if (tipo === 'Global') {
            update = { visible: [true, true, false, false] };
        } else {
            update = { visible: [false, false, true, true] };
        }
    } 
    else {
        if (tipo === 'Global') {
            update = { visible: [true, false] };
            
            if (chartId === 'chart-top5') {
                const xData = gd.data[0].x;
                const maxVal = xData ? Math.max(0, ...xData) : 0;
                layoutUpdate = { 'xaxis.range': [0, maxVal * 1.25] };
            }
        } else {
            update = { visible: [false, true] };
            
            if (chartId === 'chart-top5') {
                const xData = gd.data[1].x;
                const maxVal = xData ? Math.max(0, ...xData) : 0;
                layoutUpdate = { 'xaxis.range': [0, (maxVal > 0 ? maxVal : 100) * 1.25] };
            }
        }
    }

    Plotly.restyle(gd, update).then(() => {
        if (Object.keys(layoutUpdate).length > 0) {
            Plotly.relayout(gd, layoutUpdate);
        }
    });
};