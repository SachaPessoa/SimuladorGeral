from django import forms
from django.utils.translation import gettext_lazy as _

from .engine.fluids import CUSTOM_FLUID, DEFAULT_VISCOSITY_CP, FLUIDS
from .engine.gas_engine import DEFAULT_Z_MAX_PLOT


class FlexibleFloatField(forms.FloatField):
    def to_python(self, value):
        if isinstance(value, str):
            value = value.strip().replace(",", ".")
        return super().to_python(value)


class GasSimulationForm(forms.Form):
    FLUID_CHOICES = [(name, name) for name in FLUIDS] + [(CUSTOM_FLUID, CUSTOM_FLUID)]
    THERMAL_CHOICES = [("isothermal", _("Isotérmico")), ("combined", _("Adiabático"))]
    RANGE_CHOICES = [("auto", _("Automática")), ("manual", _("Manual"))]

    fluid_type = forms.ChoiceField(label=_("Fluido"), choices=FLUID_CHOICES, initial="Water")
    mu_constant_Pa_s = FlexibleFloatField(label=_("Viscosidade dinâmica [Pa·s]"), initial=1.4e-5, min_value=0)

    P0_bar_a = FlexibleFloatField(label=_("Pressão inicial [bar(a)]"), initial=4.2, min_value=0)
    T0_C = FlexibleFloatField(label=_("Temperatura inicial [°C]"), initial=149.85)
    mdot_kg_h = FlexibleFloatField(label=_("Vazão mássica [kg/h]"), initial=1675.8, min_value=0)
    thermal_model = forms.ChoiceField(label=_("Modelo térmico"), choices=THERMAL_CHOICES, initial="combined")

    L_m = FlexibleFloatField(label=_("Comprimento [m]"), initial=600.0, min_value=0)
    D_m = FlexibleFloatField(label=_("Diâmetro interno [m]"), initial=0.089, min_value=0)
    rough_m = FlexibleFloatField(label=_("Rugosidade [m]"), initial=0.000149, min_value=0)
    dx_m = FlexibleFloatField(label=_("Passo de cálculo [m]"), initial=5.0, min_value=0)

    mollier_enabled = forms.BooleanField(label=_("Mostrar Mollier"), required=False, initial=True)
    mollier_range = forms.ChoiceField(label=_("Faixa Mollier"), choices=RANGE_CHOICES, initial="auto")
    mollier_clip_outliers = forms.BooleanField(label=_("Recortar outliers"), required=False, initial=True)
    mollier_P_min_bar = FlexibleFloatField(label=_("Pmin [bar(a)]"), initial=1.01325, min_value=0, required=False)
    mollier_P_max_bar = FlexibleFloatField(label=_("Pmax [bar(a)]"), initial=8.0, min_value=0, required=False)
    mollier_T_min_C = FlexibleFloatField(label=_("Tmin [°C]"), initial=50.0, required=False)
    mollier_T_max_C = FlexibleFloatField(label=_("Tmax [°C]"), initial=250.0, required=False)

    MM_kg_kmol = FlexibleFloatField(label=_("MM [kg/kmol]"), initial=16.04, min_value=0, required=False)
    Tc_C = FlexibleFloatField(label=_("Tc [°C]"), initial=-82.55, required=False)
    Pc_bar_a = FlexibleFloatField(label=_("Pc [bar(a)]"), initial=46.0, min_value=0, required=False)
    omega = FlexibleFloatField(label=_("Fator acêntrico [-]"), initial=0.012, required=False)
    C1 = FlexibleFloatField(label=_("Perry C1"), initial=33300.0, required=False)
    C2 = FlexibleFloatField(label=_("Perry C2"), initial=79930.0, required=False)
    C3 = FlexibleFloatField(label=_("Perry C3"), initial=2086.0, required=False)
    C4 = FlexibleFloatField(label=_("Perry C4"), initial=41600.0, required=False)
    C5 = FlexibleFloatField(label=_("Perry C5"), initial=991.96, required=False)
    Z_max_plot = FlexibleFloatField(label=_("Z max Mollier [-]"), initial=DEFAULT_Z_MAX_PLOT, min_value=0, required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        fluid = self.initial.get("fluid_type") or self.data.get("fluid_type") or "Water"
        if fluid in FLUIDS:
            fluid_data = FLUIDS[fluid]
            viscosity_cp = DEFAULT_VISCOSITY_CP.get(fluid, 0.011)
            self.fields["mu_constant_Pa_s"].initial = viscosity_cp * 1e-3
            self.fields["MM_kg_kmol"].initial = fluid_data["MM"]
            self.fields["Tc_C"].initial = fluid_data["Tc"] - 273.15
            self.fields["Pc_bar_a"].initial = fluid_data["Pc_kgf_cm2"] * 0.980665
            self.fields["omega"].initial = fluid_data["omega"]
            for index in range(1, 6):
                self.fields[f"C{index}"].initial = fluid_data[f"C{index}"]

    def clean(self):
        cleaned = super().clean()
        for key in ("P0_bar_a", "mdot_kg_h", "L_m", "D_m", "dx_m", "mu_constant_Pa_s"):
            value = cleaned.get(key)
            if value is not None and value <= 0:
                self.add_error(key, _("O valor deve ser maior que zero."))
        if cleaned.get("rough_m") is not None and cleaned["rough_m"] < 0:
            self.add_error("rough_m", _("A rugosidade não pode ser negativa."))
        if cleaned.get("T0_C") is not None and cleaned["T0_C"] <= -273.15:
            self.add_error("T0_C", _("A temperatura deve ser maior que o zero absoluto."))
        if cleaned.get("mollier_range") == "manual":
            pmin, pmax = cleaned.get("mollier_P_min_bar"), cleaned.get("mollier_P_max_bar")
            tmin, tmax = cleaned.get("mollier_T_min_C"), cleaned.get("mollier_T_max_C")
            if None in (pmin, pmax, tmin, tmax):
                raise forms.ValidationError(_("Informe a faixa manual completa do Mollier."))
            if pmax <= pmin:
                self.add_error("mollier_P_max_bar", _("Pmax deve ser maior que Pmin."))
            if tmax <= tmin:
                self.add_error("mollier_T_max_C", _("Tmax deve ser maior que Tmin."))
        if cleaned.get("fluid_type") == CUSTOM_FLUID:
            for key in ("MM_kg_kmol", "Tc_C", "Pc_bar_a", "omega", "C1", "C2", "C3", "C4", "C5"):
                if cleaned.get(key) is None:
                    self.add_error(key, _("Obrigatório para fluido genérico."))
            if cleaned.get("Tc_C") is not None and cleaned["Tc_C"] <= -273.15:
                self.add_error("Tc_C", _("Tc deve ser maior que o zero absoluto."))
        return cleaned

    def as_engine_inputs(self):
        values = self.cleaned_data
        args = {
            "P0": values["P0_bar_a"] * 1e5,
            "T0": values["T0_C"] + 273.15,
            "mdot": values["mdot_kg_h"] / 3600,
            "D": values["D_m"],
            "roughness": values["rough_m"],
            "L": values["L_m"],
            "dx": values["dx_m"],
            "thermal_model": values["thermal_model"],
            "z0": 0.0,
            "dz_total": 0.0,
        }
        mollier = {
            "enabled": values.get("mollier_enabled", False),
            "manual": values.get("mollier_range") == "manual",
            "clip_outliers": values.get("mollier_clip_outliers", True),
            "P_min_bar": values.get("mollier_P_min_bar"),
            "P_max_bar": values.get("mollier_P_max_bar"),
            "T_min_C": values.get("mollier_T_min_C"),
            "T_max_C": values.get("mollier_T_max_C"),
            "Z_max_plot": values.get("Z_max_plot") or DEFAULT_Z_MAX_PLOT,
            "saturation_margin_K": 5.0,
            "phase_margin_K": 2.0,
            "n_isobars": 8,
            "n_points": 50,
            "n_isotherms": 6,
        }
        return args, mollier
