document.addEventListener('DOMContentLoaded', function() {
    
    function renderChart(chartId, dataKey) {
        const container = document.getElementById(chartId);
        const script = document.getElementById('d-' + dataKey);

        if (container && script) {
            try {
                const json = JSON.parse(script.textContent);
                const config = { responsive: true, displayModeBar: false };
                Plotly.newPlot(chartId, json.data, json.layout, config);
            } catch (e) {
                console.error(`Erro render ${chartId}`, e);
            }
        }
    }

    renderChart('chart-pizza', 'pizza_mes');
    renderChart('chart-comp', 'comparativo');
    renderChart('chart-meta', 'gasto_acumulado');
    renderChart('chart-top5', 'top5_cat');
    renderChart('chart-orc', 'orcado_realizado');
    renderChart('chart-pareto', 'pareto');
    renderChart('chart-evocat', 'evolucao_cat');
    renderChart('chart-semana', 'dia_semana');
    renderChart('chart-tipo', 'fixa_var');
    renderChart('chart-heat', 'heatmap');
    renderChart('chart-box', 'boxplot');
    const triggers = document.querySelectorAll('button[data-bs-toggle="tab"], .accordion-button');
    triggers.forEach(btn => {
        btn.addEventListener('click', () => {
            setTimeout(() => { window.dispatchEvent(new Event('resize')); }, 200);
        });
    });
});