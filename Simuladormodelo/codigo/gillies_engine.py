from __future__ import annotations

import math

from django.utils.translation import gettext as _
from dataclasses import dataclass

import numpy as np
from scipy.optimize import brentq, root


G = 9.80665


@dataclass
class TwoLayerInputs:
    D_m: float
    U_m_s: float
    Cv: float
    rho_s: float
    rho_l: float
    mu_f_pa_s: float
    rel_roughness: float
    diameters_um: list[float]
    proportions_percent: list[float]
    Cmax: float = 0.75
    eta_s: float = 0.50
    d12_mode: str = "auto"
    d12_manual_um: float | None = None


def _fail(message: str, inputs_used: dict | None = None, warnings: list[str] | None = None) -> dict:
    return {
        "converged": False,
        "message": message,
        "inputs_used": inputs_used or {},
        "results": {},
        "diagnostics": {
            "error_Cr": None,
            "error_Clim": None,
            "error_Cc": None,
            "iterations": None,
            "status": "not_converged",
            "warnings": warnings or [],
        },
    }


def _parse_list(value) -> list[float]:
    if isinstance(value, str):
        parts = [part.strip().replace(",", ".") for part in value.replace(";", ",").split(",")]
        return [float(part) for part in parts if part]
    return [float(item) for item in value]


def _pipe_area(D: float) -> float:
    return math.pi * D * D / 4.0


def _cd_turton_levenspiel(Re_p: float) -> float:
    Re_p = abs(Re_p)
    if Re_p < 1e-14:
        return 1e30
    return 24.0 / Re_p * (1.0 + 0.173 * Re_p ** 0.657) + 0.413 / (1.0 + 16300.0 * Re_p ** -1.09)


def _terminal_velocity(d: float, rho_s: float, rho_f: float, mu_f: float) -> tuple[float, float, float]:
    if rho_s <= rho_f:
        raise ValueError("rho_s precisa ser maior que rho_f para sedimentacao.")

    def residual(v: float) -> float:
        Re_p = rho_f * v * d / mu_f
        Cd = _cd_turton_levenspiel(Re_p)
        v_calc = math.sqrt(4.0 * G * d * (rho_s - rho_f) / (3.0 * Cd * rho_f))
        return v - v_calc

    v = brentq(residual, 1e-10, 50.0)
    Re_p = rho_f * v * d / mu_f
    Cd = _cd_turton_levenspiel(Re_p)
    return v, Re_p, Cd


def _churchill_fanning(Re: float, rel_rough: float) -> float:
    Re = abs(Re)
    if Re < 1e-12:
        raise ValueError("Reynolds nulo ou negativo.")
    A = (-2.457 * math.log((7.0 / Re) ** 0.9 + 0.27 * rel_rough)) ** 16
    B = (37530.0 / Re) ** 16
    f_darcy = 8.0 * ((8.0 / Re) ** 12 + 1.0 / (A + B) ** 1.5) ** (1.0 / 12.0)
    return f_darcy / 4.0


def _lower_area_from_beta(D: float, beta: float) -> float:
    return D**2 * (2.0 * beta - math.sin(2.0 * beta)) / 8.0


def _beta_from_area_ratio(D: float, area_ratio: float) -> float:
    if not 0.0 < area_ratio < 1.0:
        raise ValueError(f"Fechamento geometrico invalido: A2/A fora do intervalo 0-1 ({area_ratio:.6g}).")
    A = _pipe_area(D)
    target = area_ratio * A
    return brentq(lambda beta: _lower_area_from_beta(D, beta) - target, 1e-10, math.pi - 1e-10)


def _f12_interface(D: float, d12: float) -> float:
    if d12 <= 0 or d12 >= D:
        raise ValueError("d12 deve ser positivo e menor que D.")
    ratio = d12 / D
    Y = 5.0 + 1.86 * math.log10(ratio) if ratio > 0.002 else 0.0
    return (1.0 + 2.0 * Y) / (4.0 * math.log10(D / d12) + 3.36) ** 2


def _d50_from_classes(diameters_um: list[float], proportions_percent: list[float]) -> float:
    pairs = sorted(zip(diameters_um, proportions_percent), key=lambda item: item[0])
    total = sum(max(p, 0.0) for _, p in pairs)
    if total <= 0.0:
        raise ValueError("A soma das proporcoes granulometricas deve ser positiva.")
    acc = 0.0
    for d_um, pct in pairs:
        acc += max(pct, 0.0)
        if acc >= 0.5 * total:
            return d_um * 1e-6
    return pairs[-1][0] * 1e-6


def _coarse_properties(diameters_um: list[float], proportions_percent: list[float]) -> tuple[float, float, float]:
    coarse = [(d, p) for d, p in zip(diameters_um, proportions_percent) if d >= 74.0]
    fines_pct = sum(p for d, p in zip(diameters_um, proportions_percent) if d < 74.0)
    coarse_pct = sum(p for _, p in coarse)
    if coarse_pct <= 0.0:
        raise ValueError("Nao ha fracao grossa +74 um para o modelo de duas camadas.")
    return _d50_from_classes([d for d, _ in coarse], [p for _, p in coarse]), fines_pct / 100.0, coarse_pct / 100.0


def _interpolate_coarse_diameter(diameters_um: list[float], proportions_percent: list[float], passing_fraction: float) -> tuple[float, float]:
    coarse = sorted(
        [(d, max(p, 0.0)) for d, p in zip(diameters_um, proportions_percent) if d >= 74.0],
        key=lambda item: item[0],
    )
    total = sum(p for _, p in coarse)
    if total <= 0.0:
        raise ValueError("Nao ha fracao grossa +74 um para calcular d12.")
    P = min(max(passing_fraction, 0.0), 1.0)
    acc = 0.0
    cumulative = []
    for d_um, pct in coarse:
        acc += pct
        cumulative.append((d_um, acc / total))
    if P <= cumulative[0][1]:
        return cumulative[0][0] * 1e-6, P
    for (d0, p0), (d1, p1) in zip(cumulative[:-1], cumulative[1:]):
        if P <= p1:
            frac = 0.0 if abs(p1 - p0) < 1e-12 else (P - p0) / (p1 - p0)
            return (d0 + frac * (d1 - d0)) * 1e-6, P
    return cumulative[-1][0] * 1e-6, P


def _normalizar_entrada(entradas: dict) -> TwoLayerInputs:
    diameters_um = _parse_list(entradas.get("diametros_um"))
    proportions = _parse_list(entradas.get("proporcoes_percent"))
    if len(diameters_um) != len(proportions):
        raise ValueError("Granulometria invalida: diametros e proporcoes com tamanhos diferentes.")
    total = sum(proportions)
    if total <= 0.0:
        raise ValueError("Granulometria invalida: soma das proporcoes menor ou igual a zero.")
    proportions = [100.0 * p / total for p in proportions]
    mu_f_cp = entradas.get("gillies_mu_f_cp")
    if mu_f_cp in (None, ""):
        mu_f_cp = entradas.get("mu_l_cp")
    d12_manual = entradas.get("gillies_d12_manual_um")
    return TwoLayerInputs(
        D_m=float(entradas.get("diametro_m") or float(entradas["diametro_pol"]) * 0.0254),
        U_m_s=float(entradas["velocidade"]),
        Cv=float(entradas["phi_total"]),
        rho_s=float(entradas["rho_s"]),
        rho_l=float(entradas["rho_l"]),
        mu_f_pa_s=float(mu_f_cp) * 0.001,
        rel_roughness=float(entradas["rugosidade_relativa"]),
        diameters_um=diameters_um,
        proportions_percent=proportions,
        Cmax=float(entradas.get("gillies_cmax", 0.75)),
        eta_s=float(entradas.get("gillies_eta_s", 0.50)),
        d12_mode=str(entradas.get("gillies_d12_mode", "auto")),
        d12_manual_um=None if d12_manual in (None, "") else float(d12_manual),
    )


def _concentrations(inp: TwoLayerInputs, Ct: float, d50_coarse: float, frac_fines: float) -> dict:
    Cf = Ct * frac_fines
    Cr = Ct - Cf
    if Cr <= 1e-10:
        raise ValueError("Cr muito baixo. O modelo de duas camadas perde sentido fisico.")
    rho_f = (inp.rho_l * (1.0 - Ct) + inp.rho_s * Cf) / (1.0 - Ct + Cf)
    v_inf, Re_p50, Cd50 = _terminal_velocity(d50_coarse, inp.rho_s, rho_f, inp.mu_f_pa_s)
    term_clim = 0.074 * (inp.U_m_s / v_inf) ** 0.44 * (1.0 - Cr) ** 0.189
    Clim = inp.Cmax - (inp.Cmax - Cr) * term_clim
    Cc = Cr * math.exp(-0.0184 * inp.U_m_s / v_inf)
    C1 = Cr - Cc
    C2 = Clim - C1
    Cc_over_Cr = Cc / Cr if Cr else math.nan
    if inp.d12_mode == "manual":
        if inp.d12_manual_um is None:
            raise ValueError("d12 manual nao informado.")
        d12 = inp.d12_manual_um * 1e-6
        d12_percentile = None
    else:
        d12, d12_percentile = _interpolate_coarse_diameter(inp.diameters_um, inp.proportions_percent, 1.0 - Cc_over_Cr)
    return {
        "Cf": Cf,
        "Cr": Cr,
        "rho_f": rho_f,
        "v_inf": v_inf,
        "Re_p50": Re_p50,
        "Cd50": Cd50,
        "Clim": Clim,
        "Cc": Cc,
        "C1": C1,
        "C2": C2,
        "Cc_over_Cr": Cc_over_Cr,
        "d12": d12,
        "d12_percentile": d12_percentile,
    }


def _run_given_ct(inp: TwoLayerInputs, Ct: float, d50_coarse: float, frac_fines: float, frac_coarse: float) -> dict:
    A = _pipe_area(inp.D_m)
    c = _concentrations(inp, Ct, d50_coarse, frac_fines)
    if c["Clim"] <= c["C1"]:
        raise ValueError(_("Erro fisico ou numerico: Clim <= C1, logo C2 <= 0."))
    if c["C2"] <= 0.0:
        raise ValueError(_("Erro fisico ou numerico: C2 <= 0. Verificar Ct, Cr, velocidade, d50, Cmax e v_inf."))
    area_ratio = c["Cc"] / c["C2"]
    beta = _beta_from_area_ratio(inp.D_m, area_ratio)
    A2 = A * area_ratio
    A1 = A - A2
    S2 = inp.D_m * beta
    S1 = inp.D_m * (math.pi - beta)
    S12 = inp.D_m * math.sin(beta)
    rho1 = c["rho_f"] * (1.0 - c["C1"]) + inp.rho_s * c["C1"]
    # rho2f: fluido + suspensos na camada inferior; corrigido conforme artigo Gillies et al. (1991).
    rho2f = (c["rho_f"] * (1.0 - c["Clim"]) + inp.rho_s * c["C1"]) / (1.0 - c["Clim"] + c["C1"])
    f12 = _f12_interface(inp.D_m, c["d12"])

    def equations(x: np.ndarray) -> list[float]:
        U1, U2, i = x
        Dh1 = 4.0 * A1 / (S1 + S12)
        Dh2 = 4.0 * A2 / S2
        Re1 = rho1 * abs(U1) * Dh1 / inp.mu_f_pa_s
        Re2 = rho2f * abs(U2) * Dh2 / inp.mu_f_pa_s
        f1 = _churchill_fanning(Re1, inp.rel_roughness)
        f2 = _churchill_fanning(Re2, inp.rel_roughness)
        tau1 = 0.5 * f1 * U1 * abs(U1) * rho1
        tau12 = 0.5 * f12 * (U1 - U2) * abs(U1 - U2) * rho1
        tau2S2 = (
            0.5 * f2 * U2 * abs(U2) * rho2f * S2
            + 0.5 * (inp.rho_s - c["rho_f"]) * c["C2"] * (1.0 - c["Clim"])
            * (math.sin(beta) - beta * math.cos(beta)) * inp.eta_s / (1.0 - c["C2"])
        )
        return [
            A * inp.U_m_s - A1 * U1 - A2 * U2,
            i * c["rho_f"] * G - (tau1 * S1 + tau12 * S12) / A1,
            i * c["rho_f"] * G - (-tau12 * S12 + tau2S2) / A2,
        ]

    sol = None
    iterations = 0
    for guess in (
        np.array([inp.U_m_s * 1.05, inp.U_m_s * 0.75, 0.02]),
        np.array([inp.U_m_s * 1.20, inp.U_m_s * 0.50, 0.05]),
        np.array([inp.U_m_s * 1.01, inp.U_m_s * 0.95, 0.01]),
    ):
        trial = root(equations, guess, method="hybr")
        iterations += int(getattr(trial, "nfev", 0) or 0)
        if trial.success and trial.x[0] > 0.0 and trial.x[1] > 0.0 and trial.x[2] > 0.0:
            sol = trial
            break
    if sol is None:
        raise RuntimeError("Nao convergiu em U1, U2 e i.")

    U1, U2, i = map(float, sol.x)
    Ff = c["Cf"] * ((1.0 - c["C1"]) * A1 * U1 + (1.0 - c["Clim"]) * A2 * U2) / (1.0 - c["Cr"])
    Cd = (c["C1"] * A * inp.U_m_s + c["C2"] * A2 * U2 + Ff) / (A * inp.U_m_s)
    dpdl = i * c["rho_f"] * G
    rho_polpa = inp.rho_l * (1.0 - inp.Cv) + inp.rho_s * inp.Cv
    return {
        "U": inp.U_m_s,
        "U1": U1,
        "U2": U2,
        "Ct": Ct,
        "Cd": Cd,
        "Cf": c["Cf"],
        "Cr": c["Cr"],
        "Cc": c["Cc"],
        "Cc_over_Cr": c["Cc_over_Cr"],
        "C1": c["C1"],
        "C2": c["C2"],
        "Clim": c["Clim"],
        "A2_over_A": area_ratio,
        "lower_layer_height_m": (inp.D_m / 2.0) * (1.0 - math.cos(beta)),
        "lower_layer_height_over_D": 0.5 * (1.0 - math.cos(beta)),
        "d50_coarse_um": d50_coarse * 1e6,
        "d12_um": c["d12"] * 1e6,
        "d12_percentile_grossos": c["d12_percentile"],
        "pressure_gradient_pa_m": dpdl,
        "pressure_gradient_kpa_km": dpdl,
        "pressure_gradient_bar_km": dpdl * 1000.0 / 1e5,
        "headloss_mca_km": dpdl * 1000.0 / (inp.rho_l * G),
        "headloss_m_polpa_km": dpdl * 1000.0 / (rho_polpa * G),
        "beta_rad": beta,
        "error_Cr": c["Cr"] - (c["C1"] + c["Cc"]),
        "error_Clim": c["Clim"] - (c["C1"] + c["C2"]),
        "error_Cc": c["Cc"] - c["C2"] * area_ratio,
        "iterations": iterations,
        "frac_coarse_ge_74": frac_coarse,
    }


def run_gillies(entradas: dict) -> dict:
    try:
        inp = _normalizar_entrada(entradas)
        d50_coarse, frac_fines, frac_coarse = _coarse_properties(inp.diameters_um, inp.proportions_percent)
        inputs_used = {
            "D_m": inp.D_m,
            "U_m_s": inp.U_m_s,
            "Cv": inp.Cv,
            "rho_s": inp.rho_s,
            "rho_l": inp.rho_l,
            "mu_f_pa_s": inp.mu_f_pa_s,
            "rel_roughness": inp.rel_roughness,
            "Cmax": inp.Cmax,
            "eta_s": inp.eta_s,
            "d12_mode": inp.d12_mode,
        }
        warnings = []
        if frac_coarse < 0.05:
            warnings.append(_("Fracao grossa +74 um muito pequena; d12 automatico pode ficar numericamente instavel."))
        if inp.D_m <= 0 or inp.U_m_s <= 0 or inp.Cv <= 0 or inp.Cv > 0.65:
            return _fail(_("Dados insuficientes ou fora da faixa para o modelo de duas camadas."), inputs_used, warnings)
        if inp.rho_s <= inp.rho_l or inp.mu_f_pa_s <= 0:
            return _fail(_("Densidades ou viscosidade invalidas para o modelo de duas camadas."), inputs_used, warnings)

        def residual(Ct: float) -> float:
            return _run_given_ct(inp, Ct, d50_coarse, frac_fines, frac_coarse)["Cd"] - inp.Cv

        lo = max(1e-5, inp.Cv * 0.50)
        hi = min(0.65, max(inp.Cv * 1.80, inp.Cv + 1e-4))
        vals = []
        failures = []
        for c in np.linspace(lo, hi, 36):
            try:
                vals.append((float(c), residual(float(c))))
            except Exception as exc:
                failures.append(str(exc))
        if len(vals) < 2:
            return _fail(
                "Modelo de duas camadas nao convergiu para estas condicoes operacionais. O resultado nao deve ser usado como referencia.",
                inputs_used,
                warnings + failures[:3],
            )
        bracket = None
        for (c0, r0), (c1, r1) in zip(vals[:-1], vals[1:]):
            if r0 == 0.0 or r0 * r1 < 0.0:
                bracket = (c0, c1)
                break
        if bracket is None:
            best = min(vals, key=lambda item: abs(item[1]))
            return _fail(
                "Modelo de duas camadas nao convergiu para estas condicoes operacionais. O resultado nao deve ser usado como referencia.",
                inputs_used,
                warnings + [f"Sem bracket Cd-Cv. Melhor tentativa: Ct={best[0]:.5g}, Cd-Cv={best[1]:+.3e}"],
            )
        Ct_solution = brentq(lambda c: residual(float(c)), bracket[0], bracket[1], xtol=1e-10, rtol=1e-10)
        result = _run_given_ct(inp, Ct_solution, d50_coarse, frac_fines, frac_coarse)
        if result["Clim"] <= result["C1"]:
            warnings.append(_("Erro fisico ou numerico: Clim <= C1, logo C2 <= 0."))
        if result["C2"] <= 0.0:
            warnings.append(_("Erro fisico ou numerico: C2 <= 0."))
        if result["A2_over_A"] <= 0.0 or result["A2_over_A"] >= 1.0:
            warnings.append(_("Fechamento geometrico invalido: A2/A fora do intervalo 0-1."))
        if result["Clim"] < result["Ct"]:
            warnings.append(_("Atencao: Clim < Ct. Verificar se a comparacao e equivalente, pois Clim representa concentracao de grossos na camada inferior, enquanto Ct representa concentracao total in situ."))
        diagnostics = {
            "error_Cr": result.pop("error_Cr"),
            "error_Clim": result.pop("error_Clim"),
            "error_Cc": result.pop("error_Cc"),
            "iterations": result.pop("iterations"),
            "status": "converged",
            "warnings": warnings,
        }
        return {
            "converged": True,
            "message": _("Modelo de duas camadas convergiu."),
            "inputs_used": inputs_used,
            "results": result,
            "diagnostics": diagnostics,
        }
    except Exception as exc:
        return _fail(
            "Modelo de duas camadas nao convergiu para estas condicoes operacionais. O resultado nao deve ser usado como referencia.",
            {},
            [str(exc)],
        )
