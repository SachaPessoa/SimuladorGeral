from django.contrib import messages
import copy
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.utils.translation import gettext as _

from .engine.fluids import CUSTOM_FLUID, build_custom_gas, build_known_gas
from .engine.gas_engine import run_gas_pipeline
from .forms import GasSimulationForm


SATURATION_STATUS_LABELS = {
    "superheated_vapor": "vapor superaquecido",
    "near_saturation": "próximo da saturação",
    "probable_phase_change": "possível mudança de fase",
    "supercritical_temperature": "temperatura supercrítica",
    "unavailable": "indisponível",
    "unknown": "desconhecido",
}


def translate_chart_texts(value):
    if isinstance(value, dict):
        for key, item in value.items():
            if key in {"title", "name", "source"} and isinstance(item, str):
                value[key] = _(item)
            else:
                translate_chart_texts(item)
    elif isinstance(value, list):
        for item in value:
            translate_chart_texts(item)


def format_value(value):
    if value is None:
        return "-"
    try:
        number = float(value)
    except (TypeError, ValueError):
        return value
    absolute = abs(number)
    if absolute == 0:
        return "0"
    if absolute >= 1e6 or absolute < 1e-4:
        return f"{number:.3e}"
    if absolute >= 1000:
        return f"{number:.0f}"
    if absolute >= 100:
        return f"{number:.1f}"
    if absolute >= 10:
        return f"{number:.2f}"
    if absolute >= 1:
        return f"{number:.3f}".rstrip("0").rstrip(".")
    return f"{number:.4g}"


def add_display_values(result):
    summary = result.get("summary", {})
    if isinstance(summary.get("thermal_model"), str):
        thermal_model = summary["thermal_model"]
        summary["thermal_model"] = _("Adiabático") if thermal_model in {"Compressivel", "Compressível"} else _(thermal_model)
    result["summary_display"] = {key: format_value(value) for key, value in summary.items()}
    for row in result.get("rows", []):
        row["P_bar"] = row.get("P_Pa") / 1e5 if row.get("P_Pa") is not None else None
        row["T_C"] = row.get("T_K") - 273.15 if row.get("T_K") is not None else None
        row["Qv_m3_h"] = row.get("Qv_m3_s") * 3600 if row.get("Qv_m3_s") is not None else None
        row["display"] = {key: format_value(value) for key, value in row.items() if key != "display"}
    diagnostics = result.get("diagnostics", {})
    diagnostics["saturation_statuses"] = [
        _(SATURATION_STATUS_LABELS.get(status, status))
        for status in diagnostics.get("saturation_statuses", [])
    ]
    translate_chart_texts(result.get("charts", {}))
    return result


@login_required
def gas_home(request):
    if request.method == "GET" and request.GET.get("reset") == "padrao":
        request.session.pop("simulador_gas_form", None)
        request.session.pop("simulador_gas_result", None)
        messages.info(request, _("Entradas do simulador de gases restauradas para o padrão."))
        return redirect("simulador_gas:home")

    if request.method == "POST":
        form = GasSimulationForm(request.POST)
        if form.is_valid():
            request.session["simulador_gas_form"] = {name: form.cleaned_data.get(name) for name in form.fields}
            try:
                args, mollier_options = form.as_engine_inputs()
                fluid_name = form.cleaned_data["fluid_type"]
                if fluid_name == CUSTOM_FLUID:
                    gas = build_custom_gas(form.cleaned_data)
                else:
                    gas = build_known_gas(fluid_name, form.cleaned_data["mu_constant_Pa_s"], mollier_options["Z_max_plot"])
                result = run_gas_pipeline(gas, args, fluid_name, mollier_options)
            except Exception as exc:
                messages.error(request, _(str(exc)))
            else:
                request.session["simulador_gas_result"] = result
                return redirect("simulador_gas:results")
    else:
        form = GasSimulationForm(initial=request.session.get("simulador_gas_form") or None)
    return render(request, "simulador_gas/gas_home.html", {"form": form})


@login_required
def gas_calcular(request):
    if request.method != "POST":
        return redirect("simulador_gas:home")
    return gas_home(request)


@login_required
def gas_results(request):
    result = request.session.get("simulador_gas_result")
    if not result:
        messages.info(request, _("Execute uma simulação de gases primeiro."))
        return redirect("simulador_gas:home")
    result = add_display_values(copy.deepcopy(result))
    return render(request, "simulador_gas/gas_results.html", {"resultado": result, "graficos": result["charts"]})


@login_required
def gas_calculation_memory(request):
    return render(request, "simulador_gas/gas_calculation_memory.html")


@login_required
def mollier_cache(request):
    result = request.session.get("simulador_gas_result") or {}
    mollier = (result.get("charts") or {}).get("mollier") or {}
    return render(request, "simulador_gas/gas_mollier_cache.html", {"mollier": mollier})
