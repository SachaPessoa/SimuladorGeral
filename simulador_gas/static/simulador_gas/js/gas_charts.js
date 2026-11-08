const el = document.getElementById("gas-charts-data");
const charts = el ? JSON.parse(el.textContent) : {};
const colors = ["#176b87", "#c27a16", "#2962a3", "#7652a6", "#23805f", "#b83d56", "#16818a"];
const config = { responsive: true, displaylogo: false, scrollZoom: true, modeBarButtonsToRemove: ["lasso2d", "select2d"] };
const tr = (text) => (typeof gettext === "function" ? gettext(text) : text);
function layout(title, xTitle, yTitle, extra = {}) {
  return { title: { text: tr(title), x: 0.035, xanchor: "left", font: { size: 18, color: "#12355b" } }, font: { family: 'Inter, "Segoe UI", Roboto, Arial, sans-serif', color: "#334155", size: 12 }, margin: { t: 66, r: 48, b: 92, l: 82 }, paper_bgcolor: "#fff", plot_bgcolor: "#f9fbfc", hovermode: "closest", legend: { orientation: "h", x: 1, y: -0.18, xanchor: "right" }, xaxis: { title: tr(xTitle), gridcolor: "#e7eef3" }, yaxis: { title: tr(yTitle), gridcolor: "#e7eef3" }, ...extra };
}
function traces(group) {
  if (!group) return [];
  return (group.series || []).map((s, i) => ({ type: "scatter", mode: "lines", name: tr(s.name), x: group.x || [], y: s.y || [], line: { color: colors[i % colors.length], width: 2.4 }, yaxis: s.axis === "y2" ? "y2" : "y", hovertemplate: "%{fullData.name}<br>x=%{x:.4g}<br>y=%{y:.4g}<extra></extra>" }));
}
function plot(id, group, yTitle, extra = {}) {
  const target = document.getElementById(id);
  if (!target || !group || !window.Plotly) return;
  Plotly.newPlot(target, traces(group), layout(group.title, "x [m]", yTitle, extra), config);
}
function selectedGroup(title, x, selections) {
  return {
    title,
    x: x || [],
    series: selections.map(({ group, index, axis }) => ({ ...(group.series || [])[index], axis })),
  };
}
function secondaryAxis(title) {
  return { title: tr(title), overlaying: "y", side: "right", gridcolor: "rgba(0,0,0,0)" };
}

const flowGroup = charts.flow_density_velocity || { x: [], series: [] };
const hydraulicGroup = charts.flow_properties || { x: [], series: [] };

plot("gas-chart-pressure-temperature", charts.pressure_temperature, tr("Pressão [bar(a)]"), { yaxis2: secondaryAxis("Temperatura [K]") });
plot("gas-chart-flow-density-velocity", selectedGroup("Vazão volumétrica e velocidade", flowGroup.x, [
  { group: flowGroup, index: 1, axis: "y" },
  { group: flowGroup, index: 2, axis: "y2" },
]), tr("Vazão volumétrica [m³/h]"), { yaxis2: secondaryAxis("Velocidade [m/s]") });
plot("gas-chart-flow-properties", selectedGroup("Densidade e número de Mach", hydraulicGroup.x, [
  { group: flowGroup, index: 0, axis: "y" },
  { group: hydraulicGroup, index: 2, axis: "y2" },
]), tr("Densidade [kg/m³]"), { yaxis2: secondaryAxis("Número de Mach [-]") });
plot("gas-chart-speed-sound", selectedGroup("Velocidade do som", hydraulicGroup.x, [
  { group: hydraulicGroup, index: 3, axis: "y" },
]), tr("Velocidade do som [m/s]"));
plot("gas-chart-thermo", charts.thermodynamic_properties, tr("Base mássica"));
plot("gas-chart-specific-heats", charts.specific_heats, tr("Valores calculados"));
(function plotMollier() {
  const m = charts.mollier;
  const target = document.getElementById("gas-chart-mollier");
  if (!target || !m || !window.Plotly) return;
  const data = [];
  (m.isobars || []).forEach((s, i) => data.push({ type: "scatter", mode: "lines", name: `P ${s.name}`, x: s.s, y: s.h, line: { color: "rgba(23,107,135,0.28)", width: 1.2 }, showlegend: i < 8 }));
  (m.isotherms || []).forEach((s, i) => data.push({ type: "scatter", mode: "lines", name: `T ${s.name}`, x: s.s, y: s.h, line: { color: "rgba(194,122,22,0.28)", width: 1.1, dash: "dot" }, showlegend: i < 6 }));
  if (m.saturation) data.push({ type: "scatter", mode: "lines", name: tr("Saturação"), x: m.saturation.s, y: m.saturation.h, line: { color: "#b42318", width: 2, dash: "dash" } });
  if (m.path) data.push({ type: "scatter", mode: "lines+markers", name: tr("Trajetória"), x: m.path.s, y: m.path.h, line: { color: "#12355b", width: 3 }, marker: { size: 5, color: "#12355b" } });
  Plotly.newPlot(target, data, layout(`Mollier h-s - ${m.fluid}`, tr("s [kJ/(kg.K)]"), tr("h [kJ/kg]"), { margin: { t: 68, r: 36, b: 92, l: 82 } }), config);
})();
window.addEventListener("resize", () => document.querySelectorAll(".gas-charts .js-plotly-plot").forEach((plot) => Plotly.Plots.resize(plot)));
