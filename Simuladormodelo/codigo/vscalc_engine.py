import math

from django.utils.translation import gettext as _

from .calculos import _json_safe, normalizar_entradas


def _f_darcy(reynolds, eps, diameter):
    if reynolds <= 0:
        return math.nan
    if reynolds < 2000:
        return 64.0 / reynolds
    return 0.25 / (math.log10(eps / (3.7 * diameter) + 5.74 / (reynolds ** 0.9)) ** 2)


def _cd_turton_levenspiel(reynolds):
    if reynolds <= 0:
        return math.inf
    return (24.0 / reynolds) * (1.0 + 0.173 * reynolds ** 0.657) + 0.413 / (1.0 + 16300.0 * reynolds ** -1.09)


def _vt_stokes(d_mm, rho_s, rho_l, mu):
    d = d_mm / 1000.0
    return 9.81 * (rho_s - rho_l) * d * d / (18.0 * mu)


def _vt_tl(d_mm, rho_s, rho_l, mu):
    d = d_mm / 1000.0
    vt = min(max(_vt_stokes(d_mm, rho_s, rho_l, mu), 1e-9), 10.0)
    for _ in range(200):
        re_p = rho_l * vt * d / mu
        cd = _cd_turton_levenspiel(re_p)
        vt_new = math.sqrt((4.0 * 9.81 * d * (rho_s - rho_l)) / (3.0 * rho_l * cd))
        if abs(vt_new - vt) <= 1e-10 * max(1.0, vt_new):
            vt = vt_new
            break
        vt = 0.5 * vt + 0.5 * vt_new
    re_p = rho_l * vt * d / mu
    return vt, re_p, _cd_turton_levenspiel(re_p)


def _bisect_root(func, lo, hi):
    flo = func(lo)
    fhi = func(hi)
    tries = 0
    while flo * fhi > 0 and tries < 60:
        lo *= 0.5
        hi *= 2.0
        flo = func(lo)
        fhi = func(hi)
        tries += 1
    if flo * fhi > 0:
        raise ValueError("Nao foi possivel fechar a raiz do limite Vsmmax.")
    for _ in range(100):
        mid = 0.5 * (lo + hi)
        fmid = func(mid)
        if abs(fmid) < 1e-10 or abs(hi - lo) < 1e-10:
            return mid
        if flo * fmid <= 0:
            hi = mid
            fhi = fmid
        else:
            lo = mid
            flo = fmid
    return 0.5 * (lo + hi)


def _delta_d_inclinacao(theta_rad):
    if theta_rad >= 0:
        return 0.75 * theta_rad - 0.50 * (0.6366 * theta_rad) ** 2 / (1.0 - 0.6366 * theta_rad)
    return 0.75 * theta_rad - 0.02 * (2.29 * theta_rad) ** 2 / (1.0 - 2.29 * theta_rad)


def _compute(p):
    g = 9.81
    sf = p["rho_l"] / 1000.0
    ss = p["rho_s"] / 1000.0
    nu = p["mu"] / p["rho_l"]
    d_m = p["d_mm"] / 1000.0
    if p["D"] <= 0 or p["eps"] < 0 or p["d_mm"] <= 0 or p["Vflow"] <= 0 or p["rho_s"] <= p["rho_l"] or p["rho_l"] <= 0 or p["mu"] <= 0 or p["cvd"] < 0 or p["cvd"] >= 1 or p["cvb"] <= 0 or p["cvb"] >= 1 or p["cvd"] > p["cvb"] or p["mus"] <= 0:
        raise ValueError("Verifique entradas do VSCALC+: ha valor fora da faixa fisica.")
    stokes = _vt_stokes(p["d_mm"], p["rho_s"], p["rho_l"], p["mu"])
    vt_tl, re_tl, cd_tl = _vt_tl(p["d_mm"], p["rho_s"], p["rho_l"], p["mu"])
    vts = stokes if p["drag"] == "stokes" else vt_tl
    re_p = p["rho_l"] * vts * d_m / p["mu"]
    cd = 24.0 / max(re_p, 1e-12) if p["drag"] == "stokes" else cd_tl
    cds = (4.0 / 3.0) * ((p["rho_s"] - p["rho_l"]) / p["rho_l"]) * g * d_m / (vts * vts)
    density_term = p["mus"] * (ss / sf - 1.0) / 0.66
    v_wilson = 8.8 * density_term ** 0.55 * p["D"] ** 0.7 * p["d_mm"] ** 1.75 / (p["d_mm"] ** 2 + 0.11 * p["D"] ** 0.7)
    v_thomas = 9.0 * (g * nu * (ss / sf - 1.0)) ** 0.37 * (p["D"] / nu) ** 0.11
    v_mwj = math.nan
    if p["d_mm"] <= 0.15:
        ratio = d_m / (cds * p["D"])
        v_mwj = (2.0 + 0.305 * math.log10(ratio) + 0.00011 * ratio ** -0.489 - 0.044 * (10000000.0 * ratio) ** -1.06) * math.sqrt(2.0 * g * p["D"] * (ss / sf - 1.0))
    re_pipe = p["rho_l"] * p["Vflow"] * p["D"] / p["mu"]
    fd = _f_darcy(re_pipe, p["eps"], p["D"])
    delta_um = (p["yplus"] * p["D"] / re_pipe) * math.sqrt(8.0 / fd) * 1e6
    thomas_limit_mm = delta_um / 1000.0 if p["fine"] == "sublayer" else 0.070
    if p["d_mm"] <= thomas_limit_mm:
        selected_name = "Thomas - d <= subcamada" if p["fine"] == "sublayer" else "Thomas - d <= 70 um"
        v_horizontal = v_thomas
    elif p["d_mm"] <= 0.150:
        selected_name = "MWJ / Wilson-Judge"
        v_horizontal = v_mwj
    else:
        selected_name = "Wilson (leito)"
        v_horizontal = v_wilson
    f_est = _f_darcy(p["D"] * max(v_horizontal, 1e-9) / nu, p["eps"], p["D"])
    vcap_est = (0.018 / f_est) ** 0.13 * math.sqrt(2.0 * g * (ss / sf - 1.0) * p["D"])
    def rootfun(v):
        return v / math.sqrt(2.0 * g * (ss / sf - 1.0) * p["D"]) - (0.018 / _f_darcy(p["D"] * v / nu, p["eps"], p["D"])) ** 0.13
    vcap = _bisect_root(rootfun, max(1e-9, 0.2 * vcap_est), 5.0 * vcap_est)
    capped = False
    if v_horizontal > vcap:
        v_horizontal = vcap
        capped = True
    theta = math.radians(p["theta_deg"])
    delta_d = _delta_d_inclinacao(theta)
    fl = v_horizontal / math.sqrt(2.0 * g * (ss / sf - 1.0) * p["D"]) + delta_d
    vsm = max(0.0, fl * math.sqrt(2.0 * g * (ss / sf - 1.0) * p["D"]))
    cr = p["cvd"] / p["cvb"]
    den_base = math.cos(theta) + 2.145 * math.sin(theta)
    den = max(den_base, 1e-12) ** 0.17
    crm = 0.16 * p["D"] ** 0.4 / (p["d_mm"] ** 0.84 * density_term ** (0.55 * 0.3) * den)
    crm = max(0.05, min(0.66, crm))
    alpha = math.log(0.333) / math.log(crm)
    beta = math.log(0.667) / math.log(1.0 - crm)
    vs_vsm = cr ** alpha * (1.0 - cr ** alpha) ** 2
    if crm > 0.333:
        vs_vsm = (1.0 - cr) ** (2.0 * beta) * (1.0 - (1.0 - cr) ** beta)
    vs = 6.75 * vs_vsm * vsm
    cw = (p["cvd"] * p["rho_s"]) / (p["cvd"] * p["rho_s"] + (1.0 - p["cvd"]) * p["rho_l"])
    return {"Vsm": vsm, "Vs": vs, "margem_vs_percent": 100.0 * (p["Vflow"] / vs - 1.0) if vs > 0 else None, "margem_vsm_percent": 100.0 * (p["Vflow"] / vsm - 1.0) if vsm > 0 else None, "model": selected_name + (" / limite eq. 4.15" if capped else ""), "stokes": stokes, "vt_tl": vt_tl, "Re_particula": re_p, "Cd": cd, "Re_pipe": re_pipe, "fD": fd, "delta_um": delta_um, "DeltaD": delta_d, "Cr": cr, "Crm": crm, "FL": fl, "Cw": cw, "Vwilson": v_wilson, "Vthomas": v_thomas, "Vmwj": v_mwj, "Vcap": vcap}


def _diametro_representativo(dados):
    pares = sorted(zip(dados["diametros_um"], dados["proporcoes_percent"]), key=lambda item: item[0])
    total = sum(p for _, p in pares)
    alvo = 0.5 * total
    acum = 0.0
    for diam, frac in pares:
        acum += frac
        if acum >= alvo:
            return diam / 1000.0
    return pares[-1][0] / 1000.0


def _range_parametrico(valor_operacional, minimo_informado, maximo_informado, minimo_absoluto):
    minimo = float(minimo_informado) if minimo_informado not in (None, "") else 0.5 * valor_operacional
    maximo = float(maximo_informado) if maximo_informado not in (None, "") else 2.0 * valor_operacional
    minimo = max(minimo_absoluto, minimo)
    maximo = max(minimo + minimo_absoluto, maximo)
    return minimo, maximo


def executar_vscalc(entradas):
    dados = normalizar_entradas(entradas)
    d_mm = float(dados.get("vscalc_d_mm") or _diametro_representativo(dados))
    p = {"D": dados["diametro_pol"] * 0.0254, "eps": dados["rugosidade_relativa"] * dados["diametro_pol"] * 0.0254, "d_mm": d_mm, "Vflow": dados["velocidade"], "theta_deg": float(dados.get("vscalc_theta_deg") or 0.0), "rho_s": dados["rho_s"], "rho_l": dados["rho_l"], "mu": dados["mu_l_cp"] * 0.001, "cvd": dados["phi_total"], "cvb": float(dados.get("vscalc_cvb") or 0.60), "mus": float(dados.get("vscalc_mus") or 0.45), "yplus": float(dados.get("vscalc_yplus") or 5.0), "drag": str(dados.get("vscalc_drag") or "tl"), "fine": str(dados.get("vscalc_fine") or "original70")}
    r = _compute(p)
    n_pontos = 80
    vel_rows = []
    vmin, vmax = _range_parametrico(p["Vflow"], dados.get("vscalc_vmin"), dados.get("vscalc_vmax"), 1e-4)
    for i in range(n_pontos):
        v = vmin + i * (vmax - vmin) / max(n_pontos - 1, 1)
        rr = _compute({**p, "Vflow": v})
        vel_rows.append({"x": v, "Vop": v, "Vs": rr["Vs"], "Vsm": rr["Vsm"]})
    dia_rows = []
    dmin_mm, dmax_mm = _range_parametrico(
        p["d_mm"],
        float(dados["vscalc_dmin_um"]) / 1000.0 if dados.get("vscalc_dmin_um") not in (None, "") else None,
        float(dados["vscalc_dmax_um"]) / 1000.0 if dados.get("vscalc_dmax_um") not in (None, "") else None,
        1e-4,
    )
    for i in range(n_pontos):
        d = dmin_mm + i * (dmax_mm - dmin_mm) / max(n_pontos - 1, 1)
        rr = _compute({**p, "d_mm": d})
        dia_rows.append({"x": d, "Vop": p["Vflow"], "Vs": rr["Vs"], "Vsm": rr["Vsm"]})
    tabela = [
        {
            "simbolo": "Vsm",
            "descricao": _("Velocidade de deposição - Limit of Stationary Deposit"),
            "valor": r["Vsm"],
            "unidade": "m/s",
            "help_text": _("Velocidade de deposição utilizada pelo modelo de Wilson. Acima desta velocidade o material permanece em movimento, podendo ainda existir leito móvel. Não corresponde necessariamente à suspensão completa das partículas."),
        },
        {
            "simbolo": "Vs",
            "descricao": _("Velocidade crítica de deposição"),
            "valor": r["Vs"],
            "unidade": "m/s",
            "help_text": _("Velocidade crítica de deposição estimada pelo modelo selecionado. Representa a velocidade mínima recomendada para evitar deposição estacionária nas condições especificadas."),
        },
        {"simbolo": "Modelo", "descricao": _("Modelo selecionado automaticamente"), "valor": r["model"], "unidade": "-"},
        {"simbolo": "Re", "descricao": _("Reynolds do tubo"), "valor": r["Re_pipe"], "unidade": "-"},
        {"simbolo": "fD", "descricao": _("Fator de atrito Darcy"), "valor": r["fD"], "unidade": "-"},
        {"simbolo": "delta_v", "descricao": _("Subcamada viscosa"), "valor": r["delta_um"], "unidade": "um"},
        {"simbolo": "vt TL", "descricao": _("Velocidade terminal Turton-Levenspiel"), "valor": r["vt_tl"], "unidade": "m/s"},
        {"simbolo": "vt Stokes", "descricao": _("Velocidade terminal Stokes"), "valor": r["stokes"], "unidade": "m/s"},
        {"simbolo": "Cd", "descricao": _("Coeficiente de arrasto"), "valor": r["Cd"], "unidade": "-"},
        {"simbolo": "DeltaD", "descricao": _("Correcao de inclinacao"), "valor": r["DeltaD"], "unidade": "-"},
        {"simbolo": "Cv", "descricao": _("Concentracao volumetrica interna"), "valor": p["cvd"], "unidade": "-"},
        {"simbolo": "Cw", "descricao": _("Concentracao massica equivalente"), "valor": r["Cw"], "unidade": "-"},
        {"simbolo": "Cr", "descricao": "Cvd/Cvb", "valor": r["Cr"], "unidade": "-"},
        {"simbolo": "Crm", "descricao": _("Concentracao relativa no maximo"), "valor": r["Crm"], "unidade": "-"},
    ]
    avisos = ["VSCALC+ calculado integralmente no backend Python a partir das equacoes do prototipo."]
    if p["fine"] == "sublayer":
        avisos.append("Criterio Thomas por subcamada viscosa ativo; y+ usado apenas como criterio alternativo/diagnostico.")
    return _json_safe({
        "tipo_resultado": "vscalc",
        "entradas": {**dados, "vscalc_d_mm": d_mm},
        "resumo": {
            "modelo_escoamento": "vscalc",
            "velocidade_operacao": p["Vflow"],
            "vsm": r["Vsm"],
            "vs": r["Vs"],
            "diametro_operacional_mm": d_mm,
            "diametro_operacional_um": d_mm * 1000.0,
            "modelo_vscalc": r["model"],
            "margem_vs_percent": r["margem_vs_percent"],
            "margem_vsm_percent": r["margem_vsm_percent"],
            "phi_w_percent": r["Cw"] * 100.0,
            "phi_v_percent": p["cvd"] * 100.0,
        },
        "avisos": avisos,
        "tabela_resultados": tabela,
        "graficos": {
            "vscalc_velocidade": vel_rows,
            "vscalc_diametro": dia_rows,
            "vscalc_operacao": {"velocidade": p["Vflow"], "diametro_mm": d_mm, "diametro_um": d_mm * 1000.0, "Vs": r["Vs"], "Vsm": r["Vsm"]},
        },
    })
