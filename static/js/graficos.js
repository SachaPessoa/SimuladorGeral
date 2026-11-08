const dataEl = document.getElementById("graficos-data");
let graficos = {};

if (dataEl) {
  graficos = JSON.parse(dataEl.textContent);
  if (typeof graficos === "string") {
    graficos = JSON.parse(graficos);
  }
}

const plotConfig = {
  responsive: true,
  displaylogo: false,
  scrollZoom: true,
  showTips: true,
  modeBarButtonsToRemove: ["pan2d", "lasso2d", "select2d", "autoScale2d"],
  toImageButtonOptions: { format: "png", filename: "grafico-simulador-polpa", scale: 2 },
};

const colors = ["#176b87", "#c27a16", "#2962a3", "#7652a6", "#23805f", "#b83d56", "#16818a", "#9b7218", "#4759a8", "#8b4f91"];

function hasPlotly() {
  return typeof window.Plotly !== "undefined";
}

function asArray(value) {
  return Array.isArray(value) ? value : [];
}

function finitePairs(x, y) {
  const pairs = [];
  const n = Math.min(asArray(x).length, asArray(y).length);
  for (let i = 0; i < n; i += 1) {
    const xi = Number(x[i]);
    const yi = Number(y[i]);
    if (Number.isFinite(xi) && Number.isFinite(yi)) pairs.push([xi, yi]);
  }
  return pairs;
}

function nice(value, digits = 3) {
  const n = Number(value);
  if (!Number.isFinite(n)) return "";
  return n.toLocaleString("pt-BR", { maximumFractionDigits: digits });
}

function baseLayout(title, xTitle, yTitle, extra = {}) {
  return {
    font: { family: 'Inter, "Segoe UI", Roboto, Arial, sans-serif', color: "#334155", size: 12 },
    title: { text: title, x: 0.035, xanchor: "left", font: { size: 18, color: "#12355b" } },
    margin: { t: 66, r: 34, b: 150, l: 82 },
    paper_bgcolor: "#ffffff",
    plot_bgcolor: "#f9fbfc",
    hovermode: "closest",
    hoverlabel: { bgcolor: "#ffffff", bordercolor: "#a8beca", font: { color: "#172033", size: 12 } },
    legend: {
      orientation: "h",
      x: 1,
      y: -0.19,
      xanchor: "right",
      yanchor: "top",
      font: { size: 11, color: "#475569" },
      bgcolor: "rgba(255,255,255,0)",
    },
    xaxis: { title: xTitle, gridcolor: "#e7eef3", linecolor: "#b9c7d1", zeroline: false, automargin: true },
    yaxis: { title: yTitle, gridcolor: "#e7eef3", linecolor: "#b9c7d1", zeroline: false, automargin: true },
    ...extra,
  };
}

function scatterLine(name, x, y, opts = {}) {
  return {
    type: "scatter",
    mode: opts.mode || "lines",
    name,
    x: asArray(x),
    y: asArray(y),
    line: { width: opts.width || 2.4, color: opts.color, dash: opts.dash },
    marker: { size: opts.size || 8, color: opts.color, symbol: opts.symbol || "circle" },
    hovertemplate: opts.hovertemplate || "%{fullData.name}<br>x=%{x:.4g}<br>y=%{y:.4g}<extra></extra>",
    visible: opts.visible,
    showlegend: opts.showlegend,
  };
}

function markerTrace(name, x, y, label, opts = {}) {
  if (x === null || x === undefined || y === null || y === undefined) return null;
  return {
    type: "scatter",
    mode: "markers",
    name,
    x: [Number(x)],
    y: [Number(y)],
    marker: { size: opts.size || 12, color: opts.color || "#e11d48", symbol: opts.symbol || "circle" },
    hovertemplate: `${label}<extra></extra>`,
    showlegend: opts.showlegend,
  };
}

function renderFallbackChart(id, title, xTitle, yTitle, series) {
  const el = document.getElementById(id);
  if (!el) return;
  const width = Math.max(el.clientWidth || 520, 420);
  const height = Math.max(el.clientHeight || 400, 340);
  const margin = { top: 46, right: 22, bottom: 56, left: 66 };
  const plotW = width - margin.left - margin.right;
  const plotH = height - margin.top - margin.bottom;
  const normalized = series.map((s) => ({ name: s.name, points: finitePairs(s.x, s.y), dash: s.line && s.line.dash })).filter((s) => s.points.length > 1);
  if (!normalized.length) {
    el.innerHTML = `<div class="chart-empty">Sem dados para ${title}</div>`;
    return;
  }
  const all = normalized.flatMap((s) => s.points);
  let minX = Math.min(...all.map((p) => p[0]));
  let maxX = Math.max(...all.map((p) => p[0]));
  let minY = Math.min(...all.map((p) => p[1]));
  let maxY = Math.max(...all.map((p) => p[1]));
  if (minX === maxX) maxX = minX + 1;
  if (minY === maxY) maxY = minY + 1;
  const yPad = (maxY - minY) * 0.08;
  minY -= yPad;
  maxY += yPad;
  const sx = (x) => margin.left + ((x - minX) / (maxX - minX)) * plotW;
  const sy = (y) => margin.top + plotH - ((y - minY) / (maxY - minY)) * plotH;
  const paths = normalized.map((s, idx) => {
    const d = s.points.map((p, i) => `${i === 0 ? "M" : "L"} ${sx(p[0]).toFixed(2)} ${sy(p[1]).toFixed(2)}`).join(" ");
    const dash = s.dash === "dot" ? ' stroke-dasharray="2 5"' : (s.dash ? ' stroke-dasharray="8 5 2 5"' : "");
    return `<path d="${d}" fill="none" stroke="${colors[idx % colors.length]}" stroke-width="2.4"${dash}><title>${s.name}</title></path>`;
  }).join("");
  el.innerHTML = `<svg viewBox="0 0 ${width} ${height}" role="img" aria-label="${title}">
    <text x="${margin.left}" y="25" class="chart-title">${title}</text>${paths}
    <text x="${margin.left + plotW / 2}" y="${height - 6}" class="axis-title" text-anchor="middle">${xTitle}</text>
    <text transform="translate(16 ${margin.top + plotH / 2}) rotate(-90)" class="axis-title" text-anchor="middle">${yTitle}</text>
  </svg>`;
}

function renderChart(id, traces, layout, fallbackLabels) {
  const target = document.getElementById(id);
  if (!target) return;
  const cleanTraces = traces.filter(Boolean).filter((trace) => asArray(trace.x).length && asArray(trace.y).length);
  if (!cleanTraces.length) {
    target.remove();
    return;
  }
  if (hasPlotly()) {
    const plotLayout = {
      autosize: true,
      height: Math.max(target.clientHeight || 0, 560),
      ...layout,
    };
    Plotly.newPlot(target, cleanTraces, plotLayout, plotConfig).then(() => {
      requestAnimationFrame(() => Plotly.Plots.resize(target));
      setTimeout(() => Plotly.Plots.resize(target), 120);
    });
    return;
  }
  renderFallbackChart(id, layout.title.text || layout.title, fallbackLabels.x, fallbackLabels.y, cleanTraces);
}

function nearestIndex(values, target) {
  const xs = asArray(values).map(Number);
  if (!xs.length || target === null || target === undefined) return -1;
  let best = 0;
  let bestDiff = Math.abs(xs[0] - Number(target));
  for (let i = 1; i < xs.length; i += 1) {
    const diff = Math.abs(xs[i] - Number(target));
    if (diff < bestDiff) {
      best = i;
      bestDiff = diff;
    }
  }
  return best;
}

function pipeSectionGeometry(hRaw, points = 90) {
  const h = Math.max(0, Math.min(1, Number(hRaw || 0)));
  const r = 0.5;
  const center = 0.5;
  const dy = h - center;
  const chordHalf = Math.sqrt(Math.max(0, r * r - dy * dy));
  const x1 = center - chordHalf;
  const x2 = center + chordHalf;
  const xsTop = Array.from({ length: points }, (_, i) => x1 + ((x2 - x1) * i) / Math.max(points - 1, 1));
  const xsBottom = [...xsTop].reverse();
  const lowerArcY = xsBottom.map((x) => center - Math.sqrt(Math.max(0, r * r - (x - center) * (x - center))));
  return {
    h,
    x1,
    x2,
    lowerX: [...xsTop, ...xsBottom, xsTop[0]],
    lowerY: [...xsTop.map(() => h), ...lowerArcY, h],
  };
}

function plotPerda() {
  const g = graficos.perda_carga;
  if (!g) return;
  const traces = [
    scatterLine("WASP Modificado", g.velocidades, g.polpa, { color: colors[0], hovertemplate: `WASP Modificado<br>U=%{x:.3f} m/s<br>J=%{y:.3f} ${gettext("m coluna de polpa/km")}<extra></extra>` }),
  ];
  traces.push(scatterLine(gettext("Água"), g.velocidades, g.agua, { color: colors[1], dash: "dot", hovertemplate: `${gettext("Água")}<br>U=%{x:.3f} m/s<br>DP=%{y:.3f} m/km<extra></extra>` }));
  if (asArray(g.fourcm_total).length) {
    traces.push(scatterLine("4CM", g.fourcm_velocidades || g.velocidades, g.fourcm_total, { color: colors[5], width: 3, hovertemplate: `4CM<br>U=%{x:.3f} m/s<br>J=%{y:.3f} ${gettext("m coluna de polpa/km")}<extra></extra>` }));
  }
  if (asArray(g.arraste).length) {
    traces.push(scatterLine(gettext("Arraste"), g.velocidades, g.arraste, { color: colors[4], visible: "legendonly", hovertemplate: `${gettext("Arraste")}<br>U=%{x:.3f} m/s<br>DP=%{y:.3f} m/km<extra></extra>` }));
  }
  const comp = g.fourcm_componentes || {};
  [
    [gettext("4CM carrier"), comp.carrier, colors[4]],
    [gettext("4CM pseudo-homogêneo"), comp.pseudo, colors[2]],
    [gettext("4CM heterogêneo"), comp.heterogeneo, colors[1]],
    [gettext("4CM estratificado"), comp.estratificado, colors[6]],
  ].forEach(([name, values, color]) => {
    if (asArray(values).length) traces.push(scatterLine(name, g.fourcm_velocidades || g.velocidades, values, { color, visible: "legendonly", dash: "dot" }));
  });
  traces.push(markerTrace(gettext("Operação"), g.operacao_x, g.operacao_y, `${gettext("Ponto de operação")}<br>U=${nice(g.operacao_x)} m/s<br>WASP=${nice(g.operacao_y)} m coluna de polpa/km`, { color: "#e11d48" }));
  const trans = g.transicao_laminar_turbulento;
  if (trans) {
    traces.push(markerTrace(gettext("Transição L-T"), trans.velocidade, trans.perda_carga, `${gettext("Transição laminar/turbulento")}<br>U=${nice(trans.velocidade)} m/s<br>DP=${nice(trans.perda_carga)} m/km`, { color: "#7c2d12", symbol: "diamond" }));
  }
  const limite = g.limite_hom_het;
  if (limite) {
    traces.push(markerTrace(gettext("Limite Hom-Het"), limite.velocidade, limite.perda_carga, `${gettext("Limite Hom-Het")}<br>U=${nice(limite.velocidade)} m/s<br>DP=${nice(limite.perda_carga)} m/km<br>${gettext("Arraste")}=${nice(limite.frac_arraste_percent)}%`, { color: "#111827", symbol: "triangle-up" }));
  }
  const scale = g.scale || "log";
  const xType = scale === "log" ? "log" : "linear";
  const yType = scale === "linear" ? "linear" : "log";
  renderChart("chart-perda", traces, baseLayout(gettext("Curva J - WASP Modificado x 4CM"), gettext("Velocidade média da polpa [m/s]"), gettext("Perda de carga [m coluna de polpa/km]"), {
    xaxis: { title: gettext("Velocidade média da polpa [m/s]"), type: xType, gridcolor: "#edf3f6" },
    yaxis: { title: gettext("Perda de carga [m coluna de polpa/km]"), type: yType, gridcolor: "#edf3f6" },
  }), { x: gettext("Velocidade média da polpa [m/s]"), y: gettext("Perda de carga [m coluna de polpa/km]") });
}

function plotConcentracao() {
  const g = graficos.concentracao_vertical;
  if (!g) return;
  const theta = Array.from({ length: 121 }, (_, i) => (2 * Math.PI * i) / 120);
  const circleX = theta.map((t) => 0.5 + 0.5 * Math.cos(t));
  const circleY = theta.map((t) => 0.5 + 0.5 * Math.sin(t));
  const hasDeposit = g.altura_deposito !== undefined && g.altura_deposito !== null;
  const deposit = hasDeposit ? pipeSectionGeometry(g.altura_deposito, 90) : null;
  const traces = [
    scatterLine(gettext("Seção da tubulação"), circleX, circleY, { color: "#8a96a3", width: 1.4, hovertemplate: `${gettext("Seção da tubulação")}<extra></extra>` }),
    scatterLine("φ total", g.x_phi, g.yD, { color: colors[0], hovertemplate: `${gettext("Perfil")}<br>φ=%{x:.5f}<br>y/D=%{y:.4f}<extra></extra>` }),
    markerTrace("Referência y/D=0,1", g.phi_ref, g.phi_ref_yD || 0.1, `Referência<br>φ=${nice(g.phi_ref, 5)}<br>y/D=${nice(g.phi_ref_yD || 0.1)}`, { color: "#e11d48" }),
  ];
  if (deposit) {
    traces.unshift({
      type: "scatter",
      mode: "lines",
      name: gettext("depósito"),
      x: deposit.lowerX,
      y: deposit.lowerY,
      fill: "toself",
      fillcolor: "rgba(216, 180, 106, 0.58)",
      line: { color: "rgba(124, 45, 18, 0.18)", width: 1 },
      hovertemplate: `${gettext("Depósito")}<br>y/D=${nice(deposit.h)}<extra></extra>`,
    });
    traces.push(scatterLine(gettext("y/D depósito"), [deposit.x1, deposit.x2], [deposit.h, deposit.h], {
      mode: "lines",
      color: "#2563eb",
      width: 2.4,
      hovertemplate: `${gettext("Depósito")}<br>y/D=${nice(deposit.h)}<extra></extra>`,
    }));
  }
  renderChart("chart-concentracao", traces, baseLayout(gettext("Perfil vertical de concentração"), "φ total", "y/D", {
    width: undefined,
    xaxis: { title: "φ total", range: [0, 1], constrain: "domain", gridcolor: "#edf3f6" },
    yaxis: { title: "y/D", range: [0, 1], scaleanchor: "x", scaleratio: 1, gridcolor: "#edf3f6" },
    annotations: deposit ? [{
      x: Math.min(0.94, Math.max(0.08, deposit.x2 - 0.02)),
      y: Math.min(0.98, deposit.h + 0.035),
      xref: "x",
      yref: "y",
      text: `${gettext("y/D depósito")} = ${nice(deposit.h)}`,
      showarrow: false,
      xanchor: "right",
      yanchor: "bottom",
      font: { color: "#2563eb", size: 11 },
      bgcolor: "rgba(255,255,255,0.82)",
      bordercolor: "#d7e0e7",
      borderpad: 3,
    }] : [],
  }), { x: gettext("φ total"), y: "y/D" });
}

function plotTwoLayerSection() {
  const g = graficos.gillies_secao;
  if (!g) return;

  const section = pipeSectionGeometry(g.altura_interface_yD, 90);
  const h = section.h;

  const r = 0.5;
  const center = 0.5;
  const theta = Array.from({ length: 161 }, (_, i) => (2 * Math.PI * i) / 160);
  const circleX = theta.map((t) => center + r * Math.cos(t));
  const circleY = theta.map((t) => center + r * Math.sin(t));

  const traces = [
    {
      type: "scatter",
      mode: "lines",
      name: gettext("camada inferior"),
      x: section.lowerX,
      y: section.lowerY,
      fill: "toself",
      fillcolor: "rgba(216, 180, 106, 0.72)",
      line: { color: "rgba(124, 45, 18, 0.25)", width: 1 },
      hovertemplate: `${gettext("camada inferior")}<br>h/D=${nice(h, 4)}<br>A2/A=${nice(g.A2_over_A, 4)}<extra></extra>`,
    },
    scatterLine(gettext("seção da tubulação"), circleX, circleY, {
      color: "#334155",
      width: 2.4,
      hovertemplate: `${gettext("seção da tubulação")}<extra></extra>`,
      showlegend: false,
    }),
    scatterLine(gettext("interface"), [section.x1, section.x2], [h, h], {
      color: "#7c2d12",
      width: 3,
      hovertemplate: `${gettext("interface")}<br>h/D=${nice(h, 4)}<extra></extra>`,
    }),
  ];

  renderChart("chart-gillies-section", traces, baseLayout(gettext("Seção transversal - modelo de duas camadas"), "x/D", "y/D", {
    margin: { t: 66, r: 230, b: 76, l: 76 },
    xaxis: { title: "x/D", range: [0, 1], constrain: "domain", gridcolor: "#edf3f6", zeroline: false },
    yaxis: { title: "y/D", range: [0, 1], scaleanchor: "x", scaleratio: 1, gridcolor: "#edf3f6", zeroline: false },
    annotations: [
      {
        x: 1.06,
        y: 0.88,
        xref: "paper",
        yref: "paper",
        xanchor: "left",
        yanchor: "top",
        align: "left",
        showarrow: false,
        bgcolor: "rgba(255,255,255,0.86)",
        bordercolor: "#d7e0e7",
        borderpad: 8,
        font: { color: "#12355b", size: 12 },
        text: [
          `U1 = ${nice(g.U1, 3)} m/s`,
          `U2 = ${nice(g.U2, 3)} m/s`,
          `C1 = ${nice(g.C1, 4)}`,
          `Clim = ${nice(g.Clim, 4)}`,
          `A2/A = ${nice(g.A2_over_A, 4)}`,
          `y/D interface = ${nice(h, 4)}`,
          `d12 = ${nice(g.d12_um, 1)} µm`,
        ].join("<br>"),
      },
      {
        x: Math.min(0.94, Math.max(0.08, section.x2 - 0.02)),
        y: Math.min(0.98, h + 0.035),
        xref: "x",
        yref: "y",
        text: `y/D interface = ${nice(h, 4)}`,
        showarrow: false,
        xanchor: "right",
        yanchor: "bottom",
        font: { color: "#7c2d12", size: 12 },
        bgcolor: "rgba(255,255,255,0.82)",
        bordercolor: "#d7e0e7",
        borderpad: 3,
      },
      {
        x: 0.5,
        y: Math.max(h + 0.08, 0.62),
        text: gettext("camada superior"),
        showarrow: false,
        font: { color: "#0f3b5f", size: 13 },
        bgcolor: "rgba(255,255,255,0.55)",
      },
      {
        x: 0.5,
        y: Math.max(0.04, h / 2),
        text: gettext("camada inferior"),
        showarrow: false,
        font: { color: "#4a2d08", size: 13 },
        bgcolor: "rgba(255,255,255,0.55)",
      },
    ],
  }), { x: "x/D", y: "y/D" });
}

function plotCv() {
  const g = graficos.cv_veiculo;
  if (!g) return;
  const phiRatio = "φ<sub>VV</sub> / φ<sub>V</sub> [%]";
  const traces = [
    scatterLine("φ<sub>VV</sub>", g.velocidades, g.percentual, { color: colors[0], hovertemplate: `${gettext("Sólidos suspensos")}<br>U=%{x:.3f} m/s<br>φ<sub>VV</sub>/φ<sub>V</sub>=%{y:.3f}%<extra></extra>` }),
    markerTrace(gettext("Operação"), g.operacao_x, g.operacao_y, `${gettext("Ponto de operação")}<br>U=${nice(g.operacao_x)} m/s<br>Cv=${nice(g.operacao_y)}%`, { color: "#e11d48" }),
  ];
  renderChart("chart-cv", traces, baseLayout(gettext("Sólidos suspensos vs velocidade"), gettext("Velocidade [m/s]"), phiRatio, {
    xaxis: { title: gettext("Velocidade [m/s]"), type: "log", gridcolor: "#edf3f6" },
    yaxis: { title: phiRatio, type: "log", gridcolor: "#edf3f6" },
  }), { x: gettext("Velocidade [m/s]"), y: phiRatio });
}

function plotC0Ca() {
  const g = graficos.c0ca;
  if (!g) return;
  const traces = asArray(g.series).map((serie, idx) => scatterLine(`${Number(serie.diametro_um).toFixed(0)} µm`, g.velocidades, serie.valores, {
    color: colors[idx % colors.length],
    hovertemplate: `${Number(serie.diametro_um).toFixed(0)} µm<br>U=%{x:.3f} m/s<br>C/Ca=%{y:.3f}%<extra></extra>`,
  }));
  const opIdx = nearestIndex(g.velocidades, g.operacao_x);
  asArray(g.series).forEach((serie, idx) => {
    if (opIdx >= 0 && asArray(serie.valores).length > opIdx) {
      traces.push(markerTrace(`${Number(serie.diametro_um).toFixed(0)} µm operação`, g.velocidades[opIdx], serie.valores[opIdx], `${Number(serie.diametro_um).toFixed(0)} µm<br>U=${nice(g.velocidades[opIdx])} m/s<br>C/Ca=${nice(serie.valores[opIdx])}%`, { color: colors[idx % colors.length], size: 9, showlegend: false }));
    }
  });
  renderChart("chart-c0ca", traces, baseLayout(gettext("C/Ca por classe granulométrica"), gettext("Velocidade [m/s]"), "C/Ca [%]", {
    yaxis: { title: "C/Ca [%]", range: [0, 100], gridcolor: "#edf3f6" },
  }), { x: gettext("Velocidade [m/s]"), y: "C/Ca [%]" });
}

function plotGranulometriaModelo() {
  const g = graficos.granulometria_passante_modelo;
  if (!g) return;
  const traces = [
    scatterLine("y/D = 0,05", g.diametros_um, g.yD_005, { mode: "lines+markers", color: colors[0], hovertemplate: `y/D=0,05<br>D=%{x:.3f} µm<br>${gettext("Passante")}=%{y:.3f}%<extra></extra>` }),
    scatterLine("y/D = 0,50", g.diametros_um, g.yD_050, { mode: "lines+markers", color: colors[1], hovertemplate: `y/D=0,50<br>D=%{x:.3f} µm<br>${gettext("Passante")}=%{y:.3f}%<extra></extra>` }),
    scatterLine("y/D = 0,95", g.diametros_um, g.yD_095, { mode: "lines+markers", color: colors[2], hovertemplate: `y/D=0,95<br>D=%{x:.3f} µm<br>${gettext("Passante")}=%{y:.3f}%<extra></extra>` }),
  ];
  renderChart("chart-gran-modelo", traces, baseLayout(gettext("Granulometria acumulada passante (modelo)"), gettext("Diâmetro [µm]"), gettext("Passante [%]"), {
    yaxis: { title: gettext("Passante [%]"), range: [0, 100], gridcolor: "#edf3f6" },
  }), { x: gettext("Diâmetro [µm]"), y: gettext("Passante [%]") });
}

function plotGranulometriaEntrada() {
  const g = graficos.granulometria_passante_entrada;
  if (!g) return;
  const traces = [scatterLine(gettext("Entrada"), g.diametros_um, g.passante, { mode: "lines+markers", color: colors[0], hovertemplate: `${gettext("Entrada")}<br>D=%{x:.3f} µm<br>${gettext("Passante")}=%{y:.3f}%<extra></extra>` })];
  renderChart("chart-gran-entrada", traces, baseLayout(gettext("Granulometria acumulada passante (entrada)"), gettext("Diâmetro [µm]"), gettext("Passante [%]"), {
    yaxis: { title: gettext("Passante [%]"), range: [0, 100], gridcolor: "#edf3f6" },
  }), { x: gettext("Diâmetro [µm]"), y: gettext("Passante [%]") });
}

function plotHomogeneoFator() {
  const g = graficos.homogeneo_fator_atrito;
  if (!g) return;
  const traces = asArray(g.series).map((serie, idx) => {
    const seriesName = gettext(serie.name);
    return scatterLine(seriesName, serie.x, serie.y, {
    color: colors[idx % colors.length],
    dash: serie.dash,
    width: serie.width,
    hovertemplate: `${seriesName}<br>Re=%{x:.4g}<br>f=%{y:.5g}<extra></extra>`,
    });
  });
  traces.push(markerTrace(gettext("Operação"), g.operacao_x, g.operacao_y, g.operacao_label || `${gettext("Operação")}<br>Re=${nice(g.operacao_x)}<br>f=${nice(g.operacao_y, 5)}`, { color: "#e11d48" }));
  renderChart("chart-homogeneo-fator", traces, baseLayout(g.titulo ? gettext(g.titulo) : gettext("Fator de atrito homogêneo"), "Reynolds [-]", gettext("Fator de atrito [-]"), {
    xaxis: { title: "Reynolds [-]", type: "log", gridcolor: "#edf3f6" },
    yaxis: { title: gettext("Fator de atrito [-]"), type: "log", gridcolor: "#edf3f6" },
  }), { x: "Reynolds [-]", y: gettext("Fator de atrito [-]") });
}


function plotVscalc() {
  const gv = graficos.vscalc_velocidade;
  const gd = graficos.vscalc_diametro;
  const op = graficos.vscalc_operacao || {};
  if (gv) {
    const x = asArray(gv).map((p) => p.x);
    const traces = [
    scatterLine(gettext("V operacional"), x, asArray(gv).map((p) => p.Vop), { color: "#111827", dash: "dot" }),
      scatterLine("Vs", x, asArray(gv).map((p) => p.Vs), { color: colors[0] }),
      scatterLine("Vsm", x, asArray(gv).map((p) => p.Vsm), { color: colors[4] }),
    ];
    if (Number.isFinite(Number(op.velocidade))) {
      traces.push(markerTrace(gettext("Operação - Vs"), op.velocidade, op.Vs, `${gettext("Condição operacional")}<br>U=${nice(op.velocidade)} m/s<br>Vs=${nice(op.Vs)} m/s`, { color: "#e11d48", symbol: "diamond", size: 13 }));
      traces.push(markerTrace(gettext("Operação - Vsm"), op.velocidade, op.Vsm, `${gettext("Condição operacional")}<br>U=${nice(op.velocidade)} m/s<br>Vsm=${nice(op.Vsm)} m/s`, { color: "#7c2d12", symbol: "diamond-open", size: 13, showlegend: false }));
    }
    renderChart("chart-vscalc-velocidade", traces, baseLayout(gettext("Simulador de Deposição - variação da velocidade"), gettext("Velocidade média [m/s]"), gettext("Velocidade de deposição [m/s]"), {
      annotations: Number.isFinite(Number(op.velocidade)) ? [{
        x: op.velocidade,
        y: Math.max(Number(op.Vs || 0), Number(op.Vsm || 0)),
        text: `${gettext("Condição operacional")}<br>U = ${nice(op.velocidade)} m/s`,
        showarrow: true,
        ax: 42,
        ay: -42,
        bgcolor: "rgba(255,255,255,0.9)",
        bordercolor: "#d7e0e7",
        borderpad: 4,
        font: { color: "#12355b", size: 11 },
      }] : [],
    }), { x: gettext("Velocidade média [m/s]"), y: gettext("Velocidade [m/s]") });
  }
  if (gd) {
    const x = asArray(gd).map((p) => Number(p.x) * 1000);
    const dOp = Number(op.diametro_um || (Number(op.diametro_mm) * 1000));
    const traces = [
      scatterLine(gettext("V operacional"), x, asArray(gd).map((p) => p.Vop), { color: "#111827", dash: "dot" }),
      scatterLine("Vs", x, asArray(gd).map((p) => p.Vs), { color: colors[0] }),
      scatterLine("Vsm", x, asArray(gd).map((p) => p.Vsm), { color: colors[4] }),
    ];
    if (Number.isFinite(dOp)) {
      traces.push(markerTrace(gettext("Diâmetro operacional - Vs"), dOp, op.Vs, `${gettext("Diâmetro operacional")}=${nice(dOp, 0)} µm<br>Vs=${nice(op.Vs)} m/s`, { color: "#e11d48", symbol: "diamond", size: 13 }));
      traces.push(markerTrace(gettext("Diâmetro operacional - Vsm"), dOp, op.Vsm, `${gettext("Diâmetro operacional")}=${nice(dOp, 0)} µm<br>Vsm=${nice(op.Vsm)} m/s`, { color: "#7c2d12", symbol: "diamond-open", size: 13, showlegend: false }));
    }
    renderChart("chart-vscalc-diametro", traces, baseLayout(gettext("Simulador de Deposição - variação do diâmetro"), gettext("Diâmetro da partícula [µm]"), gettext("Velocidade de deposição [m/s]"), {
      shapes: Number.isFinite(dOp) ? [{
        type: "line",
        x0: dOp,
        x1: dOp,
        y0: 0,
        y1: 1,
        xref: "x",
        yref: "paper",
        line: { color: "#e11d48", width: 1.6, dash: "dot" },
      }] : [],
      annotations: Number.isFinite(dOp) ? [{
        x: dOp,
        y: Math.max(Number(op.Vs || 0), Number(op.Vsm || 0)),
        text: `${gettext("Diâmetro operacional")} = ${nice(dOp, 0)} µm`,
        showarrow: true,
        ax: 48,
        ay: -42,
        bgcolor: "rgba(255,255,255,0.9)",
        bordercolor: "#d7e0e7",
        borderpad: 4,
        font: { color: "#12355b", size: 11 },
      }] : [],
    }), { x: gettext("Diâmetro [µm]"), y: gettext("Velocidade [m/s]") });
  }
}

function plotFourCm() {
  const g = graficos.fourcm_curva_j;
  if (!g) return;
  const scale = g.scale || "log";
  const xType = scale === "log" ? "log" : "linear";
  const yType = scale === "linear" ? "linear" : "log";
  const traces = [
    scatterLine(gettext("Total"), g.velocidades, g.total, { color: colors[0], width: 3 }),
    scatterLine(gettext("Carrier"), g.velocidades, g.carrier, { color: colors[4] }),
    scatterLine(gettext("Pseudo-homogêneo"), g.velocidades, g.pseudo, { color: colors[2] }),
    scatterLine(gettext("Heterogêneo"), g.velocidades, g.heterogeneo, { color: colors[1] }),
    scatterLine(gettext("Estratificado"), g.velocidades, g.estratificado, { color: colors[5] }),
  ];
  renderChart("chart-fourcm-curva-j", traces, baseLayout(gettext("4CM - Curva J"), gettext("Velocidade [m/s]"), gettext("Perda de carga [m polpa/km]"), {
    xaxis: { title: gettext("Velocidade [m/s]"), type: xType, gridcolor: "#edf3f6" },
    yaxis: { title: gettext("Perda de carga [m polpa/km]"), type: yType, gridcolor: "#edf3f6" },
  }), { x: gettext("Velocidade [m/s]"), y: gettext("Perda de carga [m polpa/km]") });
}

const isVscalcResultado = Boolean(graficos.vscalc_velocidade || graficos.vscalc_diametro);
const isHomogeneoResultado = Boolean(graficos.homogeneo_fator_atrito);

if (isVscalcResultado) {
  plotVscalc();
} else if (isHomogeneoResultado) {
  plotPerda();
  plotHomogeneoFator();
} else {
  plotConcentracao();
  plotC0Ca();
  plotCv();
  plotPerda();
  plotGranulometriaModelo();
  plotGranulometriaEntrada();
  plotTwoLayerSection();
}

function formatExcelCell(value) {
  if (value === null || value === undefined || value === "") return "";
  const number = Number(value);
  if (Number.isFinite(number)) return String(value).replace(".", ",");
  return String(value);
}

function tableFromSeries(xHeader, xValues, series) {
  const x = asArray(xValues);
  const cleanSeries = asArray(series).filter((item) => item && item.name && Array.isArray(item.values));
  const rowCount = Math.max(x.length, ...cleanSeries.map((item) => item.values.length), 0);
  const rows = [[xHeader, ...cleanSeries.map((item) => item.name)]];
  for (let i = 0; i < rowCount; i += 1) {
    rows.push([x[i], ...cleanSeries.map((item) => item.values[i])]);
  }
  return rows.map((row) => row.map(formatExcelCell).join("\t")).join("\n");
}

function buildExportTables() {
  const exports = [];
  const isHomogeneo = Boolean(graficos.homogeneo_fator_atrito);
  if (graficos.vscalc_velocidade) {
    exports.push({ key: "vscalc_velocidade", title: gettext("Simulador de Deposição - variação da velocidade"), text: tableFromSeries(gettext("Velocidade [m/s]"), asArray(graficos.vscalc_velocidade).map((p) => p.x), [{ name: "Vop", values: asArray(graficos.vscalc_velocidade).map((p) => p.Vop) }, { name: "Vs", values: asArray(graficos.vscalc_velocidade).map((p) => p.Vs) }, { name: "Vsm", values: asArray(graficos.vscalc_velocidade).map((p) => p.Vsm) }]) });
  }
  if (graficos.vscalc_diametro) {
    exports.push({ key: "vscalc_diametro", title: gettext("Simulador de Deposição - variação do diâmetro"), text: tableFromSeries(gettext("Diâmetro [µm]"), asArray(graficos.vscalc_diametro).map((p) => Number(p.x) * 1000), [{ name: "Vop", values: asArray(graficos.vscalc_diametro).map((p) => p.Vop) }, { name: "Vs", values: asArray(graficos.vscalc_diametro).map((p) => p.Vs) }, { name: "Vsm", values: asArray(graficos.vscalc_diametro).map((p) => p.Vsm) }]) });
    return exports;
  }

  if (graficos.concentracao_vertical) {
    const g = graficos.concentracao_vertical;
    exports.push({ key: "concentracao_vertical", title: gettext("Perfil vertical de concentração"), text: tableFromSeries("phi total", g.x_phi, [{ name: "y/D", values: g.yD }]) });
  }
  if (graficos.c0ca) {
    const g = graficos.c0ca;
    exports.push({
      key: "c0ca",
      title: gettext("C/Ca por classe granulométrica"),
      text: tableFromSeries(gettext("Velocidade [m/s]"), g.velocidades, asArray(g.series).map((serie) => ({ name: `${Number(serie.diametro_um).toFixed(0)} um`, values: serie.valores }))),
    });
  }
  if (graficos.cv_veiculo) {
    const g = graficos.cv_veiculo;
    exports.push({ key: "cv_veiculo", title: gettext("Sólidos suspensos vs velocidade"), text: tableFromSeries(gettext("Velocidade [m/s]"), g.velocidades, [{ name: "φ_VV / φ_V [%]", values: g.percentual }]) });
  }
  if (graficos.perda_carga) {
    const g = graficos.perda_carga;
    const series = [
      { name: `${gettext("WASP Modificado")} [${gettext("m coluna de polpa/km")}]`, values: g.polpa },
      { name: gettext("Água [m/km]"), values: g.agua },
    ];
    if (Array.isArray(g.fourcm_total) && g.fourcm_total.length) series.splice(1, 0, { name: `${gettext("4CM")} [${gettext("m coluna de polpa/km")}]`, values: g.fourcm_total });
    if (Array.isArray(g.arraste) && g.arraste.length) series.push({ name: gettext("Arraste [m/km]"), values: g.arraste });
    exports.push({ key: "perda_carga", title: gettext("Perda de carga vs velocidade"), text: tableFromSeries(gettext("Velocidade [m/s]"), g.velocidades, series) });
  }
  if (graficos.homogeneo_fator_atrito) {
    const g = graficos.homogeneo_fator_atrito;
    asArray(g.series).forEach((serie) => {
      exports.push({ key: `homogeneo_fator_atrito_${serie.name}`, title: `${gettext(g.titulo)} - ${gettext(serie.name)}`, text: tableFromSeries("Reynolds [-]", serie.x, [{ name: gettext("Fator de atrito [-]"), values: serie.y }]) });
    });
    exports.push({
      key: "homogeneo_fator_atrito_operacao",
      title: `${gettext(g.titulo)} - ${gettext("operação por velocidade")}`,
      text: tableFromSeries(gettext("Velocidade [m/s]"), graficos.perda_carga ? graficos.perda_carga.velocidades : [], [
        { name: "Reynolds [-]", values: g.reynolds_velocidades },
        { name: gettext("Fator de atrito [-]"), values: g.fatores_velocidades },
        { name: gettext("Perda de carga [m/km]"), values: graficos.perda_carga ? graficos.perda_carga.polpa : [] },
      ]),
    });
  }
  if (isHomogeneo) return exports.filter((item) => item.key === "perda_carga" || item.key.startsWith("homogeneo_fator_atrito"));
  if (graficos.granulometria_passante_modelo) {
    const g = graficos.granulometria_passante_modelo;
    exports.push({ key: "granulometria_passante_modelo", title: gettext("Granulometria acumulada passante (modelo)"), text: tableFromSeries(gettext("Diâmetro [um]"), g.diametros_um, [
      { name: "y/D = 0,05 [%]", values: g.yD_005 },
      { name: "y/D = 0,50 [%]", values: g.yD_050 },
      { name: "y/D = 0,95 [%]", values: g.yD_095 },
    ]) });
  }
  if (graficos.granulometria_passante_entrada) {
    const g = graficos.granulometria_passante_entrada;
    exports.push({ key: "granulometria_passante_entrada", title: gettext("Granulometria acumulada passante (entrada)"), text: tableFromSeries(gettext("Diâmetro [um]"), g.diametros_um, [{ name: gettext("Passante [%]"), values: g.passante }]) });
  }
  return exports;
}

function setupChartExports() {
  const select = document.getElementById("export-chart-select");
  const copyButton = document.getElementById("copy-chart-data");
  const status = document.getElementById("export-chart-status");
  if (!select || !copyButton) return;
  const exports = buildExportTables();
  select.innerHTML = exports.map((item, index) => `<option value="${index}">${item.title}</option>`).join("");
  copyButton.addEventListener("click", async () => {
    const selected = exports[Number(select.value)] || exports[0];
    const text = selected ? selected.text : "";
    let copied = false;
    try {
      if (!navigator.clipboard) throw new Error("Clipboard API indisponível");
      await navigator.clipboard.writeText(text);
      copied = true;
    } catch (err) {
      const textarea = document.createElement("textarea");
      textarea.value = text;
      textarea.style.position = "fixed";
      textarea.style.opacity = "0";
      document.body.appendChild(textarea);
      textarea.select();
      try {
        copied = document.execCommand("copy");
      } catch (fallbackError) {
        copied = false;
      } finally {
        textarea.remove();
      }
    }
    copyButton.textContent = copied ? gettext("Copiado") : gettext("Erro ao copiar");
    if (status) {
      status.textContent = copied
        ? `${selected ? selected.title : gettext("Dados")} ${gettext("copiados. Cole diretamente no Excel.")}`
        : gettext("Não foi possível copiar os dados.");
    }
    setTimeout(() => { copyButton.textContent = gettext("Copiar para Excel"); }, 1400);
  });
}

function resizeAllPlots() {
  if (!hasPlotly()) return;
  document.querySelectorAll(".chart .js-plotly-plot").forEach((plot) => {
    Plotly.Plots.resize(plot);
  });
}

window.addEventListener("load", () => {
  resizeAllPlots();
  setTimeout(resizeAllPlots, 150);
  setTimeout(resizeAllPlots, 500);
});
window.addEventListener("resize", resizeAllPlots);

setupChartExports();
