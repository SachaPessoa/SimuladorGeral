import math
import os
import pickle
from pathlib import Path
import numpy as np
from django.utils.translation import gettext, gettext_lazy as _
import pandas as pd

R = 8.314462618  # J/mol/K
DEFAULT_REFERENCE_STATE = (101325.0, 298.15)
MOLLIER_MODEL_VERSION = "PR_CP_PERRY_VAPOR_ZFILTER_V5_ISOTHERM_FIX"
DEFAULT_Z_MAX_PLOT = 5.0
VAPOR_PRESSURE_SAFETY_FACTOR = 0.98
STANDARD_MOLLIER_TEMPERATURES_C = tuple(range(-250, 801, 25))
LABEL_ALL_ISOTHERMS = True
LABEL_ALL_ISOBARS = True


def refined_log_pressures_bar(P_min=0.05, P_max=5000.0):
    multipliers = (1, 1.25, 1.5, 2, 2.5, 3, 4, 5, 7.5)
    values = {P_min, P_max}
    for exponent in range(-2, 5):
        decade = 10.0**exponent
        values.update(value for value in (factor * decade for factor in multipliers) if P_min <= value <= P_max)
    return tuple(sorted(values))


STANDARD_MOLLIER_PRESSURES_BAR = refined_log_pressures_bar()


# ============================================================
# 1. Cp ideal - Perry
# Cp em J/kmol/K se C1...C5 estiverem na base Perry original
# Aqui converto para J/mol/K dividindo por 1000
# ============================================================

def cp_perry(T, C1, C2, C3, C4, C5):
    term1 = C1
    term2 = C2 * ((C3 / T) / math.sinh(C3 / T)) ** 2 if C2 != 0 else 0
    term3 = C4 * ((C5 / T) / math.cosh(C5 / T)) ** 2 if C4 != 0 else 0
    return (term1 + term2 + term3) / 1000  # J/mol/K


def integrate_cp(T1, T2, gas, n=80):
    Ts = np.linspace(T1, T2, n)
    cps = np.array([cp_perry(T, *gas["cp_coeffs"]) for T in Ts])
    return np.trapz(cps, Ts)  # J/mol


def integrate_cp_over_T(T1, T2, gas, n=80):
    Ts = np.linspace(T1, T2, n)
    vals = np.array([cp_perry(T, *gas["cp_coeffs"]) / T for T in Ts])
    return np.trapz(vals, Ts)  # J/mol/K


def relative_enthalpy_entropy(P, T, P_ref, T_ref, gas, n=50):
    """Retorna h e s relativos ao estado de referencia, sem propriedades residuais."""
    if min(P, T, P_ref, T_ref) <= 0:
        raise ValueError("Pressão absoluta e temperatura devem ser positivas.")

    h_rel = integrate_cp(T_ref, T, gas, n=n) if abs(T - T_ref) > 1e-12 else 0.0
    s_rel = integrate_cp_over_T(T_ref, T, gas, n=n) if abs(T - T_ref) > 1e-12 else 0.0

    if abs(P - P_ref) > 1e-9:
        pressures = np.linspace(P_ref, P, n)
        h_integrand = []
        s_integrand = []
        for pressure in pressures:
            Vm = molar_volume(pressure, T, gas)
            alpha = thermal_expansion_beta(pressure, T, gas)
            dVm_dT = alpha * Vm
            h_integrand.append(Vm - T * dVm_dT)
            s_integrand.append(-dVm_dT)
        h_rel += np.trapezoid(h_integrand, pressures)
        s_rel += np.trapezoid(s_integrand, pressures)

    return h_rel, s_rel


def property_state(gas, P, T, reference_state):
    """Propriedades h-s de estado, independentes de qualquer modelo de tubulacao."""
    P_ref, T_ref = reference_state
    return relative_enthalpy_entropy(P, T, P_ref, T_ref, gas)


def validate_mollier_state(gas, P, T, reference_state, saturation_margin_K=2.0):
    """Valida um estado antes de inclui-lo na visualizacao Mollier gasosa."""
    T_min = gas.get("T_valid_min", 50.0)
    T_max = gas.get("T_valid_max", max(2000.0, gas.get("Tc", 500.0) * 3))
    P_max = gas.get("P_valid_max", gas.get("Pc", 1e7) * 10)
    if T <= T_min or T >= T_max:
        return None, "temperature_outside_validity"
    if P <= 0 or P >= P_max:
        return None, "pressure_outside_validity"

    try:
        Z = z_peng_robinson(P, T, gas)
        Vm = Z * R * T / P
        rho = gas["MM"] / Vm
        alpha = thermal_expansion_beta(P, T, gas)
        beta_T = isothermal_compressibility(P, T, gas)
        Cp = cp_perry(T, *gas["cp_coeffs"])
        Cv = Cp - T * Vm * alpha**2 / beta_T
        h_rel, s_rel = property_state(gas, P, T, reference_state)
        P_ref, T_ref = reference_state
        Vm_ref = molar_volume(P_ref, T_ref, gas)
        u_rel = h_rel - (P * Vm - P_ref * Vm_ref)
    except (ValueError, OverflowError, ZeroDivisionError, FloatingPointError):
        return None, "invalid_eos"

    gamma = Cp / Cv if Cv != 0 else np.nan
    beta_s = beta_T / gamma if gamma != 0 else np.nan
    sound_speed = math.sqrt(gamma / (rho * beta_T)) if gamma > 0 and rho > 0 and beta_T > 0 else np.nan
    saturation_margin_K = gas.get("mollier_saturation_margin_K", saturation_margin_K)
    saturation = classify_saturation_state(P, T, gas, saturation_margin_K)
    phase_flags = {
        "superheated_vapor": "gas_region", "near_saturation": "near_saturation",
        "probable_phase_change": "below_saturation",
        "supercritical_temperature": "supercritical", "unavailable": "unknown",
    }
    state_data = {
        "P_Pa": P, "P_bar": P / 1e5, "T_K": T, "T_C": T - 273.15,
        "Z": Z, "Vm_m3_mol": Vm, "rho_kg_m3": rho,
        "Cp_J_molK": Cp, "Cp_kJ_kgK": Cp / (gas["MM"] * 1000),
        "Cv_J_molK": Cv, "Cv_kJ_kgK": Cv / (gas["MM"] * 1000),
        "gamma": gamma, "alpha_1_K": alpha, "betaT_1_Pa": beta_T,
        "betaS_1_Pa": beta_s, "c_m_s": sound_speed,
        "h_J_mol": h_rel, "h_kJ_kg": h_rel / (gas["MM"] * 1000),
        "s_J_molK": s_rel, "s_kJ_kgK": s_rel / (gas["MM"] * 1000),
        "u_J_mol": u_rel, "u_kJ_kg": u_rel / (gas["MM"] * 1000),
        "saturation_status": saturation["status"],
        "phase_flag": phase_flags.get(saturation["status"], "unknown"),
        "valid_numeric": True, "valid_vapor_region": True,
    }

    z_max = gas.get("Z_max_plot", DEFAULT_Z_MAX_PLOT)
    if Z > z_max:
        state_data["valid_numeric"] = False
        return state_data, "Z_above_limit"
    if not all(value > 0 for value in (Z, Vm, rho, Cp, Cv, beta_T)):
        state_data["valid_numeric"] = False
        return state_data, "divergent_property"
    if gamma <= 1:
        state_data["valid_numeric"] = False
        return state_data, "gamma_not_above_one"
    if not all(np.isfinite(value) for value in (h_rel, s_rel, u_rel)):
        state_data["valid_numeric"] = False
        return state_data, "non_finite_value"

    if gas.get("is_pure", True) and T < gas.get("Tc", 0):
        Psat = saturation_pressure(T, gas)
        if Psat is not None and P >= VAPOR_PRESSURE_SAFETY_FACTOR * Psat:
            state_data["valid_vapor_region"] = False
            return state_data, "below_or_near_saturation"

    return state_data, None


def compute_mollier_grid(
    gas, P_min, P_max, T_min, T_max,
    n_pressures, n_temperatures, reference_state,
    pressures=None, temperatures=None,
):
    """Gera uma malha Mollier pura, dependente apenas do fluido e da faixa P-T."""
    if P_min <= 0 or T_min <= 0 or P_max <= P_min or T_max <= T_min:
        raise ValueError("Faixa P-T invalida para a malha Mollier.")

    pressures = np.asarray(pressures if pressures is not None else np.linspace(P_min, P_max, n_pressures))
    temperatures = np.asarray(temperatures if temperatures is not None else np.linspace(T_min, T_max, n_temperatures))
    isobars = []
    discarded = {
        "non_finite_value": 0,
        "temperature_outside_validity": 0, "pressure_outside_validity": 0,
        "invalid_eos": 0, "divergent_property": 0, "below_or_near_saturation": 0,
        "Z_above_limit": 0, "gamma_not_above_one": 0,
    }
    for pressure in pressures:
        h_values = []
        s_values = []
        u_values = []
        states = []
        valid_values = []
        invalid_reasons = []
        for temperature in temperatures:
            state, reason = validate_mollier_state(gas, pressure, temperature, reference_state)
            if reason:
                discarded[reason] += 1
                h_values.append(np.nan)
                s_values.append(np.nan)
                u_values.append(np.nan)
                valid_values.append(False)
                invalid_reasons.append(reason)
                invalid_state = {
                    "P_Pa": pressure, "P_bar": pressure / 1e5,
                    "T_K": temperature, "T_C": temperature - 273.15,
                    "valid": False, "valid_numeric": reason == "below_or_near_saturation",
                    "valid_vapor_region": reason != "below_or_near_saturation", "phase_flag": "unknown",
                    "saturation_status": "unknown", "invalid_reason": reason,
                }
                if state is not None:
                    invalid_state.update(state)
                    invalid_state["valid"] = False
                    invalid_state["invalid_reason"] = reason
                states.append(invalid_state)
                if reason == "below_or_near_saturation":
                    states[-1]["valid_vapor_region"] = False
                    states[-1]["phase_flag"] = "below_saturation"
                    states[-1]["saturation_status"] = "probable_phase_change"
            else:
                h_values.append(state["h_J_mol"])
                s_values.append(state["s_J_molK"])
                u_values.append(state["u_J_mol"])
                valid_values.append(True)
                invalid_reasons.append("")
                states.append({**state, "valid": True, "invalid_reason": ""})
        isobars.append({
            "P_Pa": pressure,
            "T_K": temperatures.copy(),
            "h_J_mol": np.asarray(h_values),
            "s_J_molK": np.asarray(s_values),
            "u_J_mol": np.asarray(u_values),
            "valid": np.asarray(valid_values),
            "invalid_reason": np.asarray(invalid_reasons),
            "states": states,
        })

    return {
        "gas": dict(gas),
        "reference_state": tuple(reference_state),
        "P_range": (P_min, P_max),
        "T_range": (T_min, T_max),
        "pressures": pressures,
        "temperatures": temperatures,
        "isobars": isobars,
        "discarded": discarded,
    }


def standard_mollier_grid(gas, reference_state=DEFAULT_REFERENCE_STATE):
    """Malha padrão para cache dos fluidos conhecidos."""
    pressures = np.asarray(STANDARD_MOLLIER_PRESSURES_BAR) * 1e5
    temperatures = np.asarray(STANDARD_MOLLIER_TEMPERATURES_C) + 273.15
    return compute_mollier_grid(
        gas, pressures.min(), pressures.max(), temperatures.min(), temperatures.max(),
        len(pressures), len(temperatures), reference_state,
        pressures=pressures, temperatures=temperatures,
    )


def mollier_cache_path(fluid_name):
    safe_name = "".join(character if character.isalnum() else "_" for character in fluid_name)
    cache_root = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "SimuladorGas" / "mollier_cache"
    return cache_root / f"{safe_name}.pkl"


def save_mollier_cache(fluid_name, grid):
    path = mollier_cache_path(fluid_name)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("wb") as file:
            pickle.dump(grid, file, protocol=pickle.HIGHEST_PROTOCOL)
    except OSError:
        return None
    return path


def load_or_create_mollier_cache(fluid_name, gas, reference_state=DEFAULT_REFERENCE_STATE):
    """Carrega cache persistente; calcula uma unica vez quando ainda nao existe."""
    path = mollier_cache_path(fluid_name)
    vapor_pressure_signature = tuple(sorted((gas.get("vapor_pressure") or {}).items()))
    signature = (
        MOLLIER_MODEL_VERSION,
        gas["MM"], gas["Tc"], gas["Pc"], gas["omega"], tuple(gas["cp_coeffs"]),
        gas.get("is_pure", True), vapor_pressure_signature,
        gas.get("mollier_saturation_margin_K", 2.0),
        gas.get("Z_max_plot", DEFAULT_Z_MAX_PLOT), reference_state,
    )
    if path.exists():
        try:
            with path.open("rb") as file:
                grid = pickle.load(file)
            if grid.get("cache_signature") == signature:
                return grid
        except (OSError, EOFError, pickle.PickleError):
            pass
    grid = standard_mollier_grid(gas, reference_state)
    grid["isotherms"] = compute_mollier_isotherms(
        grid, len(STANDARD_MOLLIER_TEMPERATURES_C), len(STANDARD_MOLLIER_PRESSURES_BAR)
    )
    grid["cache_signature"] = signature
    grid["cache_fluid"] = fluid_name
    save_mollier_cache(fluid_name, grid)
    return grid


def compute_mollier_isotherms(mollier_grid, n_isotherms, n_points=None):
    """Gera isotermicas usando somente os dados fixos da malha Mollier."""
    gas = mollier_grid["gas"]
    reference_state = mollier_grid["reference_state"]
    P_min, P_max = mollier_grid["P_range"]
    T_min, T_max = mollier_grid["T_range"]
    n_points = n_points or len(mollier_grid["pressures"])
    if n_points == len(mollier_grid["pressures"]):
        pressures = np.asarray(mollier_grid["pressures"]).copy()
    else:
        pressures = np.geomspace(P_min, P_max, n_points)
    isotherms = []
    if n_isotherms == len(mollier_grid["temperatures"]):
        temperatures = np.asarray(mollier_grid["temperatures"]).copy()
    else:
        temperatures = np.linspace(T_min, T_max, n_isotherms)
    for temperature in temperatures:
        h_values = []
        s_values = []
        valid_values = []
        for pressure in pressures:
            state, reason = validate_mollier_state(gas, pressure, temperature, reference_state)
            if reason:
                h_values.append(np.nan)
                s_values.append(np.nan)
                valid_values.append(False)
            else:
                h_values.append(state["h_J_mol"])
                s_values.append(state["s_J_molK"])
                valid_values.append(True)
        isotherms.append({
            "T_K": temperature,
            "P_Pa": pressures.copy(),
            "h_J_mol": np.asarray(h_values),
            "s_J_molK": np.asarray(s_values),
            "valid": np.asarray(valid_values),
        })
    return isotherms


def overlay_pipeline_path_on_mollier(mollier_grid, pipeline_results):
    """Prepara somente a sobreposicao da trajetoria; nunca recalcula a malha."""
    gas = mollier_grid["gas"]
    reference_state = mollier_grid["reference_state"]
    h_values, s_values = [], []
    for _, row in pipeline_results.iterrows():
        h_rel, s_rel = property_state(gas, row["P_Pa"], row["T_K"], reference_state)
        h_values.append(h_rel)
        s_values.append(s_rel)
    return {
        "reference_state": mollier_grid["reference_state"],
        "h_J_mol": np.asarray(h_values),
        "s_J_molK": np.asarray(s_values),
        "P_Pa": pipeline_results["P_Pa"].to_numpy(copy=True),
        "T_K": pipeline_results["T_K"].to_numpy(copy=True),
    }


def lee_kesler_saturation_pressure(T, gas):
    """Estimativa Lee-Kesler/Pitzer de pressao de saturacao, em Pa."""
    Tc = gas.get("Tc")
    Pc = gas.get("Pc")
    omega = gas.get("omega")
    if Tc is None or Pc is None or omega is None or T <= 0 or T >= Tc:
        return None

    Tr = T / Tc
    f0 = 5.92714 - 6.09648 / Tr - 1.28862 * math.log(Tr) + 0.169347 * Tr**6
    f1 = 15.2518 - 15.6875 / Tr - 13.4721 * math.log(Tr) + 0.43577 * Tr**6
    pressure = Pc * math.exp(f0 + omega * f1)
    return pressure if 0 < pressure < Pc else None


def saturation_pressure(P_temperature, gas):
    """Pressão de saturação: correlação específica ou Lee-Kesler/Pitzer."""
    T = P_temperature
    if not gas.get("is_pure", True):
        return None
    correlation = gas.get("vapor_pressure")
    if correlation:
        kind = correlation.get("type", "").lower()
        T_input = T - 273.15 if correlation.get("T_unit", "K") == "C" else T
        valid = correlation.get("T_min", -math.inf) <= T_input <= correlation.get("T_max", math.inf)
        if valid and kind == "antoine":
            pressure = 10 ** (
                correlation["A"] - correlation["B"] / (T_input + correlation["C"])
            )
            factors = {"Pa": 1.0, "bar": 1e5, "mmHg": 133.322368}
            pressure *= factors[correlation.get("P_unit", "Pa")]
            if pressure > 0:
                return pressure
    return lee_kesler_saturation_pressure(T, gas)


def saturation_temperature(P, gas, max_iter=80):
    """Temperatura de saturacao estimada para P < Pc, em K."""
    if not gas.get("is_pure", True):
        return None
    Tc = gas.get("Tc")
    Pc = gas.get("Pc")
    if Tc is None or Pc is None or P <= 0 or P >= Pc:
        return None

    correlation = gas.get("vapor_pressure")
    if correlation and correlation.get("type", "").lower() == "antoine":
        factors = {"Pa": 1.0, "bar": 1e5, "mmHg": 133.322368}
        pressure_input = P / factors[correlation.get("P_unit", "Pa")]
        denominator = correlation["A"] - math.log10(pressure_input)
        if abs(denominator) > 1e-12:
            T_input = correlation["B"] / denominator - correlation["C"]
            if correlation.get("T_min", -math.inf) <= T_input <= correlation.get("T_max", math.inf):
                return T_input + 273.15 if correlation.get("T_unit", "K") == "C" else T_input

    low = max(1.0, 0.20 * Tc)
    high = Tc * (1 - 1e-8)
    P_low = lee_kesler_saturation_pressure(low, gas)
    if P_low is None or P < P_low:
        return None

    for _ in range(max_iter):
        middle = 0.5 * (low + high)
        P_middle = lee_kesler_saturation_pressure(middle, gas)
        if P_middle is None:
            high = middle
        elif P_middle < P:
            low = middle
        else:
            high = middle
    return 0.5 * (low + high)


def classify_saturation_state(P, T, gas, margin_K=5.0):
    """Classifica a proximidade da fronteira liquido-vapor para fluido puro."""
    if not gas.get("is_pure", True):
        return {"status": "unavailable", "Tsat_K": np.nan, "Psat_Pa": np.nan, "deltaT_K": np.nan}
    Tc = gas.get("Tc")
    Pc = gas.get("Pc")
    if Tc is None or Pc is None:
        return {"status": "unavailable", "Tsat_K": np.nan, "Psat_Pa": np.nan, "deltaT_K": np.nan}
    if T >= Tc:
        return {"status": "supercritical_temperature", "Tsat_K": np.nan, "Psat_Pa": np.nan, "deltaT_K": np.nan}
    if P >= Pc:
        return {"status": "probable_phase_change", "Tsat_K": np.nan, "Psat_Pa": saturation_pressure(T, gas), "deltaT_K": np.nan}

    Tsat = saturation_temperature(P, gas)
    Psat = saturation_pressure(T, gas)
    if Tsat is None:
        return {"status": "unavailable", "Tsat_K": np.nan, "Psat_Pa": Psat or np.nan, "deltaT_K": np.nan}

    delta_T = T - Tsat
    if delta_T <= 0:
        status = "probable_phase_change"
    elif delta_T <= margin_K:
        status = "near_saturation"
    else:
        status = "superheated_vapor"
    return {"status": status, "Tsat_K": Tsat, "Psat_Pa": Psat or np.nan, "deltaT_K": delta_T}


def compute_saturation_curve(
    gas, T_min, T_max, reference_state, n_points=80, P_min=None, P_max=None,
):
    """Curva indicativa de saturacao para uso no Mollier monofasico."""
    if not gas.get("is_pure", True):
        return None
    Tc = gas.get("Tc")
    if Tc is None or gas.get("Pc") is None or gas.get("omega") is None:
        return None
    upper = min(T_max, Tc * (1 - 1e-5))
    lower = max(T_min, 0.20 * Tc)
    if upper <= lower:
        return None

    temperatures = np.linspace(lower, upper, n_points)
    pressures, enthalpies, entropies, valid_temperatures = [], [], [], []
    for temperature in temperatures:
        pressure = saturation_pressure(temperature, gas)
        if pressure is None:
            continue
        if P_min is not None and pressure < P_min:
            continue
        if P_max is not None and pressure > P_max:
            continue
        try:
            h_rel, s_rel = property_state(gas, pressure, temperature, reference_state)
        except (ValueError, OverflowError, ZeroDivisionError, FloatingPointError):
            continue
        pressures.append(pressure)
        valid_temperatures.append(temperature)
        enthalpies.append(h_rel)
        entropies.append(s_rel)
    if len(pressures) < 2:
        return None
    return {
        "P_Pa": np.asarray(pressures), "T_K": np.asarray(valid_temperatures),
        "h_J_mol": np.asarray(enthalpies), "s_J_molK": np.asarray(entropies),
        "method": "Lee-Kesler/Pitzer",
    }


def automatic_mollier_window(
    P_in, T_in, P_out, T_out, pressure_margin=0.50, temperature_margin=0.50,
    small_pressure_fraction=0.25, small_temperature_fraction=0.10,
    minimum_pressure=101325.0, minimum_temperature=50.0,
):
    """Define uma janela P-T ampliada ao redor dos pontos operacionais."""
    P_op_min, P_op_max = sorted((P_in, P_out))
    T_op_min, T_op_max = sorted((T_in, T_out))
    dP = P_op_max - P_op_min
    dT = T_op_max - T_op_min

    if dP <= max(P_op_max * 1e-6, 1.0):
        P_min = P_op_min * (1 - small_pressure_fraction)
        P_max = P_op_max * (1 + small_pressure_fraction)
    else:
        P_min = P_op_min - pressure_margin * dP
        P_max = P_op_max + pressure_margin * dP

    if dT <= max(T_op_max * 1e-6, 1e-3):
        T_min = T_op_min * (1 - small_temperature_fraction)
        T_max = T_op_max * (1 + small_temperature_fraction)
    else:
        T_min = T_op_min - temperature_margin * dT
        T_max = T_op_max + temperature_margin * dT

    pressure_floor = minimum_pressure if P_op_min >= minimum_pressure else 1.0
    temperature_floor = minimum_temperature if T_op_min >= minimum_temperature else 1.0
    P_min = max(P_min, pressure_floor)
    T_min = max(T_min, temperature_floor)
    P_max = max(P_max, P_op_max * 1.001)
    T_max = max(T_max, T_op_max * 1.001)
    return P_min, P_max, T_min, T_max


# ============================================================
# 2. Peng-Robinson
# ============================================================

def peng_robinson_params(T, gas):
    Tc = gas["Tc"]
    Pc = gas["Pc"]
    w = gas["omega"]

    kappa = 0.37464 + 1.54226 * w - 0.26992 * w**2
    alpha = (1 + kappa * (1 - math.sqrt(T / Tc))) ** 2

    a = 0.45724 * R**2 * Tc**2 / Pc
    b = 0.07780 * R * Tc / Pc

    return a, b, alpha


def z_peng_robinson(P, T, gas):
    a, b, alpha = peng_robinson_params(T, gas)

    A = a * alpha * P / (R**2 * T**2)
    B = b * P / (R * T)

    # Cúbica PR:
    # Z^3 - (1-B)Z^2 + (A - 3B^2 - 2B)Z - (AB - B^2 - B^3) = 0
    coeffs = [
        1,
        -(1 - B),
        A - 3 * B**2 - 2 * B,
        -(A * B - B**2 - B**3),
    ]

    roots = np.roots(coeffs)
    real_roots = [r.real for r in roots if abs(r.imag) < 1e-8]

    if not real_roots:
        raise ValueError("Peng-Robinson não encontrou raiz real para Z.")

    # Para fase vapor, usar a maior raiz real
    return max(real_roots)


def molar_volume(P, T, gas):
    Z = z_peng_robinson(P, T, gas)
    return Z * R * T / P  # m3/mol


# ============================================================
# 3. Derivadas numéricas: beta e compressibilidade isotérmica
# ============================================================

def thermal_expansion_beta(P, T, gas, dT=0.01):
    dT = min(dT, T * 0.25)
    Vm = molar_volume(P, T, gas)
    Vm_plus = molar_volume(P, T + dT, gas)
    Vm_minus = molar_volume(P, T - dT, gas)

    dVm_dT = (Vm_plus - Vm_minus) / (2 * dT)
    return dVm_dT / Vm  # 1/K


def isothermal_compressibility(P, T, gas, dP=None):
    if dP is None:
        dP = min(max(10.0, P * 1e-5), P * 0.25)

    Vm = molar_volume(P, T, gas)
    Vm_plus = molar_volume(P + dP, T, gas)
    Vm_minus = molar_volume(P - dP, T, gas)

    dVm_dP = (Vm_plus - Vm_minus) / (2 * dP)
    return -dVm_dP / Vm  # 1/Pa


# ============================================================
# 4. Joule-Thomson
# ============================================================

def joule_thomson_mu(P, T, gas, Vm=None, Cp=None, alpha=None):
    """Coeficiente Joule-Thomson em K/Pa, mantendo compatibilidade da API."""
    Vm = molar_volume(P, T, gas) if Vm is None else Vm
    Cp = cp_perry(T, *gas["cp_coeffs"]) if Cp is None else Cp
    alpha = thermal_expansion_beta(P, T, gas) if alpha is None else alpha
    return Vm * (T * alpha - 1) / Cp


# ============================================================
# 5. Viscosidade
# ============================================================

def gas_viscosity_sutherland(T, mu_ref=1.8e-5, T_ref=293.15, S=110.4):
    return mu_ref * (T / T_ref)**1.5 * (T_ref + S) / (T + S)


# ============================================================
# 6. Fator de atrito Darcy
# ============================================================

def friction_factor_darcy(Re, rel_roughness):
    if Re <= 0:
        raise ValueError("Reynolds inválido.")

    if Re < 2000:
        return 64 / Re

    # Swamee-Jain como aproximação explícita inicial
    f = 0.25 / (math.log10(rel_roughness / 3.7 + 5.74 / Re**0.9))**2

    # Refinamento Colebrook
    for _ in range(30):
        lhs = 1 / math.sqrt(f)
        rhs = -2 * math.log10(rel_roughness / 3.7 + 2.51 / (Re * math.sqrt(f)))
        error = lhs - rhs

        if abs(error) < 1e-10:
            break

        # Newton numérico simples
        df = f * 1e-5
        lhs2 = 1 / math.sqrt(f + df)
        rhs2 = -2 * math.log10(rel_roughness / 3.7 + 2.51 / (Re * math.sqrt(f + df)))
        error2 = lhs2 - rhs2

        deriv = (error2 - error) / df
        f = f - error / deriv

        if f <= 0:
            f = 1e-4

    return f


# ============================================================
# 7. Estado local
# ============================================================

def calculate_state(P, T, mdot, D, roughness, gas):
    if P <= 0 or T <= 0:
        raise ValueError("Pressão absoluta e temperatura devem ser maiores que zero.")

    Z = z_peng_robinson(P, T, gas)
    Vm = Z * R * T / P

    MM = gas["MM"]  # kg/mol
    rho = MM / Vm          # kg/m3

    # Propriedades reais obtidas numericamente a partir de Peng-Robinson.
    alpha = thermal_expansion_beta(P, T, gas)
    beta_T = isothermal_compressibility(P, T, gas)
    Cp = cp_perry(T, *gas["cp_coeffs"])
    Cv = Cp - T * Vm * alpha**2 / beta_T
    if Cv <= 0 or beta_T <= 0:
        raise ValueError("Estado termodinamico invalido: Cv ou beta_T nao positivo.")

    gamma = Cp / Cv
    Cp_mass = Cp / MM
    beta_s_thermo = beta_T - T * alpha**2 / (rho * Cp_mass)
    beta_s_gamma = beta_T / gamma
    if beta_s_gamma <= 0:
        raise ValueError("Compressibilidade isentropica nao positiva.")

    beta_s_rel_error = abs(beta_s_thermo - beta_s_gamma) / beta_s_gamma
    c_real = math.sqrt(gamma / (rho * beta_T))

    Qv = mdot / rho        # m3/s
    area = math.pi * D**2 / 4
    v = Qv / area

    if gas.get("viscosity_model", "sutherland") == "constant":
        mu = gas["mu_constant"]
    else:
        mu = gas_viscosity_sutherland(
            T,
            mu_ref=gas.get("mu_ref", 1.8e-5),
            T_ref=gas.get("T_mu_ref", 293.15),
            S=gas.get("S_sutherland", 110.4),
        )

    Re = rho * v * D / mu
    fD = friction_factor_darcy(Re, roughness / D)
    mu_JT = joule_thomson_mu(P, T, gas, Vm=Vm, Cp=Cp, alpha=alpha)
    Mach = v / c_real

    return {
        "P": P,
        "T": T,
        "Z": Z,
        "Vm": Vm,
        "rho": rho,
        "Qv": Qv,
        "v": v,
        "mu": mu,
        "Re": Re,
        "fD": fD,
        "Cp": Cp,
        "Cp_mass": Cp_mass,
        "Cv": Cv,
        "gamma": gamma,
        "beta": alpha,
        "alpha": alpha,
        "beta_T": beta_T,
        "beta_s_thermo": beta_s_thermo,
        "beta_s_gamma": beta_s_gamma,
        "beta_s_rel_error": beta_s_rel_error,
        "mu_JT": mu_JT,
        "c": c_real,
        "Mach": Mach,
    }


# ============================================================
# 8. Simulação da linha
# ============================================================

def temperature_by_mach(P2, T_reference, st1, mdot, D, roughness, gas, max_iter=50):
    """Calcula T2 conservando a temperatura de estagnacao."""
    T2 = T_reference
    numerator = 1 + ((st1["gamma"] - 1) / 2) * st1["Mach"]**2
    for _ in range(max_iter):
        st2 = calculate_state(P2, T2, mdot, D, roughness, gas)
        denominator = 1 + ((st1["gamma"] - 1) / 2) * st2["Mach"]**2
        updated = T_reference * numerator / denominator
        if abs(updated - T2) < 1e-8:
            return updated
        T2 = 0.5 * (T2 + updated)
    return T2


def simulate_pipeline(
    gas,
    P0,
    T0,
    mdot,
    D,
    roughness,
    L,
    dx,
    thermal_model="joule_thomson",
    z0=0.0,
    dz_total=0.0,
):
    results = []

    P = P0
    T = T0
    x = 0.0
    z = z0

    H_acc = 0.0  # J/mol relativo
    S_acc = 0.0  # J/mol/K relativo
    U_acc = 0.0  # J/mol relativo
    Qflow_acc = 0.0  # J/mol relativo
    MM = gas["MM"]
    g = 9.80665
    v0 = None

    while x < L:
        step = min(dx, L - x)
        z2 = z0 + dz_total * ((x + step) / L)

        st1 = calculate_state(P, T, mdot, D, roughness, gas)
        if v0 is None:
            v0 = st1["v"]

        dP = st1["fD"] * (step / D) * (st1["rho"] * st1["v"]**2 / 2)
        P2 = P - dP

        if P2 <= 0:
            raise ValueError("Pressão ficou negativa ou zero. Reduza dx ou revise dados.")

        # Temperatura final
        if thermal_model == "isothermal":
            T2 = T

        elif thermal_model == "joule_thomson":
            T2 = T + st1["mu_JT"] * (P2 - P)

        elif thermal_model == "mach":
            T2 = temperature_by_mach(P2, T, st1, mdot, D, roughness, gas)

        elif thermal_model == "combined":
            T_jt = T + st1["mu_JT"] * (P2 - P)
            T2 = temperature_by_mach(P2, T_jt, st1, mdot, D, roughness, gas)

        else:
            raise ValueError("Modelo termico invalido.")

        st2 = calculate_state(P2, T2, mdot, D, roughness, gas)

        # Delta H por integração numérica diferencial:
        # dH = Cp dT + [Vm - T(dVm/dT)_P] dP
        dH_T = integrate_cp(T, T2, gas) if abs(T2 - T) > 1e-12 else 0.0
        dVm_dT = st1["beta"] * st1["Vm"]
        dH_P = (st1["Vm"] - T * dVm_dT) * (P2 - P)
        dH = dH_T + dH_P

        # Delta S:
        # dS = Cp/T dT - (dVm/dT)_P dP
        dS_T = integrate_cp_over_T(T, T2, gas) if abs(T2 - T) > 1e-12 else 0.0
        dS_P = -dVm_dT * (P2 - P)
        dS = dS_T + dS_P

        # Delta U = Delta H - Delta(PVm)
        dPV = P2 * st2["Vm"] - P * st1["Vm"]
        dU = dH - dPV

        # Trabalho de expansão específico molar aproximado:
        # delta W_by_gas = integral P dV ≈ Pmedio * Delta Vm
        W_exp = 0.5 * (P + P2) * (st2["Vm"] - st1["Vm"])  # J/mol

        # Balanco de energia para escoamento continuo, sem trabalho de eixo.
        dKE = MM * (st2["v"]**2 - st1["v"]**2) / 2
        dPE = MM * g * (z2 - z)
        Q_flow = dH + dKE + dPE

        H_acc += dH
        S_acc += dS
        U_acc += dU
        Qflow_acc += Q_flow

        row = {
            "x_m": x,
            "z_m": z,
            "P_Pa": P,
            "T_K": T,
            "dP_Pa": dP,
            "Z": st1["Z"],
            "Vm_m3_mol": st1["Vm"],
            "rho_kg_m3": st1["rho"],
            "Qv_m3_s": st1["Qv"],
            "v_m_s": st1["v"],
            "mu_Pa_s": st1["mu"],
            "Re": st1["Re"],
            "fD": st1["fD"],
            "Cp_J_molK": st1["Cp"],
            "Cp_J_kgK": st1["Cp_mass"],
            "Cv_J_molK": st1["Cv"],
            "gamma": st1["gamma"],
            "beta_1_K": st1["beta"],
            "betaT_1_Pa": st1["beta_T"],
            "betaS_thermo_1_Pa": st1["beta_s_thermo"],
            "betaS_gamma_1_Pa": st1["beta_s_gamma"],
            "betaS_rel_error": st1["beta_s_rel_error"],
            "muJT_K_Pa": st1["mu_JT"],
            "c_m_s": st1["c"],
            "Mach": st1["Mach"],
            "dH_J_mol": dH,
            "dS_J_molK": dS,
            "dU_J_mol": dU,
            "Wexp_J_mol": W_exp,
            "dKE_J_mol": dKE,
            "dPE_J_mol": dPE,
            "Qflow_J_mol": Q_flow,
            "H_rel_J_mol": H_acc - dH,
            "S_rel_J_molK": S_acc - dS,
            "U_rel_J_mol": U_acc - dU,
            "Qflow_rel_J_mol": Qflow_acc - Q_flow,
            "mechanical_energy_J_kg": (
                (H_acc - dH) / MM + (st1["v"]**2 - v0**2) / 2 + g * (z - z0)
            ),
        }

        results.append(row)

        P = P2
        T = T2
        x += step
        z = z2

    df = pd.DataFrame(results)
    df.attrs.update({
        "final_P": P, "final_T": T, "final_z": z,
        "final_H": H_acc, "final_S": S_acc, "final_U": U_acc, "final_Qflow": Qflow_acc,
    })
    return df


# ============================================================
# 9. Interface grafica
# ============================================================

def add_pipeline_endpoint(df, gas, mdot, D, roughness, L, thermal_model):
    """Inclui no perfil o estado calculado exatamente em x = L."""
    if df.empty:
        return df

    last = df.iloc[-1]
    P = df.attrs.get("final_P", last["P_Pa"] - last["dP_Pa"])
    T = df.attrs.get("final_T", last["T_K"])
    z = df.attrs.get("final_z", last.get("z_m", 0.0))

    state = calculate_state(P, T, mdot, D, roughness, gas)
    endpoint = {column: np.nan for column in df.columns}
    endpoint.update({
        "x_m": L,
        "z_m": z,
        "P_Pa": P,
        "T_K": T,
        "dP_Pa": 0.0,
        "Z": state["Z"],
        "Vm_m3_mol": state["Vm"],
        "rho_kg_m3": state["rho"],
        "Qv_m3_s": state["Qv"],
        "v_m_s": state["v"],
        "mu_Pa_s": state["mu"],
        "Re": state["Re"],
        "fD": state["fD"],
        "Cp_J_molK": state["Cp"],
        "Cp_J_kgK": state["Cp_mass"],
        "Cv_J_molK": state["Cv"],
        "gamma": state["gamma"],
        "beta_1_K": state["beta"],
        "betaT_1_Pa": state["beta_T"],
        "betaS_thermo_1_Pa": state["beta_s_thermo"],
        "betaS_gamma_1_Pa": state["beta_s_gamma"],
        "betaS_rel_error": state["beta_s_rel_error"],
        "muJT_K_Pa": state["mu_JT"],
        "c_m_s": state["c"],
        "Mach": state["Mach"],
        "H_rel_J_mol": df.attrs.get("final_H", last["H_rel_J_mol"]),
        "S_rel_J_molK": df.attrs.get("final_S", last["S_rel_J_molK"]),
        "U_rel_J_mol": df.attrs.get("final_U", last["U_rel_J_mol"]),
        "Qflow_rel_J_mol": df.attrs.get("final_Qflow", last["Qflow_rel_J_mol"]),
        "mechanical_energy_J_kg": (
            df.attrs.get("final_H", last["H_rel_J_mol"]) / gas["MM"]
            + (state["v"]**2 - df.iloc[0]["v_m_s"]**2) / 2
            + 9.80665 * (z - df.iloc[0]["z_m"])
        ),
    })
    return pd.concat([df, pd.DataFrame([endpoint])], ignore_index=True)


def add_saturation_diagnostics(df, gas, margin_K=5.0):
    """Adiciona diagnósticos indicativos de saturação sem alterar a simulação."""
    diagnostics = [
        classify_saturation_state(row["P_Pa"], row["T_K"], gas, margin_K)
        for _, row in df.iterrows()
    ]
    result = df.copy()
    result["Tsat_K"] = [item["Tsat_K"] for item in diagnostics]
    result["Psat_Pa"] = [item["Psat_Pa"] for item in diagnostics]
    result["superheat_deltaT_K"] = [item["deltaT_K"] for item in diagnostics]
    result["saturation_status"] = [item["status"] for item in diagnostics]
    result["mollier_state_valid"] = [
        item["status"] not in ("near_saturation", "probable_phase_change")
        for item in diagnostics
    ]
    result.attrs.update(df.attrs)
    return result


def add_mass_basis_properties(df, gas):
    """Adiciona propriedades em base massica sem remover a base molar."""
    result = df.copy()
    MM = gas["MM"]
    result["h_kJ_kg"] = result["H_rel_J_mol"] / (MM * 1000)
    result["s_kJ_kgK"] = result["S_rel_J_molK"] / (MM * 1000)
    result["u_kJ_kg"] = result["U_rel_J_mol"] / (MM * 1000)
    result["Cp_kJ_kgK"] = result["Cp_J_molK"] / (MM * 1000)
    result["Cv_kJ_kgK"] = result["Cv_J_molK"] / (MM * 1000)
    result.attrs.update(df.attrs)
    return result

FLUIDS = {
    "Air": {
        "formula": "N2 + O2", "MM": 28.96, "Pc_kgf_cm2": 38.44, "Tc": 132.40,
        "omega": 0.038, "C1": 28960, "C2": 93900, "C3": 3120, "C4": 7580, "C5": 1484.0,
    },
    "Water": {
        "formula": "H2O", "MM": 18.02, "Pc_kgf_cm2": 225.56, "Tc": 647.30,
        "omega": 0.345, "C1": 33360, "C2": 26790, "C3": 2610.5, "C4": 8900, "C5": 1169,
        "vapor_pressure": {
            "type": "antoine", "A": 8.07131, "B": 1730.63, "C": 233.426,
            "T_unit": "C", "P_unit": "mmHg", "T_min": 1.0, "T_max": 100.0,
        },
    },
    "Methane": {
        "formula": "CH4", "MM": 16.04, "Pc_kgf_cm2": 46.91, "Tc": 190.60,
        "omega": 0.012, "C1": 33300, "C2": 79930, "C3": 2086, "C4": 41600, "C5": 991.96,
    },
    "Argonio": {
        "formula": "Ar", "MM": 39.95, "Pc_kgf_cm2": 49.95, "Tc": 150.90,
        "omega": 0.0, "C1": 20790, "C2": 0, "C3": 0, "C4": 0, "C5": 0,
    },
    "Carbon Dioxide": {
        "formula": "CO2", "MM": 44.01, "Pc_kgf_cm2": 75.26, "Tc": 304.40,
        "omega": 0.224, "C1": 29370, "C2": 34540, "C3": 1428, "C4": 26400, "C5": 588.0,
    },
    "Carbon Monoxide": {
        "formula": "CO", "MM": 28.01, "Pc_kgf_cm2": 35.69, "Tc": 133.10,
        "omega": 0.048, "C1": 29110, "C2": 8770, "C3": 3085, "C4": 8460, "C5": 1538.2,
    },
    "Ammonia": {
        "formula": "NH3", "MM": 17.03, "Pc_kgf_cm2": 115.02, "Tc": 405.50,
        "omega": 0.253, "C1": 33430, "C2": 48980, "C3": 2360, "C4": 22560, "C5": 882.0,
    },
    "Nitrogen": {
        "formula": "N2", "MM": 28.01, "Pc_kgf_cm2": 34.67, "Tc": 126.20,
        "omega": 0.038, "C1": 29110, "C2": 8610, "C3": 1701.6, "C4": 100, "C5": 909.79,
    },
    "Oxygen": {
        "formula": "O2", "MM": 32.00, "Pc_kgf_cm2": 51.80, "Tc": 154.70,
        "omega": 0.022, "C1": 29100, "C2": 10040, "C3": 2526.5, "C4": 9360, "C5": 1153.8,
    },
    "Ethanol": {
        "formula": "C2H6O", "MM": 46.07, "Pc_kgf_cm2": 62.61, "Tc": 513.90,
        "omega": 0.645, "C1": 49200, "C2": 145770, "C3": 1662.6, "C4": 93900, "C5": 744.7,
    },
    "Hydrogen": {
        "formula": "H2", "MM": 2.02, "Pc_kgf_cm2": 13.26, "Tc": 33.20,
        "omega": -0.216, "C1": 27620, "C2": 95600, "C3": 2466, "C4": 3760, "C5": 567.6,
    },
}
CUSTOM_FLUID = "Generico / personalizado"
DEFAULT_VISCOSITY_CP = {
    "Air": 0.0181, "Water": 0.0140, "Methane": 0.0110, "Argonio": 0.0223,
    "Carbon Dioxide": 0.0148, "Carbon Monoxide": 0.0175, "Ammonia": 0.0098,
    "Nitrogen": 0.0176, "Oxygen": 0.0202, "Ethanol": 0.0120, "Hydrogen": 0.0089,
}
PIPELINE_FIELDS = [
    ("P0_bar_a", _("Pressão absoluta de entrada"), "bar(a)", "4.2"),
    ("T0_C", _("Temperatura de entrada"), "degC", "149.85"),
    ("mdot_kg_h", _("Vazão mássica"), "kg/h", "1675.8"),
    ("D_m", _("Diâmetro interno"), "m", "0.089"),
    ("rough_m", _("Rugosidade absoluta"), "m", "0.000149"),
    ("L_m", _("Comprimento"), "m", "600"),
    ("dx_m", _("Passo de cálculo"), "m", "5"),
    ("z0_m", _("Elevação inicial"), "m", "0"),
    ("dz_total_m", _("Variação de elevação"), "m", "0"),
]
GAS_FIELDS = [
    ("MM_kg_kmol", _("Massa molar"), "kg/kmol", "16.04"),
    ("Tc_C", _("Temperatura crítica"), "degC", "-82.55"),
    ("Pc_bar_a", _("Pressão crítica absoluta"), "bar(a)", "46.0"),
    ("omega", _("Fator acêntrico"), "-", "0.012"),
    ("C1", "Perry C1", "-", "33300"),
    ("C2", "Perry C2", "-", "79930"),
    ("C3", "Perry C3", "-", "2086"),
    ("C4", "Perry C4", "-", "41600"),
    ("C5", "Perry C5", "-", "991.96"),
    ("mu_ref_cP", _("Viscosidade de referência"), "cP", "0.011"),
    ("T_mu_ref_C", _("Temperatura de referência da viscosidade"), "degC", "20"),
    ("S_sutherland", _("Constante de Sutherland"), "K", "170"),
    ("mu_constant_Pa_s", _("Viscosidade dinâmica"), "Pa.s", "1.10e-5"),
    ("saturation_margin_K", _("Margem de alerta de saturação"), "K", "5"),
]


THERMAL_MODEL_LABELS = {
    "isothermal": "Isotermico",
    "combined": "Compressivel",
}


def build_known_gas(fluid_name, viscosity_pa_s=None, z_max_plot=DEFAULT_Z_MAX_PLOT):
    if fluid_name not in FLUIDS:
        raise ValueError("Fluido conhecido invalido.")
    fluid = FLUIDS[fluid_name]
    viscosity_cp = DEFAULT_VISCOSITY_CP.get(fluid_name, 0.011)
    gas = {
        "MM": fluid["MM"] / 1000,
        "Tc": fluid["Tc"],
        "Pc": fluid["Pc_kgf_cm2"] * 0.980665 * 1e5,
        "omega": fluid["omega"],
        "cp_coeffs": tuple(fluid[f"C{i}"] for i in range(1, 6)),
        "mu_ref": viscosity_cp * 1e-3,
        "T_mu_ref": 293.15,
        "S_sutherland": 170.0,
        "mu_constant": viscosity_pa_s if viscosity_pa_s is not None else viscosity_cp * 1e-3,
        "viscosity_model": "constant",
        "is_pure": fluid_name != "Air",
        "Z_max_plot": z_max_plot,
    }
    if "vapor_pressure" in fluid:
        gas["vapor_pressure"] = dict(fluid["vapor_pressure"])
    return gas


def build_custom_gas(values):
    return {
        "MM": values["MM_kg_kmol"] / 1000,
        "Tc": values["Tc_C"] + 273.15,
        "Pc": values["Pc_bar_a"] * 1e5,
        "omega": values["omega"],
        "cp_coeffs": tuple(values[f"C{i}"] for i in range(1, 6)),
        "mu_ref": values["mu_constant_Pa_s"],
        "T_mu_ref": 293.15,
        "S_sutherland": 170.0,
        "mu_constant": values["mu_constant_Pa_s"],
        "viscosity_model": "constant",
        "is_pure": True,
        "Z_max_plot": values.get("Z_max_plot", DEFAULT_Z_MAX_PLOT),
    }


def finite_or_none(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return value
    return number if np.isfinite(number) else None


def records_from_dataframe(df):
    return [{key: finite_or_none(value) for key, value in row.items()} for row in df.to_dict(orient="records")]


def run_gas_pipeline(gas, args, fluid_name, mollier_options=None):
    mollier_options = mollier_options or {}
    results = simulate_pipeline(gas=gas, **args)
    results = add_pipeline_endpoint(results, gas, args["mdot"], args["D"], args["roughness"], args["L"], args["thermal_model"])
    results = add_saturation_diagnostics(results, gas, mollier_options.get("saturation_margin_K", 5.0))
    results = add_mass_basis_properties(results, gas)
    first = results.iloc[0]
    last = results.iloc[-1]
    summary = {
        "fluid_name": fluid_name,
        "thermal_model": gettext(THERMAL_MODEL_LABELS.get(args["thermal_model"], args["thermal_model"])),
        "P_in_bar": first["P_Pa"] / 1e5,
        "P_out_bar": last["P_Pa"] / 1e5,
        "delta_P_bar": (first["P_Pa"] - last["P_Pa"]) / 1e5,
        "T_in_K": first["T_K"],
        "T_out_K": last["T_K"],
        "delta_T_K": last["T_K"] - first["T_K"],
        "mdot_kg_s": args["mdot"],
        "Qv_in_m3_h": first["Qv_m3_s"] * 3600,
        "Qv_out_m3_h": last["Qv_m3_s"] * 3600,
        "v_in_m_s": first["v_m_s"],
        "v_out_m_s": last["v_m_s"],
        "v_mean_m_s": results["v_m_s"].mean(),
        "Z_in": first["Z"],
        "Z_out": last["Z"],
        "Z_mean": results["Z"].mean(),
        "delta_h_kJ_kg": last["h_kJ_kg"],
        "delta_u_kJ_kg": last["u_kJ_kg"],
        "delta_s_kJ_kgK": last["s_kJ_kgK"],
        "Re_mean": results["Re"].mean(),
        "fD_mean": results["fD"].mean(),
        "Mach_max": results["Mach"].max(),
    }
    return {
        "summary": {key: finite_or_none(value) for key, value in summary.items()},
        "rows": records_from_dataframe(results),
        "charts": build_chart_payload(results, gas, fluid_name, mollier_options),
        "diagnostics": build_diagnostics(results),
    }


def series(df, column, factor=1.0, offset=0.0):
    return [finite_or_none(value * factor + offset) for value in df[column].to_numpy(dtype=float)]


def build_chart_payload(results, gas, fluid_name, mollier_options):
    x = series(results, "x_m")
    charts = {
        "pressure_temperature": {"title": gettext("Pressão e temperatura ao longo da linha"), "x": x, "series": [
            {"name": gettext("Pressão [bar(a)]"), "y": series(results, "P_Pa", 1e-5), "axis": "y"},
            {"name": gettext("Temperatura [K]"), "y": series(results, "T_K"), "axis": "y2"},
        ]},
        "flow_density_velocity": {"title": gettext("Densidade, vazão volumétrica e velocidade"), "x": x, "series": [
            {"name": gettext("Densidade [kg/m³]"), "y": series(results, "rho_kg_m3")},
            {"name": gettext("Vazão volumétrica [m³/h]"), "y": series(results, "Qv_m3_s", 3600)},
            {"name": gettext("Velocidade [m/s]"), "y": series(results, "v_m_s")},
        ]},
        "thermodynamic_properties": {"title": gettext("Propriedades termodinâmicas"), "x": x, "series": [
            {"name": "h [kJ/kg]", "y": series(results, "h_kJ_kg")},
            {"name": "u [kJ/kg]", "y": series(results, "u_kJ_kg")},
            {"name": "s [kJ/(kg·K)]", "y": series(results, "s_kJ_kgK")},
        ]},
        "flow_properties": {"title": gettext("Reynolds, fator Darcy e Mach"), "x": x, "series": [
            {"name": "Reynolds [-]", "y": series(results, "Re")},
            {"name": gettext("Fator Darcy [-]"), "y": series(results, "fD")},
            {"name": "Mach [-]", "y": series(results, "Mach")},
            {"name": gettext("Velocidade do som [m/s]"), "y": series(results, "c_m_s")},
        ]},
        "specific_heats": {"title": gettext("Cp, Cv e gamma"), "x": x, "series": [
            {"name": "Cp [kJ/(kg·K)]", "y": series(results, "Cp_kJ_kgK")},
            {"name": "Cv [kJ/(kg·K)]", "y": series(results, "Cv_kJ_kgK")},
            {"name": "gamma [-]", "y": series(results, "gamma")},
        ]},
    }
    if mollier_options.get("enabled", True):
        charts["mollier"] = build_mollier_payload(results, gas, fluid_name, mollier_options)
    return charts


def build_mollier_payload(results, gas, fluid_name, options):
    reference_state = (101325.0, 298.15)
    gas = dict(gas)
    gas["mollier_saturation_margin_K"] = options.get("phase_margin_K", 2.0)
    gas["Z_max_plot"] = options.get("Z_max_plot", gas.get("Z_max_plot", DEFAULT_Z_MAX_PLOT))
    first = results.iloc[0]
    last = results.iloc[-1]
    if options.get("manual"):
        P_min = options["P_min_bar"] * 1e5
        P_max = options["P_max_bar"] * 1e5
        T_min = options["T_min_C"] + 273.15
        T_max = options["T_max_C"] + 273.15
    else:
        P_min, P_max, T_min, T_max = automatic_mollier_window(first["P_Pa"], first["T_K"], last["P_Pa"], last["T_K"])
    if fluid_name in FLUIDS and not options.get("manual"):
        grid = load_or_create_mollier_cache(fluid_name, gas, reference_state)
        source = "cache"
    else:
        n_isobars = int(options.get("n_isobars", 8))
        n_points = int(options.get("n_points", 50))
        grid = compute_mollier_grid(
            gas, P_min, P_max, T_min, T_max, n_isobars, n_points, reference_state,
            pressures=np.geomspace(P_min, P_max, n_isobars), temperatures=np.linspace(T_min, T_max, n_points),
        )
        grid["isotherms"] = compute_mollier_isotherms(grid, int(options.get("n_isotherms", 6)))
        source = gettext("dinamico")
    path = overlay_pipeline_path_on_mollier(grid, results)
    factor = 1 / (gas["MM"] * 1000)
    isobars = [{"name": f"{item['P_Pa'] / 1e5:.4g} bar", "s": [finite_or_none(v * factor) for v in item["s_J_molK"]], "h": [finite_or_none(v * factor) for v in item["h_J_mol"]]} for item in grid.get("isobars", [])]
    isotherms = [{"name": f"{item['T_K'] - 273.15:.0f} C", "s": [finite_or_none(v * factor) for v in item["s_J_molK"]], "h": [finite_or_none(v * factor) for v in item["h_J_mol"]]} for item in grid.get("isotherms", [])]
    saturation_curve = compute_saturation_curve(gas, T_min, T_max, reference_state, P_min=P_min, P_max=P_max)
    saturation = None
    if saturation_curve:
        saturation = {"s": [finite_or_none(v * factor) for v in saturation_curve["s_J_molK"]], "h": [finite_or_none(v * factor) for v in saturation_curve["h_J_mol"]]}
    total = len(grid.get("pressures", [])) * len(grid.get("temperatures", []))
    omitted = int(sum(grid.get("discarded", {}).values()))
    return {
        "source": source,
        "fluid": fluid_name,
        "version": MOLLIER_MODEL_VERSION,
        "P_range_bar": [finite_or_none(P_min / 1e5), finite_or_none(P_max / 1e5)],
        "T_range_C": [finite_or_none(T_min - 273.15), finite_or_none(T_max - 273.15)],
        "total_points": total,
        "valid_points": max(total - omitted, 0),
        "omitted_points": omitted,
        "discarded": grid.get("discarded", {}),
        "isobars": isobars,
        "isotherms": isotherms,
        "saturation": saturation,
        "path": {"s": [finite_or_none(v * factor) for v in path["s_J_molK"]], "h": [finite_or_none(v * factor) for v in path["h_J_mol"]]},
    }


def build_diagnostics(results):
    superheat = results["superheat_deltaT_K"].dropna()
    return {
        "saturation_statuses": sorted(set(results["saturation_status"].dropna())),
        "min_superheat_K": finite_or_none(superheat.min()) if not superheat.empty else None,
        "max_betaS_rel_error": finite_or_none(results["betaS_rel_error"].max()),
        "rho_min": finite_or_none(results["rho_kg_m3"].min()),
        "rho_max": finite_or_none(results["rho_kg_m3"].max()),
        "Mach_max": finite_or_none(results["Mach"].max()),
        "Z_min": finite_or_none(results["Z"].min()),
        "Z_max": finite_or_none(results["Z"].max()),
    }
