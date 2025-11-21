document.addEventListener('DOMContentLoaded', function() {
    
    function renderChart(chartId, dataScriptId) {
        const chartContainer = document.getElementById(chartId);
        const dataScript = document.getElementById(dataScriptId);

        if (chartContainer && dataScript) {
            try {
                const json = JSON.parse(dataScript.textContent);
                const config = {
                    responsive: true, 
                    displayModeBar: false, 
                    staticPlot: false 
                };

                Plotly.newPlot(chartId, json.data, json.layout, config);
            } catch (e) {
                console.error("Erro chart " + chartId, e);
            }
        }
    }

    renderChart('chart-pizza', 'data-pizza');
    renderChart('chart-barras', 'data-barras');
    renderChart('chart-area', 'data-area');

    const accordions = document.querySelectorAll('.accordion-collapse');
    accordions.forEach(el => {
        el.addEventListener('shown.bs.collapse', () => {
            window.dispatchEvent(new Event('resize'));
        });
    });
});