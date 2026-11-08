import math

from django.utils.translation import gettext as _

from .calculos import _json_safe, normalizar_entradas


def cv_to_cw(cv, rho_s, rho_l):
    return (cv * rho_s) / (cv * rho_s + (1.0 - cv) * rho_l)


def cw_to_cv(cw, rho_s, rho_l):
    return (cw * rho_l) / (rho_s * (1.0 - cw) + cw * rho_l)


def absoluta_para_passante(diametros_um, proporcoes_percent):
    if len(diametros_um) != len(proporcoes_percent):
        raise ValueError("PSD invalida: diametros e fracoes devem ter o mesmo tamanho.")
    pares = sorted((float(d), float(p)) for d, p in zip(diametros_um, proporcoes_percent))
    if any(d <= 0 for d, _ in pares):
        raise ValueError("PSD invalida: diametros devem ser positivos.")
    if any(p < 0 for _, p in pares):
        raise ValueError("PSD invalida: fracoes negativas nao sao permitidas.")
    total = sum(p for _, p in pares)
    if not math.isclose(total, 100.0, rel_tol=1e-6, abs_tol=1e-4):
        raise ValueError("PSD invalida: a soma das fracoes deve ser 100%.")
    acumulado = 0.0
    psd = []
    for diam, frac in pares:
        acumulado += frac
        psd.append({"d": diam, "p": max(0.0, min(1.0, acumulado / 100.0))})
    if psd[0]["p"] > 0:
        psd.insert(0, {"d": max(psd[0]["d"] * 0.1, 0.001), "p": 0.0})
    if psd[-1]["p"] < 1:
        psd.append({"d": psd[-1]["d"] * 1.5, "p": 1.0})
    return psd


def _p_of(psd, diam):
    if diam <= psd[0]["d"]:
        return psd[0]["p"]
    for i in range(1, len(psd)):
        if diam <= psd[i]["d"]:
            x0 = math.log(psd[i - 1]["d"])
            x1 = math.log(psd[i]["d"])
            x = math.log(diam)
            t = (x - x0) / (x1 - x0)
            return psd[i - 1]["p"] + t * (psd[i]["p"] - psd[i - 1]["p"])
    return psd[-1]["p"]


def _d_of_p(psd, p):
    p = max(0.0, min(1.0, p))
    if p <= psd[0]["p"]:
        return psd[0]["d"]
    for i in range(1, len(psd)):
        if p <= psd[i]["p"]:
            denom = psd[i]["p"] - psd[i - 1]["p"] or 1e-12
            t = (p - psd[i - 1]["p"]) / denom
            return math.exp(math.log(psd[i - 1]["d"]) + t * (math.log(psd[i]["d"]) - math.log(psd[i - 1]["d"])))
    return psd[-1]["d"]


def _f_darcy(reynolds, eps, diameter):
    if reynolds < 2000:
        return 64.0 / max(reynolds, 1e-12)
    return 0.25 / (math.log10(eps / (3.7 * diameter) + 5.74 / (reynolds ** 0.9)) ** 2)


def _vsm_wilson(diameter, d_um, ss, sf, mus):
    dmm = d_um / 1000.0
    return 8.8 * (mus * (ss / sf - 1.0) / 0.66) ** 0.55 * diameter ** 0.7 * dmm ** 1.75 / (dmm * dmm + 0.11 * diameter ** 0.7)


def _calc_once(dados, velocidade=None):
    g = 9.81
    diameter = dados["diametro_pol"] * 0.0254
    eps = dados["rugosidade_relativa"] * diameter
    v = float(velocidade if velocidade is not None else dados["velocidade"])
    rho_s = dados["rho_s"]
    rho_l = dados["rho_l"]
    mu_l = dados["mu_l_cp"] * 0.001
    cv = dados["phi_total"]
    mus = float(dados.get("fourcm_mus") or dados.get("gillies_eta_s") or 0.48)
    af = float(dados.get("fourcm_af") or 1.0)
    ap = float(dados.get("fourcm_ap") or 0.5)
    cf = float(dados.get("fourcm_cf") or 1.0)
    cp = float(dados.get("fourcm_cp") or 0.5)
    nc = float(dados.get("fourcm_nc") or 0.5)
    bf = float(dados.get("fourcm_bf") or 1.0)
    bp = float(dados.get("fourcm_bp") or 1.0)
    bh = float(dados.get("fourcm_bh") or 0.5)
    nb = float(dados.get("fourcm_nb") or 0.5)
    psd = absoluta_para_passante(dados["diametros_um"], dados["proporcoes_percent"])
    ss = rho_s / 1000.0
    sl = rho_l / 1000.0
    sm = sl + cv * (ss - sl)
    df = 40.0 * (2.65 / ss)
    d200 = 200.0
    ds = 0.015 * diameter * 1e6
    pf = _p_of(psd, df)
    p200 = _p_of(psd, d200)
    pds = _p_of(psd, ds)
    xf = max(0.0, pf)
    xp = max(0.0, p200 - pf)
    xh = max(0.0, pds - p200)
    xs = max(0.0, 1.0 - pds)
    d50h = _d_of_p(psd, p200 + 0.5 * xh) if xh > 1e-8 else None
    d50s = _d_of_p(psd, pds + 0.5 * xs) if xs > 1e-8 else None
    denom_f = 1.0 - cv * (1.0 - xf)
    cvf = (xf * cv) / denom_f if denom_f > 0 else 0.0
    sf = sl + (xf * cv * (ss - sl)) / denom_f
    muf = mu_l * (1.0 + 2.5 * cvf + 10.0 * cvf * cvf + 0.0019 * math.exp(20.0 * cvf))
    reynolds = 1000.0 * sf * v * diameter / max(muf, 1e-12)
    ff = _f_darcy(reynolds, eps, diameter)
    iff = sf * ff * v * v / (2.0 * g * diameter)
    sfp = sl + ((xf + xp) * cv * (ss - sl)) / (1.0 - cv * (1.0 - xf - xp))
    sfph = sl + ((xf + xp + xh) * cv * (ss - sl)) / (1.0 - cv * (1.0 - xf - xp - xh))
    a_factor = max(0.0, min(1.0, 1.0 - (af * xf + ap * xp)))
    dip = a_factor * (sfp - sf) * (iff / sf) if xp > 1e-12 else 0.0
    nu_r = muf / (0.001 * sf)
    v50h = 44.1 * (d50h / 1e6) ** 0.35 / (nu_r ** 0.25) * ((ss - sfp) / 1.65) if xh > 1e-12 and d50h else None
    vsmh = _vsm_wilson(diameter, d50h, ss, sfp, mus) if xh > 1e-12 and d50h else None
    vsms = _vsm_wilson(diameter, ds, ss, sfph, mus)
    dsm = ds / 1e6
    vts = 0.94 * math.sqrt(g * dsm * (ss / sf - 1.0))
    v100 = 1800.0 * g * diameter * vts ** 3
    def trans(vsm, coeff, n):
        if vsm is None:
            return 1.0
        if v >= v100 or v100 <= vsm:
            return 1.0
        ratio = (v100 - v) / (v100 - vsm)
        return max(0.0, min(1.0, 1.0 - coeff * max(0.0, ratio) ** n))
    c_factor = trans(vsmh, cf * xf + cp * xp, nc) if xh > 1e-12 else 1.0
    b_factor = trans(vsms, bf * xf + bp * xp + bh * xh, nb) if xs > 1e-12 else 1.0
    dih = c_factor * (mus / 2.0) * (sfph - sfp) * (v50h / max(v, 1e-9)) if xh > 1e-12 and v50h else 0.0
    dis = b_factor * 2.0 * mus * (xs * cv) * (ss - sfph) * (vsms / max(v, 1e-9)) ** 0.25 if xs > 1e-12 else 0.0
    im = iff + dip + dih + dis
    return {"D": diameter, "eps": eps, "V": v, "Cv": cv, "Cw": cv_to_cw(cv, rho_s, rho_l), "Ss": ss, "Sl": sl, "Sm": sm, "df": df, "ds": ds, "Xf": xf, "Xp": xp, "Xh": xh, "Xs": xs, "d50h": d50h, "d50s": d50s, "Cvf": cvf, "Sf": sf, "muf": muf, "Re": reynolds, "ff": ff, "iff": iff, "Sfp": sfp, "Sfph": sfph, "A": a_factor, "C": c_factor, "B": b_factor, "dip": dip, "dih": dih, "dis": dis, "V50h": v50h, "Vsmh": vsmh, "Vsms": vsms if xs > 1e-12 else None, "V100": v100, "im": im, "headloss_m_polpa_km": (im / sm) * 1000.0, "headloss_magua_km": im * 1000.0, "bar_km": im * 98.0665, "psd": psd}


def executar_4cm(entradas):
    dados = normalizar_entradas(entradas)
    r = _calc_once(dados)
    vmin = float(dados.get("fourcm_vmin") or dados.get("U_inicial") or 0.5)
    vmax = float(dados.get("fourcm_vmax") or dados.get("U_final") or max(8.0, 2.0 * dados["velocidade"]))
    if vmin <= 0:
        vmin = 0.2
    if vmax <= vmin:
        vmax = vmin + 1.0
    velocidades = []
    curva = {"total": [], "carrier": [], "pseudo": [], "heterogeneo": [], "estratificado": []}
    for i in range(60):
        v = 10 ** (math.log10(vmin) + (math.log10(vmax) - math.log10(vmin)) * i / 59.0)
        rr = _calc_once(dados, v)
        velocidades.append(v)
        curva["total"].append(rr["headloss_m_polpa_km"])
        curva["carrier"].append((rr["iff"] / rr["Sm"]) * 1000.0)
        curva["pseudo"].append((rr["dip"] / rr["Sm"]) * 1000.0)
        curva["heterogeneo"].append((rr["dih"] / rr["Sm"]) * 1000.0)
        curva["estratificado"].append((rr["dis"] / rr["Sm"]) * 1000.0)
    warnings = []
    if r["Xp"] <= 1e-12:
        warnings.append(_("Xp = 0: parcela pseudo-homogenea ignorada."))
    if r["Xh"] <= 1e-12:
        warnings.append(_("Xh = 0: parcela heterogênea ignorada; d50h/V50h/Vsm,h ficam N/A."))
    if r["Xs"] <= 1e-12:
        warnings.append(_("Xs = 0: parcela estratificada ignorada; V100,s permanece diagnóstico."))
    rows = [
        ("J", _("Gradiente hidráulico total"), r["im"] / r["Sm"], "m polpa/m"),
        ("DeltaP 4CM", _("Perda de carga 4CM"), r["headloss_m_polpa_km"], "m polpa/km"),
        ("DeltaP 4CM", _("Perda de carga 4CM"), r["bar_km"], "bar/km"),
        ("DeltaP ref.", _("Referência em coluna de água"), r["headloss_magua_km"], "mH2O/km"),
        ("if", _("Carrier + finos"), r["iff"] / r["Sm"], "m polpa/m"),
        ("Delta ip", _("Pseudo-homogêneo"), r["dip"] / r["Sm"], "m polpa/m"),
        ("Delta ih", _("Heterogêneo"), r["dih"] / r["Sm"], "m polpa/m"),
        ("Delta is", _("Estratificado"), r["dis"] / r["Sm"], "m polpa/m"),
        ("Xf", _("Fração carrier/finos"), r["Xf"], "-"),
        ("Xp", _("Fração pseudo-homogênea"), r["Xp"], "-"),
        ("Xh", _("Fração heterogênea"), r["Xh"], "-"),
        ("Xs", _("Fração estratificada"), r["Xs"], "-"),
        ("d50h", _("d50 da parcela heterogênea"), r["d50h"], "um"),
        ("d50s", _("d50 da parcela estratificada"), r["d50s"], "um"),
        ("Vsm,h", _("Velocidade mínima da parcela heterogênea"), r["Vsmh"], "m/s"),
        ("Vsm,s", _("Velocidade mínima da parcela estratificada"), r["Vsms"], "m/s"),
        ("V50,h", _("Velocidade característica V50,h"), r["V50h"], "m/s"),
        ("V100,s", _("Velocidade de suspensão completa V100,s"), r["V100"], "m/s"),
        ("A''", _("Fator A''"), r["A"], "-"),
        ("B''", _("Fator B''"), r["B"], "-"),
        ("C''", _("Fator C''"), r["C"], "-"),
    ]
    return _json_safe({
        "converged": True,
        "message": _("4CM calculado no backend Python."),
        "warnings": warnings,
        "results": r,
        "rows": [{"symbol": s, "description": d, "value": v, "unit": u} for s, d, v, u in rows],
        "components": [
            {"name": _("Carrier"), "fraction": r["Xf"], "gradient": r["iff"] / r["Sm"]},
            {"name": _("Pseudo-homogêneo"), "fraction": r["Xp"], "gradient": r["dip"] / r["Sm"]},
            {"name": _("Heterogêneo"), "fraction": r["Xh"], "gradient": r["dih"] / r["Sm"]},
            {"name": _("Estratificado"), "fraction": r["Xs"], "gradient": r["dis"] / r["Sm"]},
        ],
        "graph": {"velocidades": velocidades, **curva, "scale": str(dados.get("fourcm_scale") or "log")},
        "psd_passante": {"diametros_um": [p["d"] for p in r["psd"]], "passante": [100.0 * p["p"] for p in r["psd"]]},
    })