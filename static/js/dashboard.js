document.addEventListener("DOMContentLoaded", function () {
    const chartMap = {
        "chart-evo": "d-evo",
        "chart-invest-desp": "d-invest-desp",
        "chart-pizza": "d-pizza",
        "chart-top5": "d-top5",
        "chart-orc": "d-orc",
    };

    function renderChart(containerId, scriptId) {
        const container = document.getElementById(containerId);
        const scriptElement = document.getElementById(scriptId);
        if (!container || !scriptElement) return;

        try {
            const fig = JSON.parse(scriptElement.textContent);
            const config = {
                responsive: true,
                displayModeBar: false,
                scrollZoom: false,
            };
            Plotly.newPlot(container, fig.data, fig.layout, config);
        } catch (e) {
            console.error("Erro ao renderizar gráfico:", containerId, e);
        }
    }

    Object.entries(chartMap).forEach(([containerId, scriptId]) => {
        renderChart(containerId, scriptId);
    });

    window.addEventListener("resize", function () {
        Object.keys(chartMap).forEach((id) => {
            const el = document.getElementById(id);
            if (el && el.data) {
                Plotly.Plots.resize(el);
            }
        });
    });
});
