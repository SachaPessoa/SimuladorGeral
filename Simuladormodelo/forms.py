from django import forms

import math

from django.utils.translation import gettext_lazy as _

from .codigo.modelo import DEFAULT_ENTRADAS


def converter_concentracao_para_cv(valor, tipo, rho_s, rho_l):
    """Converte a concentração informada como fração decimal para Cv."""
    if valor is None or not 0 < valor < 1:
        raise forms.ValidationError(_("A concentração informada deve estar entre 0 e 1."))
    if rho_s is None or rho_s <= 0 or rho_l is None or rho_l <= 0:
        raise forms.ValidationError(_("As densidades dos sólidos e do fluido devem ser maiores que zero."))
    if tipo == "cv":
        return valor
    if tipo == "cw":
        return (valor * rho_l) / (rho_s * (1 - valor) + valor * rho_l)
    raise forms.ValidationError(_("Tipo de concentração inválido."))


class FlexibleFloatField(forms.FloatField):
    def to_python(self, value):
        if isinstance(value, str):
            value = value.strip().replace(",", ".")
        return super().to_python(value)


class FlexibleIntegerField(forms.IntegerField):
    def to_python(self, value):
        if isinstance(value, str):
            value = value.strip().replace(",", ".")
        return super().to_python(value)


class SimulacaoForm(forms.Form):
    CALCULO_TIPO_CHOICES = [
        ("perda_carga", _("Perda de carga - WASP Modificado")),
        ("vscalc", _("Simulador de Deposição")),
    ]
    FOURCM_SCALE_CHOICES = [
        ("log", _("Log-log")),
        ("semilog", _("Semi-log")),
        ("linear", _("Linear")),
    ]
    TIPO_CONCENTRACAO_CHOICES = [
        ("cv", _("Fração volumétrica total")),
        ("cw", _("Fração mássica")),
    ]
    ENTRADA_REOLOGIA_CHOICES = [
        ("laboratorio", _("Parâmetros laboratoriais (A, B e B')")),
        ("direta", _("Parâmetros reológicos diretos")),
    ]
    TAU0_UNIDADE_CHOICES = [
        ("pa", _("Pa")),
        ("kpa", _("kPa")),
        ("dyn_cm2", _("dyn/cm²")),
    ]
    COEFICIENTE_UNIDADE_CHOICES = [
        ("cp", _("cP / cP·sⁿ")),
        ("mpa_s", _("mPa·s / mPa·sⁿ")),
        ("pa_s", _("Pa·s / Pa·sⁿ")),
    ]
    MODELO_CHOICES = [
        ("auto", _("Automático: perguntar se C/Ca total > 80%")),
        ("heterogeneo", _("Forçar modelo heterogêneo")),
        ("homogeneo", _("Forçar modelo homogêneo")),
    ]
    TIPO_FLUIDO_CHOICES = [
        ("bingham", _("Plástico de Bingham")),
        ("powerlaw", _("Power Law")),
        ("hb", _("Herschel-Bulkley")),
    ]
    DIAMETRO_UNIDADE_CHOICES = [
        ("pol", _("pol")),
        ("mm", _("mm")),
        ("m", _("m")),
    ]
    RUGOSIDADE_UNIDADE_CHOICES = [
        ("mm", _("mm")),
        ("um", _("µm")),
        ("m", _("m")),
    ]
    GILLIES_CMAX_CHOICES = [
        (0.75, _("0,75 — distribuição granulométrica ampla")),
        (0.60, _("0,60 — distribuição granulométrica estreita")),
    ]
    GILLIES_D12_CHOICES = [
        ("auto", _("Automático pela granulometria")),
        ("manual", _("Manual/debug")),
    ]

    _diametro_padrao_m = DEFAULT_ENTRADAS["diametro_pol"] * 0.0254
    _rugosidade_padrao_mm = DEFAULT_ENTRADAS["rugosidade_relativa"] * _diametro_padrao_m * 1000
    _tau0_padrao_pa = DEFAULT_ENTRADAS["A"] * (DEFAULT_ENTRADAS["phi_total"] ** DEFAULT_ENTRADAS["B"]) * 0.1
    _coeficiente_padrao_cp = 10 ** (
        (DEFAULT_ENTRADAS["phi_total"] / (1 - DEFAULT_ENTRADAS["phi_total"])) * DEFAULT_ENTRADAS["B_linha"]
    )

    calculo_tipo = forms.ChoiceField(
        label=_("Cálculo"),
        choices=CALCULO_TIPO_CHOICES,
        initial="perda_carga",
        required=False,
        help_text=_("Selecione o engine Python utilizado nesta execução."),
    )
    comparar_4cm = forms.BooleanField(
        label=_("Comparar com 4CM"),
        initial=True,
        required=False,
        help_text=_("Inclui o Four Component Model como cálculo comparativo do WASP Modificado."),
    )
    fourcm_vmin = FlexibleFloatField(label=_("Velocidade mínima do gráfico"), initial=0.5, min_value=0, required=False)
    fourcm_vmax = FlexibleFloatField(label=_("Velocidade máxima do gráfico"), initial=8.0, min_value=0, required=False)
    fourcm_scale = forms.ChoiceField(label=_("Escala do gráfico de perda de carga"), choices=FOURCM_SCALE_CHOICES, initial="log", required=False)
    fourcm_mus = FlexibleFloatField(label=_("4CM - µs atrito sólido/parede"), initial=0.48, min_value=0, required=False)
    fourcm_af = FlexibleFloatField(label=_("4CM - Af"), initial=1.0, required=False)
    fourcm_ap = FlexibleFloatField(label=_("4CM - Ap"), initial=0.5, required=False)
    fourcm_cf = FlexibleFloatField(label=_("4CM - Cf"), initial=1.0, required=False)
    fourcm_cp = FlexibleFloatField(label=_("4CM - Cp"), initial=0.5, required=False)
    fourcm_nc = FlexibleFloatField(label=_("4CM - nC"), initial=0.5, required=False)
    fourcm_bf = FlexibleFloatField(label=_("4CM - Bf"), initial=1.0, required=False)
    fourcm_bp = FlexibleFloatField(label=_("4CM - Bp"), initial=1.0, required=False)
    fourcm_bh = FlexibleFloatField(label=_("4CM - Bh"), initial=0.5, required=False)
    fourcm_nb = FlexibleFloatField(label=_("4CM - nB"), initial=0.5, required=False)
    vscalc_d_mm = FlexibleFloatField(
        label=_("Deposição - diâmetro equivalente (µm)"),
        initial=None,
        min_value=0,
        required=False,
        help_text=_(
            "Opcional. Informe o diâmetro equivalente em µm. Para distribuições estreitas (Short PSD), use D50. "
            "Para distribuições largas (Broad PSD), use preferencialmente D80, D85 ou Top Size. "
            "Critério de indicação: D80/D20 < 2,0 sugere Short PSD; D80/D20 > 2,5 sugere Broad PSD; "
            "valores intermediários ficam em zona de transição e devem ser definidos pelo usuário."
        ),
    )
    vscalc_dmin_um = FlexibleFloatField(
        label=_("Deposição - diâmetro inicial do gráfico (µm)"),
        initial=None,
        min_value=0,
        required=False,
        help_text=_("Opcional. Se vazio, o gráfico usa 50% do diâmetro operacional."),
    )
    vscalc_dmax_um = FlexibleFloatField(
        label=_("Deposição - diâmetro final do gráfico (µm)"),
        initial=None,
        min_value=0,
        required=False,
        help_text=_("Opcional. Se vazio, o gráfico usa 200% do diâmetro operacional."),
    )
    vscalc_vmin = FlexibleFloatField(
        label=_("Deposição - velocidade mínima do gráfico (m/s)"),
        initial=None,
        min_value=0,
        required=False,
        help_text=_("Opcional. Se vazio, o gráfico usa 50% da velocidade operacional."),
    )
    vscalc_vmax = FlexibleFloatField(
        label=_("Deposição - velocidade máxima do gráfico (m/s)"),
        initial=None,
        min_value=0,
        required=False,
        help_text=_("Opcional. Se vazio, o gráfico usa 200% da velocidade operacional."),
    )
    vscalc_theta_deg = FlexibleFloatField(label=_("Deposição - inclinação da tubulação"), initial=0.0, required=False)
    vscalc_cvb = FlexibleFloatField(label=_("Deposição - Cvb concentração do leito"), initial=0.60, min_value=0, required=False)
    vscalc_mus = FlexibleFloatField(label=_("Deposição - µs atrito do leito"), initial=0.45, min_value=0, required=False)
    vscalc_yplus = FlexibleFloatField(label=_("Deposição - y+ da subcamada"), initial=5.0, min_value=0, required=False)
    vscalc_drag = forms.ChoiceField(label=_("Deposição - velocidade terminal"), choices=[("tl", "Turton-Levenspiel"), ("stokes", "Stokes")], initial="tl", required=False)
    vscalc_fine = forms.ChoiceField(label=_("Deposição - critério Thomas"), choices=[("original70", "Thomas se d <= 70 µm"), ("sublayer", "Thomas se d <= subcamada viscosa")], initial="original70", required=False)

    diametro_entrada = FlexibleFloatField(
        label=_("DI - Diâmetro interno do tubo"),
        initial=DEFAULT_ENTRADAS["diametro_pol"],
        min_value=0,
        help_text=_("Informe o diâmetro interno na unidade selecionada ao lado. O cálculo converte internamente para polegadas."),
    )
    diametro_unidade = forms.ChoiceField(
        label=_("Unidade do DI"),
        choices=DIAMETRO_UNIDADE_CHOICES,
        initial="pol",
        help_text=_("Escolha a unidade usada no campo DI: polegada, milímetro ou metro."),
    )
    rugosidade_absoluta = FlexibleFloatField(
        label=_("ε - Rugosidade absoluta"),
        initial=_rugosidade_padrao_mm,
        min_value=0,
        error_messages={"min_value": _("A rugosidade deve ser maior que zero.")},
        help_text=_("Informe a rugosidade absoluta da tubulação. O sistema calcula e/D = ε / DI usando unidades consistentes."),
    )
    rugosidade_unidade = forms.ChoiceField(
        label=_("Unidade de ε"),
        choices=RUGOSIDADE_UNIDADE_CHOICES,
        initial="mm",
        help_text=_("Escolha a unidade da rugosidade absoluta: mm, µm ou m."),
    )
    velocidade = FlexibleFloatField(
        label=_("U - Velocidade média (m/s)"),
        initial=DEFAULT_ENTRADAS["velocidade"],
        min_value=0,
        error_messages={"min_value": _("A velocidade operacional deve ser maior que zero.")},
        help_text=_("Velocidade operacional média da polpa na tubulação, em m/s."),
    )
    tipo_concentracao = forms.ChoiceField(
        label=_("Tipo de concentração"),
        choices=TIPO_CONCENTRACAO_CHOICES,
        initial="cv",
        help_text=_("Escolha se a concentração informada representa fração volumétrica ou fração mássica."),
    )
    phi_total = FlexibleFloatField(
        label=_("φV - Concentração volumétrica"),
        initial=DEFAULT_ENTRADAS["phi_total"],
        min_value=0,
        max_value=1,
        help_text=_("Informe como fração decimal, não em %. Exemplo: 0,30 para 30%."),
    )
    proporcoes_percent = forms.CharField(
        label=_("φᵢ - Proporções relativas das partículas (%)"),
        initial=", ".join(map(str, DEFAULT_ENTRADAS["proporcoes_percent"])),
        help_text=_("Lista em %, separada por vírgula. A soma deve ser 100. Use ponto decimal dentro dos valores se precisar: 10.5, 20, 69.5."),
    )
    diametros_um = forms.CharField(
        label=_("dᵢ - Diâmetros das partículas (µm)"),
        initial=", ".join(map(str, DEFAULT_ENTRADAS["diametros_um"])),
        help_text=_("Lista de diâmetros em micra, na mesma ordem das proporções. Separe por vírgula: 250, 180, 125."),
    )
    rho_s = FlexibleFloatField(
        label=_("ρₛ - Densidade das partículas (kg/m³)"),
        initial=DEFAULT_ENTRADAS["rho_s"],
        min_value=0,
        error_messages={
            "min_value": _("Para o modelo atual, a densidade dos sólidos deve ser maior que a densidade do líquido.")
        },
        help_text=_("Densidade real dos sólidos em kg/m³."),
    )
    rho_l = FlexibleFloatField(
        label=_("ρₗ - Densidade do fluido (kg/m³)"),
        initial=DEFAULT_ENTRADAS["rho_l"],
        min_value=0,
        help_text=_("Densidade do líquido transportador em kg/m³."),
    )
    mu_l_cp = FlexibleFloatField(
        label=_("µₗ - Viscosidade do fluido (cP)"),
        initial=DEFAULT_ENTRADAS["mu_l_cp"],
        min_value=0,
        help_text=_("Viscosidade dinâmica do fluido em cP. Exemplo: água a 20 °C ≈ 1,002 cP."),
    )
    A = FlexibleFloatField(
        label=_("A - Parâmetro para τ0"),
        initial=DEFAULT_ENTRADAS["A"],
        required=False,
        help_text=_("Usado em τ0 = A·φ^B, com τ0 em dyn/cm² antes da conversão para Pa."),
    )
    B = FlexibleFloatField(
        label=_("B - Parâmetro para τ0"),
        initial=DEFAULT_ENTRADAS["B"],
        required=False,
        help_text=_("Expoente da equação τ0 = A·φ^B. φ é a fração volumétrica total."),
    )
    B_linha = FlexibleFloatField(
        label=_("B' - Parâmetro para η ou K"),
        initial=DEFAULT_ENTRADAS["B_linha"],
        required=False,
        help_text=_("Usado em η ou K = 10^((φ/(1-φ))·B'), com η/K em cP antes do ajuste pela viscosidade do fluido."),
    )
    entrada_reologia = forms.ChoiceField(
        label=_("Tipo de entrada reológica"),
        choices=ENTRADA_REOLOGIA_CHOICES,
        initial="laboratorio",
        required=False,
        help_text=_("Escolha entre os parâmetros laboratoriais atuais ou valores reológicos informados diretamente."),
    )
    tau0_direto = FlexibleFloatField(
        label=_("τ₀ - Tensão de escoamento direta"),
        initial=_tau0_padrao_pa,
        min_value=0,
        required=False,
        help_text=_("Usada em Bingham e Herschel-Bulkley. Para Power Law, a tensão de escoamento interna será zero."),
    )
    tau0_unidade = forms.ChoiceField(
        label=_("Unidade de τ₀"),
        choices=TAU0_UNIDADE_CHOICES,
        initial="pa",
        required=False,
    )
    eta_direta = FlexibleFloatField(
        label=_("η ou K - Coeficiente reológico direto"),
        initial=_coeficiente_padrao_cp,
        min_value=0,
        required=False,
        help_text=_("Informe η para Bingham ou K para Power Law/Herschel-Bulkley, na referência de 20 °C. O sistema ajustará pela viscosidade do fluido carreador."),
    )
    eta_unidade = forms.ChoiceField(
        label=_("Unidade de η ou K"),
        choices=COEFICIENTE_UNIDADE_CHOICES,
        initial="cp",
        required=False,
    )
    k_direto = FlexibleFloatField(
        label=_("η ou K - Coeficiente reológico direto"),
        initial=_coeficiente_padrao_cp,
        min_value=0,
        required=False,
        help_text=_("Informe η para Bingham ou K para Power Law/Herschel-Bulkley, na referência de 20 °C. O sistema ajustará pela viscosidade do fluido carreador."),
    )
    k_unidade = forms.ChoiceField(
        label=_("Unidade de η ou K"),
        choices=COEFICIENTE_UNIDADE_CHOICES,
        initial="cp",
        required=False,
    )
    n = FlexibleFloatField(
        label=_("n - Fator de potência da reologia"),
        initial=DEFAULT_ENTRADAS["n"],
        min_value=0,
        error_messages={"min_value": _("O índice reológico n deve estar entre 0 e 2.")},
        required=False,
        help_text=_("Índice de comportamento do fluido para modelos Power Law ou Herschel-Bulkley."),
    )
    n_pontos_elev = FlexibleIntegerField(
        label=_("Pontos de elevação"),
        initial=DEFAULT_ENTRADAS["n_pontos_elev"],
        required=False,
        min_value=2,
        help_text=_("Quantidade de pontos no perfil vertical y/D. Mais pontos deixam o perfil mais suave e aumentam o tempo de cálculo."),
    )
    yD_min = FlexibleFloatField(
        label=_("y/D mínimo"),
        initial=DEFAULT_ENTRADAS["yD_min"],
        required=False,
        min_value=0,
        max_value=1,
        help_text=_("Limite inferior do perfil vertical. Use valores entre 0 e 1."),
    )
    yD_max = FlexibleFloatField(
        label=_("y/D máximo"),
        initial=DEFAULT_ENTRADAS["yD_max"],
        required=False,
        min_value=0,
        max_value=1,
        help_text=_("Limite superior do perfil vertical. Use valores entre 0 e 1."),
    )
    erro = FlexibleFloatField(
        label=_("Critério de erro"),
        initial=DEFAULT_ENTRADAS["erro"],
        required=False,
        min_value=0,
        help_text=_("Tolerância de convergência do acoplamento β/f. Valores menores exigem mais iterações."),
    )
    max_iter = FlexibleIntegerField(
        label=_("Máximo de iterações"),
        initial=DEFAULT_ENTRADAS["max_iter"],
        required=False,
        min_value=1,
        max_value=100,
        help_text=_("Limite de iterações do acoplamento. O sistema limita a 100."),
    )
    U_inicial = FlexibleFloatField(
        label=_("U inicial dos gráficos (m/s)"),
        initial=DEFAULT_ENTRADAS["U_inicial"],
        required=False,
        min_value=0,
        help_text=_("Velocidade inicial usada para gerar as curvas dos gráficos."),
    )
    U_final = FlexibleFloatField(
        label=_("U final dos gráficos (m/s)"),
        initial=DEFAULT_ENTRADAS["U_final"],
        required=False,
        min_value=0,
        help_text=_("Velocidade final usada para gerar as curvas. Deve ser maior ou igual à inicial."),
    )
    U_passo = FlexibleFloatField(
        label=_("Passo de velocidade dos gráficos (m/s)"),
        initial=DEFAULT_ENTRADAS["U_passo"],
        required=False,
        min_value=0,
        help_text=_("Incremento entre velocidades calculadas nos gráficos. Exemplo: 0,05 ou 0.05."),
    )
    fator_perda = FlexibleFloatField(
        label=_("Fator de ajuste para perda de carga"),
        initial=DEFAULT_ENTRADAS["fator_perda"],
        required=False,
        min_value=0,
        help_text=_("Multiplicador aplicado à perda de carga calculada. Use 1 para sem ajuste."),
    )
    modelo_escoamento = forms.ChoiceField(
        label=_("Modelo de escoamento"),
        choices=MODELO_CHOICES,
        initial="auto",
        required=False,
        help_text=_("No automático, o sistema calcula heterogêneo e pergunta pelo homogêneo se C/Ca total for maior que 80%."),
    )
    tipo_fluido_homogeneo = forms.ChoiceField(
        label=_("Tipo de fluido homogêneo"),
        choices=TIPO_FLUIDO_CHOICES,
        initial="bingham",
        required=False,
        help_text=_("Escolha o modelo reológico usado quando a linha homogênea for selecionada."),
    )
    gillies_cmax = FlexibleFloatField(
        label=_("Cmax - modelo de duas camadas"),
        initial=0.75,
        required=False,
        help_text=_("0,75 para distribuição ampla; 0,60 para distribuição estreita."),
    )
    gillies_eta_s = FlexibleFloatField(
        label=_("ηs - Atrito sólido-parede"),
        initial=0.50,
        min_value=0,
        required=False,
        help_text=_("Valor típico 0,50 para areia/cascalho/minerais; 0,40 pode ser usado para alguns carvões."),
    )
    gillies_mu_f_cp = FlexibleFloatField(
        label=_("µf - Viscosidade da fase fina (cP)"),
        initial=None,
        min_value=0,
        required=False,
        help_text=_("Opcional. Se vazio, usa a viscosidade do fluido informada acima."),
    )
    gillies_d12_mode = forms.ChoiceField(
        label=_("d12 - Interface hipotética"),
        choices=GILLIES_D12_CHOICES,
        initial="auto",
        required=False,
        help_text=_("Use automático pela granulometria. Manual apenas para debug."),
    )
    gillies_d12_manual_um = FlexibleFloatField(
        label=_("d12 manual/debug (µm)"),
        initial=150.0,
        min_value=0,
        required=False,
        help_text=_("Usado somente quando d12 estiver em modo manual/debug."),
    )

    @staticmethod
    def _diametro_para_metros(valor, unidade):
        if unidade == "pol":
            return valor * 0.0254
        if unidade == "mm":
            return valor / 1000
        if unidade == "m":
            return valor
        raise forms.ValidationError(_("Unidade de diâmetro inválida."))

    @staticmethod
    def _rugosidade_para_metros(valor, unidade):
        if unidade == "mm":
            return valor / 1000
        if unidade == "um":
            return valor * 1e-6
        if unidade == "m":
            return valor
        raise forms.ValidationError(_("Unidade de rugosidade inválida."))

    @staticmethod
    def _tau0_para_dyn_cm2(valor, unidade):
        if unidade == "pa":
            return valor * 10
        if unidade == "kpa":
            return valor * 10000
        if unidade == "dyn_cm2":
            return valor
        raise forms.ValidationError(_("Unidade de tensão de escoamento inválida."))

    @staticmethod
    def _coeficiente_para_cp(valor, unidade):
        if unidade in {"cp", "mpa_s"}:
            return valor
        if unidade == "pa_s":
            return valor * 1000
        raise forms.ValidationError(_("Unidade do coeficiente reológico inválida."))

    def clean(self):
        cleaned = super().clean()
        velocidade = cleaned.get("velocidade")
        diametro = cleaned.get("diametro_entrada")
        diametro_unidade = cleaned.get("diametro_unidade")
        rugosidade = cleaned.get("rugosidade_absoluta")
        rugosidade_unidade = cleaned.get("rugosidade_unidade")
        if cleaned.get("entrada_reologia") is None:
            cleaned["entrada_reologia"] = "laboratorio"
        if cleaned.get("n") is None:
            cleaned["n"] = DEFAULT_ENTRADAS["n"]
        if not cleaned.get("modelo_escoamento"):
            cleaned["modelo_escoamento"] = "heterogeneo"
        if not cleaned.get("tipo_fluido_homogeneo"):
            cleaned["tipo_fluido_homogeneo"] = "bingham"
        for nome in ("n_pontos_elev", "yD_min", "yD_max", "erro", "max_iter", "U_inicial", "U_final", "U_passo", "fator_perda"):
            if cleaned.get(nome) is None:
                cleaned[nome] = DEFAULT_ENTRADAS[nome]
        n = cleaned.get("n")
        if velocidade is not None and velocidade <= 0:
            self.add_error("velocidade", _("A velocidade operacional deve ser maior que zero."))
        if n is not None and not 0 < n < 2:
            self.add_error("n", _("O índice reológico n deve estar entre 0 e 2."))

        proporcoes_texto = cleaned.get("proporcoes_percent")
        diametros_texto = cleaned.get("diametros_um")
        if proporcoes_texto is not None:
            try:
                proporcoes = [float(parte.strip()) for parte in str(proporcoes_texto).split(",") if parte.strip()]
            except ValueError:
                proporcoes = None
            if proporcoes is not None:
                if any(valor < 0 for valor in proporcoes):
                    self.add_error("proporcoes_percent", _("As frações granulométricas não podem ser negativas."))
                elif sum(proporcoes) <= 0:
                    self.add_error("proporcoes_percent", _("A soma das frações granulométricas deve ser maior que zero."))
        if diametros_texto is not None:
            try:
                diametros = [float(parte.strip()) for parte in str(diametros_texto).split(",") if parte.strip()]
            except ValueError:
                diametros = None
            if diametros is not None and any(valor <= 0 for valor in diametros):
                self.add_error("diametros_um", _("Todos os diâmetros granulométricos devem ser maiores que zero."))

        if diametro is None or not diametro_unidade or rugosidade is None or not rugosidade_unidade:
            return cleaned

        diametro_m = self._diametro_para_metros(diametro, diametro_unidade)
        rugosidade_m = self._rugosidade_para_metros(rugosidade, rugosidade_unidade)
        if diametro_m <= 0:
            raise forms.ValidationError(_("O diâmetro interno convertido deve ser maior que zero."))
        if rugosidade_m <= 0:
            self.add_error("rugosidade_absoluta", _("A rugosidade deve ser maior que zero."))
            return cleaned

        cleaned["diametro_pol"] = diametro_m / 0.0254
        cleaned["rugosidade_relativa"] = rugosidade_m / diametro_m
        cleaned["diametro_m"] = diametro_m
        cleaned["rugosidade_absoluta_m"] = rugosidade_m

        concentracao_informada = cleaned.get("phi_total")
        tipo_concentracao = cleaned.get("tipo_concentracao")
        rho_s = cleaned.get("rho_s")
        rho_l = cleaned.get("rho_l")
        if concentracao_informada is None or not tipo_concentracao or rho_s is None or rho_l is None:
            return cleaned
        if rho_s <= rho_l:
            self.add_error(
                "rho_s",
                _("Para o modelo atual, a densidade dos sólidos deve ser maior que a densidade do líquido."),
            )
            return cleaned
        cv_equivalente = converter_concentracao_para_cv(concentracao_informada, tipo_concentracao, rho_s, rho_l)
        cleaned["concentracao_informada"] = concentracao_informada
        cleaned["cv_equivalente"] = cv_equivalente
        cleaned["phi_total"] = cv_equivalente

        if cleaned.get("entrada_reologia") == "laboratorio":
            if any(cleaned.get(nome) is None for nome in ("A", "B", "B_linha")):
                raise forms.ValidationError(_("Informe A, B e B' no modo de parâmetros laboratoriais."))

        if cleaned.get("entrada_reologia") == "direta":
            phi = cleaned.get("phi_total")
            mu_l_cp = cleaned.get("mu_l_cp")
            tipo_fluido = cleaned.get("tipo_fluido_homogeneo")
            if tipo_fluido == "bingham":
                coeficiente = cleaned.get("eta_direta")
                coeficiente_unidade = cleaned.get("eta_unidade")
            else:
                coeficiente = cleaned.get("k_direto")
                coeficiente_unidade = cleaned.get("k_unidade")
            tau0 = cleaned.get("tau0_direto")
            tau0_unidade = cleaned.get("tau0_unidade")

            if phi is None or not 0 < phi < 1:
                raise forms.ValidationError(_("A entrada reológica direta exige φ entre 0 e 1."))
            if mu_l_cp is None or mu_l_cp <= 0:
                raise forms.ValidationError(_("A entrada reológica direta exige viscosidade do fluido maior que zero."))
            if coeficiente is None or not coeficiente_unidade or coeficiente <= 0:
                raise forms.ValidationError(_("Informe η/K direto maior que zero e sua unidade."))

            coeficiente_cp = self._coeficiente_para_cp(coeficiente, coeficiente_unidade)
            fator_ajuste = mu_l_cp / 1.002
            coeficiente_ajustado_cp = fator_ajuste * coeficiente_cp

            if tipo_fluido == "powerlaw":
                tau0_dyn_cm2 = 0.0
            else:
                if tau0 is None or not tau0_unidade or tau0 < 0:
                    raise forms.ValidationError(_("Informe τ₀ direto e sua unidade para Bingham ou Herschel-Bulkley."))
                tau0_dyn_cm2 = self._tau0_para_dyn_cm2(tau0, tau0_unidade)

            cleaned["B"] = 1.0
            cleaned["A"] = tau0_dyn_cm2 / phi
            cleaned["B_linha"] = math.log10(coeficiente_cp) * ((1 - phi) / phi)
            cleaned["tau0_direto_pa"] = tau0_dyn_cm2 * 0.1
            cleaned["coeficiente_direto_cp"] = coeficiente_cp
            cleaned["coeficiente_ajustado_cp"] = coeficiente_ajustado_cp
        if cleaned.get("fourcm_vmin") is None:
            cleaned["fourcm_vmin"] = cleaned.get("U_inicial") or 0.5
        if cleaned.get("fourcm_vmax") is None:
            cleaned["fourcm_vmax"] = cleaned.get("U_final") or 8.0
        if cleaned.get("fourcm_vmax") is not None and cleaned.get("fourcm_vmin") is not None and cleaned["fourcm_vmax"] <= cleaned["fourcm_vmin"]:
            self.add_error("fourcm_vmax", _("A velocidade máxima do gráfico deve ser maior que a mínima."))
        if cleaned.get("vscalc_vmax") is not None and cleaned.get("vscalc_vmin") is not None and cleaned["vscalc_vmax"] <= cleaned["vscalc_vmin"]:
            self.add_error("vscalc_vmax", _("A velocidade máxima do gráfico deve ser maior que a mínima."))
        if cleaned.get("vscalc_dmax_um") is not None and cleaned.get("vscalc_dmin_um") is not None and cleaned["vscalc_dmax_um"] <= cleaned["vscalc_dmin_um"]:
            self.add_error("vscalc_dmax_um", _("O diâmetro final do gráfico deve ser maior que o inicial."))
        for nome, padrao in {"fourcm_mus": 0.48, "fourcm_af": 1.0, "fourcm_ap": 0.5, "fourcm_cf": 1.0, "fourcm_cp": 0.5, "fourcm_nc": 0.5, "fourcm_bf": 1.0, "fourcm_bp": 1.0, "fourcm_bh": 0.5, "fourcm_nb": 0.5, "vscalc_theta_deg": 0.0, "vscalc_cvb": 0.60, "vscalc_mus": 0.45, "vscalc_yplus": 5.0}.items():
            if cleaned.get(nome) is None:
                cleaned[nome] = padrao
        if cleaned.get("gillies_cmax") is None:
            cleaned["gillies_cmax"] = 0.75
        if cleaned.get("gillies_eta_s") is None:
            cleaned["gillies_eta_s"] = 0.50
        if not cleaned.get("gillies_d12_mode"):
            cleaned["gillies_d12_mode"] = "auto"
        return cleaned

    def as_entradas(self):
        entradas = self.cleaned_data.copy()
        entradas["diametro_pol"] = self.cleaned_data["diametro_pol"]
        entradas["rugosidade_relativa"] = self.cleaned_data["rugosidade_relativa"]
        if entradas.get("vscalc_d_mm") is not None:
            entradas["vscalc_d_mm"] = entradas["vscalc_d_mm"] / 1000.0
        return entradas


# Translate presentation text while preserving every stable value consumed by
# the calculation engine.
for _field in SimulacaoForm.base_fields.values():
    if _field.label:
        _field.label = _(_field.label)
    if _field.help_text:
        _field.help_text = _(_field.help_text)
    if getattr(_field, "choices", None):
        _field.choices = [(value, _(caption)) for value, caption in _field.choices]
