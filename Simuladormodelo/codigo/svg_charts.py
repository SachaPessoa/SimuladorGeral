import html
import math


COLORS = ["#16758f", "#b45309", "#2563eb", "#7c3aed", "#15803d", "#be123c", "#0f766e", "#a16207", "#4338ca", "#9333ea"]


def _pairs(x_values, y_values):
    out = []
    for x, y in zip(x_values or [], y_values or []):
        try:
            xf = float(x)
            yf = float(y)
        except (TypeError, ValueError):
            continue
        if math.isfinite(xf) and math.isfinite(yf):
            out.append((xf, yf))
    return out


def _fmt(v):
    if v is None:
        return ""
    v = float(v)
    if not math.isfinite(v):
        return ""
    if abs(v) >= 100:
        return f"{v:.0f}"
    if abs(v) >= 10:
        return f"{v:.2f}"
    if abs(v) >= 1:
        return f"{v:.2f}".rstrip("0").rstrip(".")
    return f"{v:.2f}".rstrip("0").rstrip(".")


def _fmt_axis(v):
    if v is None:
        return ""
    v = float(v)
    if not math.isfinite(v):
        return ""
    if abs(v) >= 10000 or (0 < abs(v) < 0.01):
        return f"{v:.1e}"
    return _fmt(v)


def _transform_point(x, y, log_x, log_y):
    try:
        xf = float(x)
        yf = float(y)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(xf) or not math.isfinite(yf):
        return None
    if log_x:
        if xf <= 0:
            return None
        xf = math.log10(xf)
    if log_y:
        if yf <= 0:
            return None
        yf = math.log10(yf)
    return xf, yf


def _marker_label(marker, x_raw, y_raw):
    label = marker.get("label")
    if label:
        return label
    name = marker.get("name", "Operação")
    return f"{name}: x={_fmt(x_raw)}; y={_fmt(y_raw)}"


def _svg_dash(dash):
    if dash == "dot":
        return ' stroke-dasharray="2 5"'
    if dash == "dashdot":
        return ' stroke-dasharray="8 4 2 4"'
    if dash:
        return ' stroke-dasharray="7 5"'
    return ""


def _velocity_ticks(values):
    vals = []
    for v in values or []:
        try:
            vf = float(v)
        except (TypeError, ValueError):
            continue
        if vf > 0:
            vals.append(vf)
    if not vals:
        return None
    min_v = min(vals)
    max_v = max(vals)
    ticks = []
    for k in range(1, 10):
        v = k / 10
        if min_v <= v <= max_v:
            ticks.append(v)
    start = max(1, math.ceil(min_v))
    end = math.floor(max_v)
    ticks.extend(float(v) for v in range(start, end + 1))
    if not ticks:
        ticks = [min_v, max_v]
    return sorted(set(round(v, 10) for v in ticks))


def _integer_velocity_ticks(values):
    vals = []
    for v in values or []:
        try:
            vf = float(v)
        except (TypeError, ValueError):
            continue
        if math.isfinite(vf):
            vals.append(vf)
    if not vals:
        return None
    start = math.ceil(min(vals))
    end = math.floor(max(vals))
    if start > end:
        return [min(vals), max(vals)]
    return [float(v) for v in range(start, end + 1)]


def _log_ticks_from_values(values):
    vals = []
    for v in values or []:
        try:
            vf = float(v)
        except (TypeError, ValueError):
            continue
        if math.isfinite(vf) and vf > 0:
            vals.append(vf)
    if not vals:
        return None

    min_v = min(vals)
    max_v = max(vals)
    start_exp = math.floor(math.log10(min_v))
    end_exp = math.ceil(math.log10(max_v))
    ticks = []
    for exp in range(start_exp, end_exp + 1):
        for mult in (1, 2, 5):
            tick = mult * (10 ** exp)
            if min_v <= tick <= max_v:
                ticks.append(float(tick))
    return sorted(set(ticks)) or None


def _valid_ticks(ticks, min_v, max_v, log_axis):
    if not ticks:
        return None
    out = []
    for raw in ticks:
        try:
            raw = float(raw)
        except (TypeError, ValueError):
            continue
        if not math.isfinite(raw):
            continue
        if log_axis:
            if raw <= 0:
                continue
            value = math.log10(raw)
        else:
            value = raw
        if min_v <= value <= max_v:
            out.append((value, raw))
    return out or None


def line_chart(
    title,
    x_title,
    y_title,
    series,
    width=760,
    height=430,
    log_x=False,
    log_y=False,
    markers=None,
    hlines=None,
    x_range=None,
    y_range=None,
    x_ticks=None,
    y_ticks=None,
    legend_position="top-right",
    pipe_circle=False,
    point_labels=False,
):
    markers = markers or []
    hlines = hlines or []
    normalized = []
    marker_points = []
    hline_values = []

    for item in series:
        pts = _pairs(item.get("x"), item.get("y"))
        if log_x:
            pts = [(math.log10(x), y) for x, y in pts if x > 0]
        if log_y:
            pts = [(x, math.log10(y)) for x, y in pts if y > 0]
        if len(pts) > 1:
            normalized.append({
                "name": item.get("name", ""),
                "points": pts,
                "dash": item.get("dash"),
                "width": item.get("width", 2.4),
            })

    for marker in markers:
        raw_x = marker.get("x")
        raw_y = marker.get("y")
        point = _transform_point(raw_x, raw_y, log_x, log_y)
        if point is not None:
            marker_points.append({
                "name": marker.get("name", "Operação"),
                "label": _marker_label(marker, float(raw_x), float(raw_y)),
                "point": point,
                "color": marker.get("color", "#e11d48"),
                "label_offset": marker.get("label_offset", 0),
            })

    legend_items = normalized[:10]
    legend_cols = 3 if len(legend_items) > 2 else max(len(legend_items), 1)
    legend_rows = math.ceil(len(legend_items) / legend_cols) if legend_items else 0
    marker_cols = 3 if len(marker_points) > 4 else (2 if len(marker_points) > 1 else 1)
    marker_rows = math.ceil(len(marker_points) / marker_cols) if marker_points else 0
    extra_marker_bottom = 18 * marker_rows + 16 if marker_points else 0
    extra_legend_bottom = 22 * legend_rows + 16 if legend_position == "below" and legend_items else 0
    height = max(height, 450 + extra_marker_bottom + extra_legend_bottom)
    margin = {"top": 54, "right": 28, "bottom": 62 + extra_marker_bottom + extra_legend_bottom, "left": 82}
    plot_w = width - margin["left"] - margin["right"]
    plot_h = height - margin["top"] - margin["bottom"]

    for hline in hlines:
        point = _transform_point(1, hline.get("y"), False, log_y)
        if point is not None:
            hline_values.append({"y": point[1], "name": hline.get("name", ""), "color": hline.get("color", "#2563eb")})

    if not normalized and not marker_points:
        return f'<div class="chart-empty">Sem dados para {html.escape(title)}</div>'

    all_pts = [p for item in normalized for p in item["points"]] + [m["point"] for m in marker_points]
    for line in hline_values:
        if all_pts:
            all_pts.append((all_pts[0][0], line["y"]))

    if x_range:
        min_x, max_x = x_range
        if log_x:
            min_x, max_x = math.log10(min_x), math.log10(max_x)
    else:
        min_x = min(p[0] for p in all_pts)
        max_x = max(p[0] for p in all_pts)

    if y_range:
        min_y, max_y = y_range
        if log_y:
            min_y, max_y = math.log10(min_y), math.log10(max_y)
    else:
        min_y = min(p[1] for p in all_pts)
        max_y = max(p[1] for p in all_pts)
        y_pad = (max_y - min_y) * 0.08 if max_y != min_y else 1
        min_y -= y_pad
        max_y += y_pad

    if min_x == max_x:
        max_x = min_x + 1
    if min_y == max_y:
        max_y = min_y + 1

    def sx(x):
        return margin["left"] + ((x - min_x) / (max_x - min_x)) * plot_w

    def sy(y):
        return margin["top"] + plot_h - ((y - min_y) / (max_y - min_y)) * plot_h

    x_tick_items = _valid_ticks(x_ticks, min_x, max_x, log_x)
    if not x_tick_items:
        x_tick_items = [(min_x + (max_x - min_x) * i / 4, None) for i in range(5)]
    y_tick_items = _valid_ticks(y_ticks, min_y, max_y, log_y)
    if not y_tick_items:
        y_tick_items = [(max_y - (max_y - min_y) * i / 4, None) for i in range(5)]

    def raw_x(v, raw):
        return raw if raw is not None else (10 ** v if log_x else v)

    def raw_y(v, raw):
        return raw if raw is not None else (10 ** v if log_y else v)

    x_tick_y = margin["top"] + plot_h + 22
    x_axis_title_y = x_tick_y + 28
    annotation_y0 = x_axis_title_y + 22

    parts = [
        f'<svg viewBox="0 0 {width} {height}" role="img" aria-label="{html.escape(title)}">',
        f'<text x="{margin["left"]}" y="25" class="chart-title">{html.escape(title)}</text>',
        f'<rect x="{margin["left"]}" y="{margin["top"]}" width="{plot_w}" height="{plot_h}" class="plot-bg" />',
    ]

    if pipe_circle:
        cx = sx(0.5)
        cy = sy(0.5)
        rx = abs(sx(1) - sx(0)) / 2
        ry = abs(sy(0) - sy(1)) / 2
        parts.append(f'<ellipse cx="{cx:.2f}" cy="{cy:.2f}" rx="{rx:.2f}" ry="{ry:.2f}" fill="none" stroke="#8a96a3" stroke-width="1.6" stroke-dasharray="6 4"><title>Seção da tubulação</title></ellipse>')

    for xv, raw in x_tick_items:
        gx = sx(xv)
        parts.append(f'<line x1="{gx:.2f}" y1="{margin["top"]}" x2="{gx:.2f}" y2="{margin["top"] + plot_h}" class="grid-line" />')
        parts.append(f'<text x="{gx:.2f}" y="{x_tick_y:.2f}" class="tick" text-anchor="middle">{_fmt_axis(raw_x(xv, raw))}</text>')
    for yv, raw in y_tick_items:
        gy = sy(yv)
        parts.append(f'<line x1="{margin["left"]}" y1="{gy:.2f}" x2="{margin["left"] + plot_w}" y2="{gy:.2f}" class="grid-line" />')
        parts.append(f'<text x="{margin["left"] - 10}" y="{gy + 4:.2f}" class="tick" text-anchor="end">{_fmt_axis(raw_y(yv, raw))}</text>')

    parts.append(f'<line x1="{margin["left"]}" y1="{margin["top"] + plot_h}" x2="{margin["left"] + plot_w}" y2="{margin["top"] + plot_h}" class="axis-line" />')
    parts.append(f'<line x1="{margin["left"]}" y1="{margin["top"]}" x2="{margin["left"]}" y2="{margin["top"] + plot_h}" class="axis-line" />')

    labeled_points = []
    for idx, item in enumerate(normalized):
        color = COLORS[idx % len(COLORS)]
        dash = _svg_dash(item.get("dash"))
        d = " ".join(
            f'{"M" if pos == 0 else "L"} {sx(x):.2f} {sy(y):.2f}'
            for pos, (x, y) in enumerate(item["points"])
        )
        parts.append(f'<path d="{d}" fill="none" stroke="{color}" stroke-width="{item["width"]}"{dash} stroke-linecap="round" stroke-linejoin="round"><title>{html.escape(item["name"])}</title></path>')
        if point_labels:
            for x, y in item["points"]:
                px = sx(x)
                py = sy(y)
                raw_x_value = 10 ** x if log_x else x
                raw_y_value = 10 ** y if log_y else y
                labeled_points.append(
                    f'<circle cx="{px:.2f}" cy="{py:.2f}" r="3.8" fill="{color}" stroke="white" stroke-width="1.3"><title>{html.escape(item["name"])}: D={_fmt(raw_x_value)} µm; valor={_fmt(raw_y_value)}%</title></circle>'
                )

    parts.extend(labeled_points)

    for line in hline_values:
        y = sy(line["y"])
        parts.append(f'<line x1="{margin["left"]}" y1="{y:.2f}" x2="{margin["left"] + plot_w}" y2="{y:.2f}" stroke="{line["color"]}" stroke-dasharray="6 4" stroke-width="1.6" />')
        if line["name"]:
            parts.append(f'<text x="{margin["left"] + plot_w - 6}" y="{y - 6:.2f}" class="marker-label" text-anchor="end">{html.escape(line["name"])}</text>')

    for marker in marker_points:
        x, y = marker["point"]
        px = sx(x)
        py = sy(y)
        parts.append(f'<circle cx="{px:.2f}" cy="{py:.2f}" r="6" fill="{marker["color"]}" stroke="white" stroke-width="2"><title>{html.escape(marker["label"])}</title></circle>')
        parts.append(f'<circle cx="{px:.2f}" cy="{py:.2f}" r="10" fill="none" stroke="{marker["color"]}" stroke-width="1.4" opacity="0.32" />')

    for idx, marker in enumerate(marker_points):
        col = idx % marker_cols
        row = idx // marker_cols
        col_w = plot_w / marker_cols
        label_x = margin["left"] + col * col_w
        label_y = annotation_y0 + row * 18
        parts.append(f'<text x="{label_x:.2f}" y="{label_y:.2f}" class="marker-label">{html.escape(marker["label"])}</text>')

    if legend_position == "below":
        legend_col_w = plot_w / legend_cols if legend_cols else plot_w
        legend_y0 = annotation_y0 + marker_rows * 18 + (18 if marker_points else 0)
        for idx, item in enumerate(legend_items):
            color = COLORS[idx % len(COLORS)]
            dash = _svg_dash(item.get("dash"))
            col = idx % legend_cols
            row = idx // legend_cols
            legend_x = margin["left"] + col * legend_col_w
            ly = legend_y0 + row * 22
            parts.append(f'<line x1="{legend_x}" y1="{ly}" x2="{legend_x + 19}" y2="{ly}" stroke="{color}" stroke-width="3"{dash} />')
            parts.append(f'<text x="{legend_x + 25}" y="{ly + 4}" class="legend">{html.escape(item["name"])}</text>')
    elif legend_position == "bottom-right":
        legend_x = width - 190
        legend_y0 = height - 28 - 18 * (len(legend_items) - 1)
        for idx, item in enumerate(legend_items):
            color = COLORS[idx % len(COLORS)]
            ly = legend_y0 + idx * 18
            parts.append(f'<line x1="{legend_x}" y1="{ly}" x2="{legend_x + 19}" y2="{ly}" stroke="{color}" stroke-width="3" />')
            parts.append(f'<text x="{legend_x + 25}" y="{ly + 4}" class="legend">{html.escape(item["name"])}</text>')
    else:
        legend_x = width - 145
        legend_y0 = margin["top"]
        for idx, item in enumerate(legend_items):
            color = COLORS[idx % len(COLORS)]
            ly = legend_y0 + idx * 18
            parts.append(f'<line x1="{legend_x}" y1="{ly}" x2="{legend_x + 19}" y2="{ly}" stroke="{color}" stroke-width="3" />')
            parts.append(f'<text x="{legend_x + 25}" y="{ly + 4}" class="legend">{html.escape(item["name"])}</text>')

    parts.append(f'<text x="{margin["left"] + plot_w / 2:.2f}" y="{x_axis_title_y:.2f}" class="axis-title" text-anchor="middle">{html.escape(x_title)}</text>')
    parts.append(f'<text transform="translate(18 {margin["top"] + plot_h / 2:.2f}) rotate(-90)" class="axis-title" text-anchor="middle">{html.escape(y_title)}</text>')
    parts.append("</svg>")
    return "\n".join(parts)


def _operation_markers_by_class(chart_data):
    velocidades = chart_data.get("velocidades") or []
    operacao_x = chart_data.get("operacao_x")
    if not velocidades or operacao_x is None:
        return []
    idx = min(range(len(velocidades)), key=lambda i: abs(float(velocidades[i]) - float(operacao_x)))
    markers = []
    for pos, serie in enumerate(chart_data.get("series", [])):
        valores = serie.get("valores") or []
        if idx >= len(valores):
            continue
        diametro = float(serie.get("diametro_um") or 0)
        y = float(valores[idx])
        markers.append({
            "name": f"{diametro:.0f} µm",
            "x": velocidades[idx],
            "y": y,
            "label": f'{diametro:.0f} µm: {y:.2f}% em U={float(velocidades[idx]):.2f}',
            "color": COLORS[pos % len(COLORS)],
            "label_offset": (pos % 5) * 12,
        })
    return markers


def charts_from_result(resultado):
    g = resultado.get("graficos", {})
    resumo = resultado.get("resumo", {})
    charts = []

    if resumo.get("modelo_escoamento") == "homogeneo":
        pc = g.get("perda_carga", {})
        charts = [line_chart(
            "Perda de carga - modelo homogêneo",
            "Velocidade [m/s]",
            "Perda de carga [m/km]",
            [
                {"name": "Polpa homogênea", "x": pc.get("velocidades"), "y": pc.get("polpa")},
                {"name": "Água", "x": pc.get("velocidades"), "y": pc.get("agua"), "dash": "dot"},
            ],
            log_x=True,
            log_y=True,
            x_ticks=_velocity_ticks(pc.get("velocidades")),
            markers=[{
                "name": "Operação",
                "x": pc.get("operacao_x"),
                "y": pc.get("operacao_y"),
                "label": f'Ponto de operação: U={float(pc.get("operacao_x") or 0):.2f}; ΔP={float(pc.get("operacao_y") or 0):.2f} m/km',
            }],
            legend_position="below",
        )]
        hf = g.get("homogeneo_fator_atrito")
        if hf:
            charts.append(line_chart(
                hf.get("titulo", "Fator de atrito homogêneo"),
                "Reynolds [-]",
                "Fator de atrito [-]",
                hf.get("series", []),
                log_x=True,
                log_y=True,
                markers=[{
                    "name": "Operação",
                    "x": hf.get("operacao_x"),
                    "y": hf.get("operacao_y"),
                    "label": hf.get("operacao_label", ""),
                }],
                legend_position="below",
            ))
        return charts

    cv = g.get("concentracao_vertical", {})
    charts.append(line_chart(
        "Perfil vertical de concentração",
        "φ total",
        "y/D",
        [{"name": "φ total", "x": cv.get("x_phi"), "y": cv.get("yD")}],
        markers=[{
            "name": "φ em y/D=0,1",
            "x": cv.get("phi_ref"),
            "y": cv.get("phi_ref_yD", 0.1),
            "label": f'Ponto de referência: φ={float(cv.get("phi_ref") or 0):.4f}; y/D={float(cv.get("phi_ref_yD") or 0.1):.3f}',
        }],
        hlines=[{"name": f'y/D depósito = {100 * float(cv.get("altura_deposito") or 0):.1f}%', "y": cv.get("altura_deposito")}],
        x_range=(0, 1),
        y_range=(0, 1),
        width=520,
        height=598,
        pipe_circle=True,
        legend_position="below",
    ))

    c0ca = g.get("c0ca", {})
    charts.append(line_chart(
        "C/Ca por classe granulométrica",
        "Velocidade [m/s]",
        "C/Ca [%]",
        [{"name": f'{s.get("diametro_um", 0):.0f} µm', "x": c0ca.get("velocidades"), "y": s.get("valores")} for s in c0ca.get("series", [])],
        markers=_operation_markers_by_class(c0ca),
        y_range=(0, 100),
        x_ticks=_integer_velocity_ticks(c0ca.get("velocidades")),
        legend_position="below",
    ))

    cvv = g.get("cv_veiculo", {})
    charts.append(line_chart(
        "Sólidos suspensos vs velocidade",
        "Velocidade [m/s]",
        "Cv veículo / Cv total [%]",
        [{"name": "Cv veículo", "x": cvv.get("velocidades"), "y": cvv.get("percentual")}],
        log_x=True,
        log_y=True,
        x_ticks=_velocity_ticks(cvv.get("velocidades")),
        markers=[{
            "name": "Operação",
            "x": cvv.get("operacao_x"),
            "y": cvv.get("operacao_y"),
            "label": f'Ponto de operação: U={float(cvv.get("operacao_x") or 0):.2f}; Cv={float(cvv.get("operacao_y") or 0):.2f}%',
        }],
        legend_position="below",
    ))

    pc = g.get("perda_carga", {})
    limite_hom_het = pc.get("limite_hom_het") or {}
    transicao_lt = pc.get("transicao_laminar_turbulento") or {}
    perda_carga_markers = [{
        "name": "Operação",
        "x": pc.get("operacao_x"),
        "y": pc.get("operacao_y"),
        "label": f'Ponto de operação: U={float(pc.get("operacao_x") or 0):.2f}; ΔP={float(pc.get("operacao_y") or 0):.2f} m/km',
    }]
    if transicao_lt:
        perda_carga_markers.append({
            "name": "Transição L-T",
            "x": transicao_lt.get("velocidade"),
            "y": transicao_lt.get("perda_carga"),
            "color": "#7c2d12",
            "label": (
                f'Transição L-T: U={float(transicao_lt.get("velocidade") or 0):.2f}; '
                f'ΔP={float(transicao_lt.get("perda_carga") or 0):.1f} m/km'
            ),
        })
    if limite_hom_het:
        perda_carga_markers.append({
            "name": "Limite Hom-Het",
            "x": limite_hom_het.get("velocidade"),
            "y": limite_hom_het.get("perda_carga"),
            "color": "#111827",
            "label": (
                f'Limite Hom-Het: U={float(limite_hom_het.get("velocidade") or 0):.2f}; '
                f'ΔP={float(limite_hom_het.get("perda_carga") or 0):.1f} m/km; '
                f'Arraste={float(limite_hom_het.get("frac_arraste_percent") or 0):.1f}%'
            ),
        })
    charts.append(line_chart(
        "Perda de carga vs velocidade",
        "Velocidade [m/s]",
        "Perda de carga [m/km]",
        [
            {"name": "Polpa", "x": pc.get("velocidades"), "y": pc.get("polpa")},
            {"name": "Água", "x": pc.get("velocidades"), "y": pc.get("agua"), "dash": "dot"},
        ],
        log_x=True,
        log_y=True,
        x_ticks=_velocity_ticks(pc.get("velocidades")),
        markers=perda_carga_markers,
        legend_position="below",
    ))

    hf = g.get("homogeneo_fator_atrito")
    if hf:
        charts.append(line_chart(
            hf.get("titulo", "Fator de atrito homogêneo"),
            "Reynolds [-]",
            "Fator de atrito [-]",
            hf.get("series", []),
            log_x=True,
            log_y=True,
            markers=[{
                "name": "Operação",
                "x": hf.get("operacao_x"),
                "y": hf.get("operacao_y"),
                "label": hf.get("operacao_label", ""),
            }],
            legend_position="below",
        ))

    gc = g.get("granulometria_concentracao", {})
    charts.append(line_chart(
        "Concentração absoluta por classe",
        "Diâmetro [µm]",
        "Concentração absoluta [%]",
        [
            {"name": "y/D = 0,05", "x": gc.get("diametros_um"), "y": [100 * v for v in gc.get("yD_005", [])]},
            {"name": "y/D = 0,50", "x": gc.get("diametros_um"), "y": [100 * v for v in gc.get("yD_050", [])]},
            {"name": "y/D = 0,95", "x": gc.get("diametros_um"), "y": [100 * v for v in gc.get("yD_095", [])]},
        ],
        log_x=False,
        legend_position="below",
        point_labels=True,
    ))

    gp = g.get("granulometria_passante_modelo", {})
    charts.append(line_chart(
        "Granulometria acumulada passante (modelo)",
        "Diâmetro [µm]",
        "Passante [%]",
        [
            {"name": "y/D = 0,05", "x": gp.get("diametros_um"), "y": gp.get("yD_005")},
            {"name": "y/D = 0,50", "x": gp.get("diametros_um"), "y": gp.get("yD_050")},
            {"name": "y/D = 0,95", "x": gp.get("diametros_um"), "y": gp.get("yD_095")},
        ],
        log_x=False,
        y_range=(0, 100),
        legend_position="below",
        point_labels=True,
    ))

    ge = g.get("granulometria_passante_entrada", {})
    charts.append(line_chart(
        "Granulometria acumulada passante (entrada)",
        "Diâmetro [µm]",
        "Passante [%]",
        [{"name": "Entrada", "x": ge.get("diametros_um"), "y": ge.get("passante")}],
        log_x=False,
        y_range=(0, 100),
        legend_position="below",
        point_labels=True,
    ))

    return charts
