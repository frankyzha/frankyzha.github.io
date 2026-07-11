import { plotlyDarkLayout, plotlyLightLayout } from "./plotly-themes.js";

const plots = Array.from(document.querySelectorAll("pre > code.language-plotly"));

function renderPlots() {
  if (!plots.length || !window.Plotly) return;

  const template = document.documentElement.hasAttribute("data-theme")
    ? plotlyDarkLayout
    : plotlyLightLayout;

  plots.forEach((source) => {
    const data = JSON.parse(source.textContent);
    let chart = source.parentElement.nextElementSibling;

    source.parentElement.classList.add("hidden");
    if (!chart?.classList.contains("plotly-chart")) {
      chart = document.createElement("div");
      chart.className = "plotly-chart";
      source.parentElement.after(chart);
    }

    data.layout = data.layout || {};
    data.layout.template = { ...template, ...data.layout.template };
    window.Plotly.react(chart, data.data, data.layout);
  });
}

renderPlots();
window.addEventListener("load", renderPlots, { once: true });
document.addEventListener("site:themechange", renderPlots);
