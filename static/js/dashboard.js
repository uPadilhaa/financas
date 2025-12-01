document.addEventListener("DOMContentLoaded", function () {
  const chartMap = {
    "chart-comp": "comparativo",
    "chart-pizza": "pizza_mes",
    "chart-top5": "top5_cat",
    "chart-semana": "dia_semana",
    "chart-orc": "orcado_realizado",
  };

  function renderChart(containerId, dataKey) {
    const container = document.getElementById(containerId);
    const script = document.getElementById("d-" + dataKey);
    if (!container || !script) return;

    try {
      const fig = JSON.parse(script.textContent);
      Plotly.newPlot(container, fig.data, fig.layout, {
        responsive: true,
        displayModeBar: false,
      });
    } catch (e) {
      console.error("Erro ao renderizar gráfico", dataKey, e);
    }
  }

  Object.entries(chartMap).forEach(([containerId, key]) =>
    renderChart(containerId, key)
  );

  window.addEventListener("resize", function () {
    Object.keys(chartMap).forEach((id) => {
      const el = document.getElementById(id);
      if (el && el.data) {
        Plotly.Plots.resize(el);
      }
    });
  });
});
