document.addEventListener("DOMContentLoaded", function () {
    const chartMap = {
        "chart-evo": "d-evo",
        "chart-fluxo": "d-fluxo", 
        "chart-pizza": "d-pizza",
        "chart-orc": "d-orc",
    };

    const PLOT_CONFIG = {
        responsive: true,
        displayModeBar: false,       
        scrollZoom: false,           
        doubleClick: false,          
        showAxisDragHandles: false,  
        staticPlot: false,           
        displaylogo: false
    };

    const LAYOUT_OVERRIDE = {
        dragmode: false, 
        xaxis: { fixedrange: true }, 
        yaxis: { fixedrange: true }  
    };

    function renderChart(containerId, scriptId) {
        const container = document.getElementById(containerId);
        const scriptElement = document.getElementById(scriptId);
        if (!container || !scriptElement) return;

        try {
            const fig = JSON.parse(scriptElement.textContent);            
            const finalLayout = { ...fig.layout, ...LAYOUT_OVERRIDE };
            if(fig.layout.xaxis) finalLayout.xaxis = { ...fig.layout.xaxis, fixedrange: true };
            if(fig.layout.yaxis) finalLayout.yaxis = { ...fig.layout.yaxis, fixedrange: true };

            Plotly.newPlot(container, fig.data, finalLayout, PLOT_CONFIG);
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