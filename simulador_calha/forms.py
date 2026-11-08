import math

from django import forms
from django.utils.translation import gettext_lazy as _


DEFAULT_ENTRADAS = {
    "S_percent": 5,
    "rugosidade_mm": 0.15,
    "rugosidade_unidade": "mm",
    "Qreq_m3h": 200,
    "rhos": 4020,
    "rhol": 998,
    "mu_l_cP": 0.89,
    "phiw_percent": 50,
    "entrada_reologia": "constantes",
    "A_lab": 23500,
    "B_lab": 5.61,
    "B_linha_lab": 2.07,
    "tau0_direto": 0.2730317880556689,
    "tau0_unidade": "pa",
    "eta_direta": 3.2650927484704075,
    "eta_unidade": "cp",
    "d85_mm": 0.15,
    "dp_mm": 0.30,
    "geometria": "retangular",
    "b": 0.2,
    "b_unidade": "m",
    "hmax": 0.2,
    "hmax_unidade": "m",
    "m": 0,
    "D": 0.25,
    "D_unidade": "m",
}


class FlexibleFloatField(forms.FloatField):
    def to_python(self, value):
        if isinstance(value, str):
            value = value.strip().replace(",", ".")
        return super().to_python(value)


class SimulacaoCalhaForm(forms.Form):
    COMPRIMENTO_CHOICES = [("m", "m"), ("mm", "mm"), ("pol", "pol"), ("ft", _("ft"))]
    TAU0_CHOICES = [("pa", "Pa"), ("kpa", "kPa"), ("dyn_cm2", "dyn/cm²")]
    ETA_CHOICES = [("cp", "cP"), ("mpa_s", "mPa·s"), ("pa_s", "Pa·s")]

    geometria = forms.ChoiceField(
        label=_("Geometria da seção [-]"),
        choices=[
            ("retangular", _("Retangular")),
            ("trapezoidal", _("Trapezoidal")),
            ("triangular", _("Triangular")),
            ("tubo", _("Tubular parcialmente cheia")),
        ],
        initial=DEFAULT_ENTRADAS["geometria"],
        help_text=_("Selecione a geometria da descida despressurizada."),
    )
    S_percent = FlexibleFloatField(
        label=_("S - Inclinação [%]"), initial=DEFAULT_ENTRADAS["S_percent"], min_value=0.000001,
        help_text=_("Inclinação longitudinal. Exemplo: 5 representa uma descida de 5%."),
    )
    rugosidade_mm = FlexibleFloatField(
        label=_("ε - Rugosidade absoluta"), initial=DEFAULT_ENTRADAS["rugosidade_mm"], min_value=0.000001,
        help_text=_("Informe a rugosidade absoluta na unidade selecionada ao lado."),
    )
    rugosidade_unidade = forms.ChoiceField(label=_("Unidade de ε"), choices=COMPRIMENTO_CHOICES, initial="mm")
    Qreq_m3h = FlexibleFloatField(
        label=_("Q - Vazão requerida [m³/h]"), initial=DEFAULT_ENTRADAS["Qreq_m3h"], min_value=0.000001,
        help_text=_("Vazão que a seção deve transportar."),
    )
    rhos = FlexibleFloatField(
        label=_("ρₛ - Densidade dos sólidos [kg/m³]"), initial=DEFAULT_ENTRADAS["rhos"], min_value=0.000001,
        help_text=_("Densidade real das partículas sólidas."),
    )
    rhol = FlexibleFloatField(
        label=_("ρₗ - Densidade do líquido [kg/m³]"), initial=DEFAULT_ENTRADAS["rhol"], min_value=0.000001,
        help_text=_("Densidade do líquido carreador."),
    )
    mu_l_cP = FlexibleFloatField(
        label=_("μₗ - Viscosidade do líquido [cP]"), initial=DEFAULT_ENTRADAS["mu_l_cP"], min_value=0.000001,
        help_text=_("Viscosidade dinâmica do líquido carreador."),
    )
    phiw_percent = FlexibleFloatField(
        label=_("φw - Concentração mássica [%]"), initial=DEFAULT_ENTRADAS["phiw_percent"],
        min_value=0.000001, max_value=99.999999,
        help_text=_("Concentração mássica de sólidos. Exemplo: 50 representa 50%."),
    )
    entrada_reologia = forms.ChoiceField(
        label=_("Tipo de entrada reológica [-]"),
        choices=[("constantes", _("Constantes laboratoriais A, B e B'")), ("direta", _("Parâmetros reológicos diretos"))],
        initial="constantes",
        help_text=_("Escolha como os parâmetros reológicos serão informados."),
    )
    A_lab = FlexibleFloatField(
        label=_("A - Constante para τ₀ [dyn/cm²]"), initial=DEFAULT_ENTRADAS["A_lab"], min_value=0, required=False,
        help_text=_("Constante A da correlação τ₀ = A · φV."),
    )
    B_lab = FlexibleFloatField(
        label=_("B - Expoente para τ₀ [-]"), initial=DEFAULT_ENTRADAS["B_lab"], required=False,
        help_text=_("Expoente B da correlação τ₀ = A · φV."),
    )
    B_linha_lab = FlexibleFloatField(
        label=_("B' - Parâmetro para η [-]"), initial=DEFAULT_ENTRADAS["B_linha_lab"], required=False,
        help_text=_("Parâmetro B' da correlação do coeficiente de rigidez."),
    )
    tau0_direto = FlexibleFloatField(
        label=_("τ₀ - Tensão de escoamento direta"), initial=DEFAULT_ENTRADAS["tau0_direto"],
        min_value=0, required=False, help_text=_("Valor direto da tensão de escoamento na condição informada."),
    )
    tau0_unidade = forms.ChoiceField(label=_("Unidade de τ₀"), choices=TAU0_CHOICES, initial="pa", required=False)
    eta_direta = FlexibleFloatField(
        label=_("η - Coeficiente de rigidez direto"), initial=DEFAULT_ENTRADAS["eta_direta"],
        min_value=0.000001, required=False,
        help_text=_("Valor de η de referência. O motor mantém o ajuste pela viscosidade do líquido carreador."),
    )
    eta_unidade = forms.ChoiceField(label=_("Unidade de η"), choices=ETA_CHOICES, initial="cp", required=False)
    d85_mm = FlexibleFloatField(
        label=_("d85 - Percentil passante [mm]"), initial=DEFAULT_ENTRADAS["d85_mm"], min_value=0.000001,
        help_text=_("Diâmetro correspondente ao percentil passante d85."),
    )
    dp_mm = FlexibleFloatField(
        label=_("dp - Maior partícula [mm]"), initial=DEFAULT_ENTRADAS["dp_mm"], min_value=0.000001,
        help_text=_("Maior diâmetro de partícula considerado."),
    )
    b = FlexibleFloatField(
        label=_("b - Base inferior"), initial=DEFAULT_ENTRADAS["b"], min_value=0, help_text=_("Largura da base inferior."),
    )
    b_unidade = forms.ChoiceField(label=_("Unidade de b"), choices=COMPRIMENTO_CHOICES, initial="m")
    hmax = FlexibleFloatField(
        label=_("hmax - Altura disponível"), initial=DEFAULT_ENTRADAS["hmax"], min_value=0.000001,
        help_text=_("Altura máxima disponível da seção."),
    )
    hmax_unidade = forms.ChoiceField(label=_("Unidade de hmax"), choices=COMPRIMENTO_CHOICES, initial="m")
    m = FlexibleFloatField(
        label=_("m - Talude lateral [-]"), initial=DEFAULT_ENTRADAS["m"], min_value=0,
        help_text=_("Relação horizontal/vertical do talude."),
    )
    D = FlexibleFloatField(
        label=_("D - Diâmetro interno"), initial=DEFAULT_ENTRADAS["D"], min_value=0.000001,
        help_text=_("Diâmetro interno da seção tubular."),
    )
    D_unidade = forms.ChoiceField(label=_("Unidade de D"), choices=COMPRIMENTO_CHOICES, initial="m")

    @staticmethod
    def _comprimento_para_m(valor, unidade):
        fatores = {"m": 1, "mm": 0.001, "pol": 0.0254, "ft": 0.3048}
        if unidade not in fatores:
            raise forms.ValidationError(_("Unidade de comprimento inválida."))
        return valor * fatores[unidade]

    @staticmethod
    def _tau0_para_dyn_cm2(valor, unidade):
        fatores = {"pa": 10, "kpa": 10000, "dyn_cm2": 1}
        if unidade not in fatores:
            raise forms.ValidationError(_("Unidade de tensão de escoamento inválida."))
        return valor * fatores[unidade]

    @staticmethod
    def _eta_para_cp(valor, unidade):
        fatores = {"cp": 1, "mpa_s": 1, "pa_s": 1000}
        if unidade not in fatores:
            raise forms.ValidationError(_("Unidade do coeficiente de rigidez inválida."))
        return valor * fatores[unidade]

    @staticmethod
    def _phiv_vr(cleaned):
        phiw = cleaned["phiw_percent"] / 100
        rhos, rhol = cleaned["rhos"], cleaned["rhol"]
        phiv = (phiw * rhol) / (phiw * rhol + (1 - phiw) * rhos)
        return phiv, phiv / (1 - phiv)

    def clean(self):
        cleaned = super().clean()
        rhos, rhol = cleaned.get("rhos"), cleaned.get("rhol")
        if rhos is not None and rhol is not None and rhos <= rhol:
            self.add_error("rhos", _("A densidade dos sólidos deve ser maior que a densidade do líquido."))

        geometria, b, m = cleaned.get("geometria"), cleaned.get("b"), cleaned.get("m")
        if geometria == "trapezoidal":
            if b is not None and b <= 0: self.add_error("b", _("Para seção trapezoidal, b deve ser maior que zero."))
            if m is not None and m <= 0: self.add_error("m", _("Para seção trapezoidal, m deve ser maior que zero."))
        elif geometria == "retangular":
            if b is not None and b <= 0: self.add_error("b", _("Para seção retangular, b deve ser maior que zero."))
        elif geometria == "triangular":
            if m is not None and m <= 0: self.add_error("m", _("Para seção triangular, m deve ser maior que zero."))

        if cleaned.get("entrada_reologia") == "constantes":
            for nome in ("A_lab", "B_lab", "B_linha_lab"):
                if cleaned.get(nome) is None: self.add_error(nome, _("Informe este parâmetro."))
        elif cleaned.get("entrada_reologia") == "direta":
            if cleaned.get("tau0_direto") is None or cleaned.get("tau0_direto", 0) <= 0:
                self.add_error("tau0_direto", _("Informe τ₀ maior que zero para o modelo atual."))
            if cleaned.get("eta_direta") is None or cleaned.get("eta_direta", 0) <= 0:
                self.add_error("eta_direta", _("Informe η maior que zero."))
        return cleaned

    def dados_motor(self):
        d = self.cleaned_data
        tipo = d["geometria"]
        b_m = self._comprimento_para_m(d["b"], d["b_unidade"])
        hmax_m = self._comprimento_para_m(d["hmax"], d["hmax_unidade"])
        D_m = self._comprimento_para_m(d["D"], d["D_unidade"])
        rug_m = self._comprimento_para_m(d["rugosidade_mm"], d["rugosidade_unidade"])
        if tipo == "retangular": m, b_m = 0, b_m
        elif tipo == "triangular": m, b_m = d["m"], 0
        else: m = d["m"]

        A, B, B_linha = d.get("A_lab"), d.get("B_lab"), d.get("B_linha_lab")
        if d["entrada_reologia"] == "direta":
            phiv, Vr = self._phiv_vr(d)
            tau_dyn = self._tau0_para_dyn_cm2(d["tau0_direto"], d["tau0_unidade"])
            eta_cp = self._eta_para_cp(d["eta_direta"], d["eta_unidade"])
            A, B = tau_dyn / phiv, 1
            B_linha = math.log10(eta_cp) / Vr

        return {
            **d,
            "geometria_tipo": tipo,
            "geometria": "tubo" if tipo == "tubo" else "trapezoidal",
            "b": b_m, "hmax": hmax_m, "D": D_m, "m": m,
            "rugosidade": rug_m, "rugosidade_mm": rug_m * 1000,
            "A_lab": A, "B_lab": B, "B_linha_lab": B_linha,
            "S": d["S_percent"] / 100,
            "mu_l_Pa_s": d["mu_l_cP"] * 0.001,
            "phiw": d["phiw_percent"] / 100,
            "d85": d["d85_mm"] / 1000,
            "dp": d["dp_mm"] / 1000,
        }
