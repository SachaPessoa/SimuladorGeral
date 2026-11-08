const dataEl = document.getElementById("graficos-data");
const graficos = dataEl ? JSON.parse(dataEl.textContent) : {};
const colors = ["#176b87", "#c27a16", "#2962a3", "#b83d56", "#23805f", "#7652a6"];
const config = { responsive: true, displaylogo: false, scrollZoom: true, modeBarButtonsToRemove: ["pan2d", "lasso2d", "select2d", "autoScale2d"], toImageButtonOptions: { format: "png", filename: "grafico-descida-despressurizada", scale: 2 } };
const tr = (text) => (typeof gettext === "function" ? gettext(text) : text);
const array = (v) => Array.isArray(v) ? v : [];
const locale = document.documentElement.lang === "en" ? "en-US" : "pt-BR";
const nice = (v, d = 3) => Number(v).toLocaleString(locale, { maximumFractionDigits: d });

function layout(title, x, y, extra = {}) {
  return {
    autosize: true,
    height: 600,
    font: { family: 'Inter, "Segoe UI", Arial', color: "#334155" },
    title: { text: tr(title), x: 0.035, xanchor: "left", font: { size: 18, color: "#12355b" } },
    margin: { t: 66, r: 34, b: 145, l: 82 },
    paper_bgcolor: "#fff",
    plot_bgcolor: "#f9fbfc",
    hovermode: "closest",
    legend: { orientation: "h", x: 1, y: -0.18, xanchor: "right", yanchor: "top" },
    xaxis: { title: tr(x), gridcolor: "#e7eef3", automargin: true },
    yaxis: { title: tr(y), gridcolor: "#e7eef3", automargin: true },
    ...extra,
  };
}

function line(name, x, y, color, extra = {}) {
  const label = tr(name);
  return {
    type: "scatter",
    mode: extra.mode || "lines",
    name: label,
    x: array(x),
    y: array(y),
    line: { color, width: extra.width || 2.4, dash: extra.dash },
    marker: { color, size: extra.size || 8 },
    fill: extra.fill,
    fillcolor: extra.fillcolor,
    hovertemplate: extra.hovertemplate || `${label}<br>x=%{x:.4g}<br>y=%{y:.4g}<extra></extra>`,
  };
}

function marker(name, x, y, label, color = "#e11d48") {
  return { type: "scatter", mode: "markers", name: tr(name), x: [x], y: [y], marker: { color, size: 12 }, hovertemplate: `${label}<extra></extra>` };
}

function render(id, traces, chartLayout) {
  const el = document.getElementById(id);
  if (!el || !window.Plotly) return;
  Plotly.newPlot(el, traces, chartLayout, config).then(() => requestAnimationFrame(() => Plotly.Plots.resize(el)));
}

if (graficos.hq) {
  const g = graficos.hq;
  render("chart-hq", [
    line("Superfície lisa", g.q_liso, g.h, colors[0]),
    line("Superfície rugosa", g.q_rugoso, g.h, colors[1]),
    line("Q requerida", [g.q_requerida, g.q_requerida], [Math.min(...g.h), Math.max(...g.h)], colors[3], { dash: "dot" }),
    marker("Operação", g.operacao_q, g.operacao_h, `${tr("Operação")}<br>Q=${nice(g.operacao_q)} m³/h<br>h=${nice(g.operacao_h)} m`),
  ], layout("Capacidade hidráulica: altura vs vazão", "Vazão [m³/h]", "Altura de fluxo [m]"));
}

if (graficos.secao) {
  const g = graficos.secao;
  const geometryName = tr(g.tipo.charAt(0).toUpperCase() + g.tipo.slice(1));
  const info = g.tipo === "tubo"
    ? `D = ${nice(g.D)} m<br>h = ${nice(g.h)} m<br>B = ${nice(g.B)} m<br>θ = ${nice(g.theta)} rad (${nice(g.theta_graus, 1)}°)<br>A = ${nice(g.A, 4)} m²<br>P = ${nice(g.P, 4)} m<br>Rh = ${nice(g.Rh, 4)} m<br>Dh = ${nice(g.Dh, 4)} m<br>${tr("Preenchimento")} = ${nice(g.preenchimento, 1)}%`
    : `${geometryName}<br>h = ${nice(g.h)} m<br>B = ${nice(g.B)} m<br>b = ${nice(g.b)} m<br>m = ${nice(g.m)}<br>hmax = ${nice(g.hmax)} m<br>A = ${nice(g.A, 4)} m²<br>P = ${nice(g.P, 4)} m<br>Rh = ${nice(g.Rh, 4)} m<br>Dh = ${nice(g.Dh, 4)} m<br>${tr("Preenchimento")} = ${nice(g.preenchimento, 1)}%`;
  const annotations = [
    { x: 1.02, y: 0.98, xref: "paper", yref: "paper", text: info, showarrow: false, xanchor: "left", yanchor: "top", align: "left", bgcolor: "rgba(255,255,255,.94)", bordercolor: "#b8c7d3", borderpad: 7, font: { size: 11, color: "#12355b" } },
    { x: 0, y: g.h, xref: "x", yref: "y", text: `h = ${nice(g.h)} m`, showarrow: true, ax: -55, ay: -28, arrowcolor: "#e11d48", font: { size: 11, color: "#be123c" } },
    { x: 0, y: g.h, xref: "x", yref: "y", text: `B = ${nice(g.B)} m`, showarrow: true, ax: 55, ay: -28, arrowcolor: "#2962a3", font: { size: 11, color: "#2962a3" } },
  ];
  if (g.tipo === "tubo") annotations.push({ x: 0, y: g.D, xref: "x", yref: "y", text: `D = ${nice(g.D)} m`, showarrow: true, ax: 55, ay: 26, arrowcolor: "#176b87", font: { size: 11, color: "#176b87" } });
  else annotations.push({ x: 0, y: g.hmax, xref: "x", yref: "y", text: `hmax = ${nice(g.hmax)} m`, showarrow: true, ax: 60, ay: 25, arrowcolor: "#176b87", font: { size: 11, color: "#176b87" } });
  render("chart-secao", [
    line("Contorno da seção", g.contorno_x, g.contorno_y, colors[0]),
    line("Lâmina de polpa", g.agua_x, g.agua_y, colors[2], { fill: "toself", fillcolor: "rgba(41,98,163,.28)" }),
  ], layout("Seção preenchida", "Largura [m]", "Altura [m]", { margin: { t: 66, r: 180, b: 145, l: 82 }, annotations, xaxis: { title: tr("Largura [m]"), scaleanchor: "y", scaleratio: 1, gridcolor: "#e7eef3" }, yaxis: { title: tr("Altura [m]"), gridcolor: "#e7eef3" } }));
}

if (graficos.velocidade) {
  const g = graficos.velocidade;
  render("chart-velocidade", [
    line("U - superfície lisa", g.h, g.u_liso, colors[0]),
    line("U - superfície rugosa", g.h, g.u_rugoso, colors[1]),
    line("Ut1 - Abulnaga", g.h, g.ut1, colors[4], { dash: "dot" }),
    line("Ut2 - Green/Abulnaga", g.h, g.ut2, colors[3], { dash: "dot" }),
    marker("Operação", g.operacao_h, g.operacao_u, `${tr("Operação")}<br>h=${nice(g.operacao_h)} m<br>U=${nice(g.operacao_u)} m/s`),
  ], layout("Velocidade e limites de deposição", "Altura de fluxo [m]", "Velocidade [m/s]"));
}

if (graficos.froude) {
  const g = graficos.froude;
  render("chart-froude", [
    line("Froude - superfície lisa", g.h, g.liso, colors[0]),
    line("Froude - superfície rugosa", g.h, g.rugoso, colors[1]),
    line("Fr = 1", g.h, g.h.map(() => 1), colors[3], { dash: "dot" }),
    marker("Operação", g.operacao_h, g.operacao_y, `${tr("Operação")}<br>h=${nice(g.operacao_h)} m<br>Fr=${nice(g.operacao_y)}`),
  ], layout("Número de Froude vs altura", "Altura de fluxo [m]", "Froude [-]"));
}

if (graficos.atrito) {
  const g = graficos.atrito;
  render("chart-atrito", [
    line("fD - superfície lisa", g.h, g.f_liso, colors[0]),
    line("fD - superfície rugosa", g.h, g.f_rugoso, colors[1]),
    marker("Operação", g.operacao_h, g.operacao_y, `${tr("Operação")}<br>h=${nice(g.operacao_h)} m<br>fD=${nice(g.operacao_y, 5)}`),
  ], layout("Fator de atrito de Darcy vs altura", "Altura de fluxo [m]", "fD [-]"));
}

if (graficos.reynolds) {
  const g = graficos.reynolds;
  render("chart-reynolds", [
    line("Re - superfície lisa", g.h, g.re_liso, colors[0]),
    line("Re - superfície rugosa", g.h, g.re_rugoso, colors[1]),
    line("Rec - referência lisa", g.h, g.rec_liso, colors[4], { dash: "dot" }),
    line("Rec - referência rugosa", g.h, g.rec_rugoso, colors[3], { dash: "dot" }),
    marker("Operação", g.operacao_h, g.operacao_y, `${tr("Operação")}<br>h=${nice(g.operacao_h)} m<br>Re=${nice(g.operacao_y, 0)}`),
  ], layout("Reynolds e transição vs altura", "Altura de fluxo [m]", "Reynolds [-]", { yaxis: { title: tr("Reynolds [-]"), type: "log", gridcolor: "#e7eef3" } }));
}

function excel(v) { if (v === null || v === undefined) return ""; return String(v).replace(".", ","); }
function table(xName, x, series) {
  const rows = [[xName, ...series.map((s) => s.name)]];
  for (let i = 0; i < x.length; i += 1) rows.push([x[i], ...series.map((s) => s.values[i])]);
  return rows.map((r) => r.map(excel).join("\t")).join("\n");
}

const exports = [];
if (graficos.hq) exports.push({ title: tr("Capacidade hidráulica"), text: table("h [m]", graficos.hq.h, [{ name: tr("Q lisa [m³/h]"), values: graficos.hq.q_liso }, { name: tr("Q rugosa [m³/h]"), values: graficos.hq.q_rugoso }]) });
if (graficos.velocidade) exports.push({ title: tr("Velocidades e deposição"), text: table("h [m]", graficos.velocidade.h, [{ name: tr("U lisa [m/s]"), values: graficos.velocidade.u_liso }, { name: tr("U rugosa [m/s]"), values: graficos.velocidade.u_rugoso }, { name: "Ut1 [m/s]", values: graficos.velocidade.ut1 }, { name: "Ut2 [m/s]", values: graficos.velocidade.ut2 }]) });
if (graficos.froude) exports.push({ title: "Froude", text: table("h [m]", graficos.froude.h, [{ name: tr("Fr liso"), values: graficos.froude.liso }, { name: tr("Fr rugoso"), values: graficos.froude.rugoso }]) });
if (graficos.atrito) exports.push({ title: tr("Fator de atrito"), text: table("h [m]", graficos.atrito.h, [{ name: tr("fD liso"), values: graficos.atrito.f_liso }, { name: tr("fD rugoso"), values: graficos.atrito.f_rugoso }]) });
if (graficos.reynolds) exports.push({ title: "Reynolds", text: table("h [m]", graficos.reynolds.h, [{ name: tr("Re liso"), values: graficos.reynolds.re_liso }, { name: tr("Re rugoso"), values: graficos.reynolds.re_rugoso }, { name: tr("Rec liso"), values: graficos.reynolds.rec_liso }, { name: tr("Rec rugoso"), values: graficos.reynolds.rec_rugoso }]) });

const select = document.getElementById("export-chart-select"), copy = document.getElementById("copy-chart-data"), status = document.getElementById("export-chart-status");
if (select && copy) {
  select.innerHTML = exports.map((x, i) => `<option value="${i}">${x.title}</option>`).join("");
  copy.addEventListener("click", async () => {
    const x = exports[Number(select.value)];
    try {
      await navigator.clipboard.writeText(x.text);
      copy.textContent = tr("Copiado");
      status.textContent = `${x.title} ${tr("copiado. Cole diretamente no Excel.")}`;
    } catch (e) {
      status.textContent = tr("Não foi possível copiar os dados.");
    }
    setTimeout(() => { copy.textContent = tr("Copiar para Excel"); }, 1400);
  });
}

function resize() { if (window.Plotly) document.querySelectorAll(".chart .js-plotly-plot").forEach((p) => Plotly.Plots.resize(p)); }
window.addEventListener("load", () => { resize(); setTimeout(resize, 150); setTimeout(resize, 500); });
window.addEventListener("resize", resize);
