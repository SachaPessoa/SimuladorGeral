from django.contrib import messages
import copy

from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.utils.translation import gettext as _

from .codigo.four_cm_engine import _calc_once as calcular_4cm_ponto, executar_4cm
from .codigo.calculos import normalizar_entradas
from .codigo.gillies_engine import run_gillies
from .codigo.modelo import executar_simulacao
from .codigo.vscalc_engine import executar_vscalc
from .forms import SimulacaoForm
from .models import Simulacao


SLURRY_FORM_SESSION_KEY = "ultimas_entradas_formulario"
VSCALC_FORM_SESSION_KEY = "ultimas_entradas_vscalc"
SLURRY_SESSION_EXCLUDED_PREFIXES = ("vscalc_",)


def _formatar_valor(valor):
    if valor is None:
        return "-"
    if isinstance(valor, str):
        return valor
    try:
        numero = float(valor)
    except (TypeError, ValueError):
        return valor

    absoluto = abs(numero)
    if absoluto == 0:
        return "0"
    if absoluto >= 1e6 or absoluto < 1e-4:
        return f"{numero:.3e}"
    if absoluto >= 1000:
        return f"{numero:.0f}"
    if absoluto >= 100:
        return f"{numero:.1f}"
    if absoluto >= 10:
        return f"{numero:.2f}"
    if absoluto >= 1:
        return f"{numero:.3f}".rstrip("0").rstrip(".")
    return f"{numero:.4g}"



def _fator_perda(entradas):
    try:
        return float(entradas.get("fator_perda") or 1.0)
    except (TypeError, ValueError):
        return 1.0


def _aplicar_fator_ajuste_4cm(fourcm, fator):
    if abs(fator - 1.0) <= 1e-12:
        return fourcm
    results = fourcm.get("results", {})
    for chave in ("im", "iff", "dip", "dih", "dis", "headloss_m_polpa_km", "headloss_magua_km", "bar_km"):
        if results.get(chave) is not None:
            results[chave] = results[chave] * fator
    for linha in fourcm.get("rows", []):
        if linha.get("symbol") in {"J", "DeltaP 4CM", "DeltaP ref.", "if", "Delta ip", "Delta ih", "Delta is"} and linha.get("value") is not None:
            linha["value"] = linha["value"] * fator
    for item in fourcm.get("components", []):
        if item.get("gradient") is not None:
            item["gradient"] = item["gradient"] * fator
    graph = fourcm.get("graph", {})
    for chave in ("total", "carrier", "pseudo", "heterogeneo", "estratificado"):
        if graph.get(chave):
            graph[chave] = [valor * fator if valor is not None else None for valor in graph[chave]]
    return fourcm


def _calcular_curva_4cm_nas_velocidades(entradas, velocidades, fator):
    dados = normalizar_entradas(entradas)
    curva = {"velocidades": [], "total": [], "carrier": [], "pseudo": [], "heterogeneo": [], "estratificado": []}
    for velocidade in velocidades:
        rr = calcular_4cm_ponto(dados, float(velocidade))
        curva["velocidades"].append(float(velocidade))
        curva["total"].append(rr["headloss_m_polpa_km"] * fator)
        curva["carrier"].append((rr["iff"] / rr["Sm"]) * 1000.0 * fator)
        curva["pseudo"].append((rr["dip"] / rr["Sm"]) * 1000.0 * fator)
        curva["heterogeneo"].append((rr["dih"] / rr["Sm"]) * 1000.0 * fator)
        curva["estratificado"].append((rr["dis"] / rr["Sm"]) * 1000.0 * fator)
    return curva

def _diagnosticos_erro_4cm(entradas, exc):
    avisos = []
    obrigatorios = {
        "diametro_pol": "diâmetro interno do tubo",
        "rugosidade_relativa": "rugosidade relativa",
        "velocidade": "velocidade operacional",
        "rho_s": "densidade das partículas",
        "rho_l": "densidade do fluido",
        "mu_l_cp": "viscosidade do fluido",
        "phi_total": "concentração volumétrica",
        "diametros_um": "diâmetros da PSD",
        "proporcoes_percent": "proporções da PSD",
    }
    for chave, rotulo in obrigatorios.items():
        valor = entradas.get(chave)
        if valor is None or valor == "" or valor == []:
            avisos.append(f"4CM: parâmetro ausente - {rotulo}.")
    diametros = entradas.get("diametros_um") or []
    proporcoes = entradas.get("proporcoes_percent") or []
    if diametros and proporcoes and len(diametros) != len(proporcoes):
        avisos.append("4CM: PSD inválida - diâmetros e proporções devem ter a mesma quantidade de classes.")
    try:
        if diametros and any(float(valor) <= 0 for valor in diametros):
            avisos.append("4CM: PSD inválida - todos os diâmetros devem ser positivos.")
        if proporcoes:
            soma = sum(float(valor) for valor in proporcoes)
            if abs(soma - 100.0) > 1e-3:
                avisos.append(f"4CM: PSD inválida - soma das proporções = {soma:.4g}%, esperado 100%.")
            if any(float(valor) < 0 for valor in proporcoes):
                avisos.append("4CM: PSD inválida - proporções negativas não são permitidas.")
    except (TypeError, ValueError):
        avisos.append("4CM: PSD inválida - diâmetros e proporções devem ser numéricos.")
    try:
        if float(entradas.get("rho_s") or 0) <= float(entradas.get("rho_l") or 0):
            avisos.append("4CM: densidade das partículas deve ser maior que a densidade do fluido.")
    except (TypeError, ValueError):
        pass
    try:
        u_ini = float(entradas.get("U_inicial") or 0)
        u_fim = float(entradas.get("U_final") or 0)
        passo = float(entradas.get("U_passo") or 0)
        if u_ini <= 0 or u_fim <= u_ini or passo <= 0:
            avisos.append("4CM: faixa de velocidades inválida - verifique U inicial, U final e passo.")
    except (TypeError, ValueError):
        avisos.append("4CM: faixa de velocidades inválida - U inicial, U final e passo devem ser numéricos.")
    detalhe = str(exc).strip()
    if detalhe:
        avisos.append(f"4CM: detalhe técnico - {detalhe}")
    return avisos or ["4CM não convergiu ou não pôde ser calculado para esta condição."]


def _destacar_parametros_4cm(fourcm):
    parametros = []
    for linha in fourcm.get("rows", []):
        if linha.get("symbol") in {"A''", "B''", "C''", "Vsm,h", "V50,h", "V100,s"}:
            parametros.append(dict(linha))
    fourcm["parameter_rows"] = parametros
    return fourcm

def _anexar_gillies(resultado, entradas):
    if resultado.get("resumo", {}).get("modelo_escoamento") == "homogeneo":
        resultado.pop("gillies", None)
        return resultado
    gillies = run_gillies(entradas)

    principal_m_km = resultado.get("resumo", {}).get("perda_carga_operacao")
    principal_bar_km = resultado.get("resumo", {}).get("perda_carga_bar_km")
    if gillies.get("converged") and principal_m_km is not None:
        results = gillies.setdefault("results", {})
        gillies_m_km = results.get("headloss_m_polpa_km") or results.get("headloss_mca_km")
        if gillies_m_km is not None:
            diff_abs = gillies_m_km - principal_m_km
            results["main_headloss_m_km"] = principal_m_km
            results["main_pressure_bar_km"] = principal_bar_km
            results["headloss_difference_abs_m_km"] = diff_abs
            results["headloss_difference_percent"] = 100 * diff_abs / principal_m_km if abs(principal_m_km) > 1e-12 else None
            if principal_bar_km is not None and results.get("pressure_gradient_bar_km") is not None:
                results["pressure_difference_abs_bar_km"] = results["pressure_gradient_bar_km"] - principal_bar_km
    resultado["gillies"] = gillies
    return resultado


def _anexar_4cm(resultado, entradas):
    if resultado.get("resumo", {}).get("modelo_escoamento") != "heterogeneo":
        resultado.pop("fourcm", None)
        return resultado

    try:
        fator = _fator_perda(entradas)
        fourcm = _aplicar_fator_ajuste_4cm(executar_4cm(entradas), fator)
    except Exception as exc:
        avisos_4cm = _diagnosticos_erro_4cm(entradas, exc)
        resultado["fourcm"] = {
            "converged": False,
            "message": "4CM não convergiu ou não pôde ser calculado para esta condição.",
            "warnings": avisos_4cm,
            "rows": [],
            "components": [],
            "graph": {},
        }
        resultado.setdefault("avisos", []).extend(avisos_4cm)
        return resultado


    fourcm = _destacar_parametros_4cm(fourcm)

    principal_m_km = resultado.get("resumo", {}).get("perda_carga_operacao")
    principal_bar_km = resultado.get("resumo", {}).get("perda_carga_bar_km")
    r4 = fourcm.get("results", {})
    fourcm_m_km = r4.get("headloss_m_polpa_km")
    fourcm_bar_km = r4.get("bar_km")
    if principal_m_km is not None and fourcm_m_km is not None:
        diff_abs = fourcm_m_km - principal_m_km
        fourcm["comparison_rows"] = [
            {"model": "WASP Modificado", "value": principal_m_km, "unit": "m coluna de polpa/km"},
            {"model": "4CM", "value": fourcm_m_km, "unit": "m coluna de polpa/km"},
            {"model": "Diferença 4CM - WASP", "value": diff_abs, "unit": "m coluna de polpa/km"},
            {"model": "Diferença relativa", "value": 100 * diff_abs / principal_m_km if abs(principal_m_km) > 1e-12 else None, "unit": "%"},
        ]
        if principal_bar_km is not None and fourcm_bar_km is not None:
            fourcm["comparison_rows"].extend([
                {"model": "WASP Modificado", "value": principal_bar_km, "unit": "bar/km"},
                {"model": "4CM", "value": fourcm_bar_km, "unit": "bar/km"},
            ])

    grafico_perda = resultado.setdefault("graficos", {}).setdefault("perda_carga", {})
    velocidades_wasp = grafico_perda.get("velocidades") or []
    if velocidades_wasp:
        graph = _calcular_curva_4cm_nas_velocidades(entradas, velocidades_wasp, fator)
        fourcm["graph"] = graph
    else:
        graph = fourcm.get("graph", {})
    if graph:
        grafico_perda["fourcm_velocidades"] = list(grafico_perda.get("velocidades") or graph.get("velocidades", []))
        grafico_perda["fourcm_total"] = graph.get("total", [])
        grafico_perda["fourcm_componentes"] = {
            "carrier": graph.get("carrier", []),
            "pseudo": graph.get("pseudo", []),
            "heterogeneo": graph.get("heterogeneo", []),
            "estratificado": graph.get("estratificado", []),
        }
    grafico_perda["scale"] = entradas.get("fourcm_scale") or "log"
    resultado["fourcm"] = fourcm
    return resultado


def _preparar_resultado_para_tela(resultado):
    entradas = resultado.get("entradas", {})
    resumo = resultado.setdefault("resumo", {})
    tabela = resultado.get("tabela_resultados", [])
    if resultado.get("tipo_resultado") == "vscalc":
        for linha in tabela:
            linha["simbolo"] = _(linha.get("simbolo", ""))
            linha["descricao"] = _(linha.get("descricao", ""))
            if linha.get("help_text"):
                linha["help_text"] = _(linha["help_text"])
            if isinstance(linha.get("valor"), str):
                linha["valor"] = _(linha["valor"])
            linha["valor_formatado"] = _formatar_valor(linha.get("valor"))
        resultado["avisos"] = [_(aviso) for aviso in resultado.get("avisos", [])]
        _traduzir_textos_graficos(resultado.get("graficos", {}))
        return resultado
    phi_v_percent = 100 * float(entradas.get("phi_total") or 0)
    resumo["phi_v_percent"] = phi_v_percent
    if resumo.get("perda_carga_bar_km") is None:
        densidade_polpa = resumo.get("densidade_polpa")
        if densidade_polpa is None:
            densidade_polpa = next(
                (linha.get("valor") for linha in tabela if linha.get("simbolo") == "ρₘ"),
                None,
            )
        if densidade_polpa is not None and resumo.get("perda_carga_operacao") is not None:
            resumo["densidade_polpa"] = densidade_polpa
            resumo["perda_carga_bar_km"] = float(resumo["perda_carga_operacao"]) * float(densidade_polpa) * 9.80665 / 1e5
    if resumo.get("modelo_escoamento") == "heterogeneo":
        resumo["phi_vv_percent"] = 100 * float(resumo.get("cv_veiculo") or 0)
    else:
        resultado.pop("gillies", None)
        resultado.get("graficos", {}).pop("gillies_secao", None)

    tabela[:] = [
        linha for linha in tabela
        if linha.get("simbolo") not in {"Cv equivalente", _("Cv equivalente")}
    ]
    for linha in tabela:
        if linha.get("descricao") == "Concentração Volumétrica Veículo":
            linha["simbolo"] = "φ<sub>VV</sub>"
            linha["descricao"] = "Fração volumétrica do veículo"
        elif linha.get("descricao") == "Fator de atrito operacional":
            linha["descricao"] = "Fator de atrito Fanning operacional"
        elif linha.get("descricao") == "Fator de atrito final":
            linha["descricao"] = "Fator de atrito Fanning final"

    tabela[:] = [linha for linha in tabela if linha.get("simbolo") != "φ<sub>V</sub>"]
    indice_phi_vv = next(
        (indice for indice, linha in enumerate(tabela) if linha.get("simbolo") == "φ<sub>VV</sub>"),
        len(tabela),
    )
    tabela.insert(indice_phi_vv, {
            "simbolo": "φ<sub>V</sub>",
            "descricao": _("Fração volumétrica total"),
            "valor": phi_v_percent,
            "unidade": "%",
    })
    if not any(linha.get("simbolo") == "Tipo de f" for linha in tabela):
        tabela.append({
            "simbolo": _("Tipo de f"),
            "descricao": _("Convenção do fator de atrito utilizada"),
            "valor": "Fanning",
            "unidade": "-",
        })
    if entradas.get("entrada_reologia") == "direta" and not any(
        linha.get("simbolo") == "A equivalente" for linha in tabela
    ):
        tabela.extend([
            {"simbolo": _("A equivalente"), "descricao": _("Parâmetro interno convertido da entrada reológica direta"), "valor": entradas.get("A"), "unidade": "-"},
            {"simbolo": _("B equivalente"), "descricao": _("Parâmetro interno convertido da entrada reológica direta"), "valor": entradas.get("B"), "unidade": "-"},
            {"simbolo": _("B' equivalente"), "descricao": _("Parâmetro interno convertido da entrada reológica direta"), "valor": entradas.get("B_linha"), "unidade": "-"},
            {"simbolo": _("η/K ref. 20 °C"), "descricao": _("Coeficiente reológico direto informado na referência de 20 °C"), "valor": entradas.get("coeficiente_direto_cp"), "unidade": "cP"},
            {"simbolo": _("η/K ajustado"), "descricao": _("Coeficiente reológico após ajuste pela viscosidade do fluido carreador"), "valor": entradas.get("coeficiente_ajustado_cp"), "unidade": "cP"},
        ])
    for linha in tabela:
        linha["simbolo"] = _(linha.get("simbolo", ""))
        linha["descricao"] = _(linha.get("descricao", ""))
        if isinstance(linha.get("valor"), str):
            linha["valor"] = _(linha["valor"])
        linha["valor_formatado"] = _formatar_valor(linha.get("valor"))
    resultado["avisos"] = [_(aviso) for aviso in resultado.get("avisos", [])]
    if resultado.get("fourcm"):
        resultado["fourcm"] = _preparar_4cm_para_tela(resultado["fourcm"])
    if resultado.get("gillies"):
        resultado["gillies"] = _preparar_gillies_para_tela(resultado["gillies"])
        if resultado["gillies"].get("converged"):
            g = resultado["gillies"]["results"]
            resultado.setdefault("graficos", {})["gillies_secao"] = {
                "altura_interface_yD": g.get("lower_layer_height_over_D"),
                "A2_over_A": g.get("A2_over_A"),
                "U1": g.get("U1"),
                "U2": g.get("U2"),
                "C1": g.get("C1"),
                "Clim": g.get("Clim"),
                "d12_um": g.get("d12_um"),
            }
    _traduzir_textos_graficos(resultado.get("graficos", {}))
    return resultado


def _preparar_4cm_para_tela(fourcm):
    descricoes_parametros = {
        "Vsm,h": _(
            "Velocidade mínima para evitar a deposição estacionária da fração heterogênea. "
            "Acima desta velocidade, essa fração permanece em movimento, podendo ainda existir leito móvel. "
            "Não representa suspensão completa."
        ),
        "V50,h": _(
            "Velocidade característica da fração heterogênea, calculada a partir do D50 dessa fração. "
            "É utilizada pelo modelo 4CM para estimar a contribuição da parcela heterogênea na perda de carga. "
            "Não representa velocidade de deposição nem velocidade de suspensão completa."
        ),
        "V100,s": _(
            "Velocidade estimada para suspensão completa da fração estratificada. "
            "Acima desta velocidade, o modelo considera que a camada estratificada desaparece e toda essa fração passa a ser transportada em suspensão."
        ),
    }
    fourcm["message"] = _(fourcm.get("message", ""))
    fourcm["warnings"] = [_(aviso) for aviso in fourcm.get("warnings", [])]
    for linha in fourcm.get("rows", []):
        linha["description"] = _(linha.get("description", ""))
        linha["unit"] = _(linha.get("unit", ""))
        if linha.get("symbol") in descricoes_parametros:
            linha["help_text"] = descricoes_parametros[linha["symbol"]]
        linha["value_formatted"] = _formatar_valor(linha.get("value"))
    for item in fourcm.get("components", []):
        item["name"] = _(item.get("name", ""))
        item["fraction_formatted"] = _formatar_valor(100 * float(item.get("fraction") or 0))
        item["gradient_formatted"] = _formatar_valor(item.get("gradient"))
    for linha in fourcm.get("comparison_rows", []):
        linha["model"] = _(linha.get("model", ""))
        linha["unit"] = _(linha.get("unit", ""))
        linha["value_formatted"] = _formatar_valor(linha.get("value"))
    for linha in fourcm.get("parameter_rows", []):
        linha["description"] = _(linha.get("description", ""))
        linha["unit"] = _(linha.get("unit", ""))
        if linha.get("symbol") in descricoes_parametros:
            linha["help_text"] = descricoes_parametros[linha["symbol"]]
        linha["value_formatted"] = _formatar_valor(linha.get("value"))
    results = fourcm.get("results", {})
    fourcm["velocity_scale"] = [
        {"label": "Vsm,h", "value": results.get("Vsmh"), "value_formatted": _formatar_valor(results.get("Vsmh")), "description": descricoes_parametros["Vsm,h"]},
        {"label": "V100,s", "value": results.get("V100"), "value_formatted": _formatar_valor(results.get("V100")), "description": descricoes_parametros["V100,s"]},
    ]
    return fourcm


def _preparar_gillies_para_tela(gillies):
    gillies["message"] = _(gillies.get("message", ""))
    diagnostics = gillies.get("diagnostics", {})
    diagnostics["warnings"] = [_(aviso) for aviso in diagnostics.get("warnings", [])]
    results = gillies.get("results", {})
    if gillies.get("converged"):
        h_over_d = max(0.0, min(1.0, float(results.get("lower_layer_height_over_D") or 0.0)))
        lower_h = 300.0 * h_over_d
        interface_y = 360.0 - lower_h
        dy = interface_y - 210.0
        chord_half = (max(0.0, 150.0**2 - dy**2)) ** 0.5
        gillies["section_plot"] = {
            "lower_y": interface_y,
            "lower_h": lower_h,
            "interface_y": interface_y,
            "interface_x1": 220.0 - chord_half,
            "interface_x2": 220.0 + chord_half,
        }
    rows = [
        ("ΔP Wasp mod.", _("Perda de carga Wasp modificado"), results.get("main_headloss_m_km"), "m/km"),
        ("ΔP Wasp mod.", _("Perda de carga Wasp modificado"), results.get("main_pressure_bar_km"), "bar/km"),
        ("ΔP 2 camadas", _("Perda de carga do modelo de duas camadas"), results.get("headloss_m_polpa_km"), "m/km"),
        ("ΔP 2 camadas", _("Perda de carga do modelo de duas camadas"), results.get("pressure_gradient_bar_km"), "bar/km"),
        ("Δ abs", _("Diferença absoluta"), results.get("headloss_difference_abs_m_km"), "m/km"),
        ("Δ abs", _("Diferença absoluta"), results.get("pressure_difference_abs_bar_km"), "bar/km"),
        ("Δ %", _("Diferença percentual"), results.get("headloss_difference_percent"), "%"),
        ("U", _("Velocidade média"), results.get("U"), "m/s"),
        ("U1", _("Velocidade camada superior"), results.get("U1"), "m/s"),
        ("U2", _("Velocidade camada inferior"), results.get("U2"), "m/s"),
        ("Ct", _("Concentração total in situ"), results.get("Ct"), "-"),
        ("Cd", _("Concentração total entregue/calculada"), results.get("Cd"), "-"),
        ("Cf", _("Finos -74 µm"), results.get("Cf"), "-"),
        ("Cr", _("Grossos +74 µm"), results.get("Cr"), "-"),
        ("Cc", _("Carga de contato"), results.get("Cc"), "-"),
        ("Cc/Cr", _("Fração de carga de contato"), results.get("Cc_over_Cr"), "-"),
        ("C1", _("Grossos suspensos na camada superior"), results.get("C1"), "-"),
        ("C2", _("Incremento de grossos na camada inferior"), results.get("C2"), "-"),
        ("Clim", _("Grossos totais na camada inferior = C1 + C2"), results.get("Clim"), "-"),
        ("A2/A", _("Fração de área da camada inferior"), results.get("A2_over_A"), "-"),
        ("h2", _("Altura da camada inferior"), results.get("lower_layer_height_m"), "m"),
        ("h2/D", _("Altura relativa da camada inferior"), results.get("lower_layer_height_over_D"), "-"),
        ("d50*", _("d50 dos grossos +74 µm"), results.get("d50_coarse_um"), "µm"),
        ("d12", _("d12 calculado/usado"), results.get("d12_um"), "µm"),
    ]
    gillies["rows"] = [
        {
            "symbol": symbol,
            "description": description,
            "value": value,
            "value_formatted": _formatar_valor(value),
            "unit": unit,
        }
        for symbol, description, value, unit in rows
        if value is not None
    ]
    gillies["diagnostic_rows"] = [
        {"symbol": "Cr-(C1+Cc)", "value": diagnostics.get("error_Cr"), "value_formatted": _formatar_valor(diagnostics.get("error_Cr"))},
        {"symbol": "Clim-(C1+C2)", "value": diagnostics.get("error_Clim"), "value_formatted": _formatar_valor(diagnostics.get("error_Clim"))},
        {"symbol": "Cc-C2*A2/A", "value": diagnostics.get("error_Cc"), "value_formatted": _formatar_valor(diagnostics.get("error_Cc"))},
        {"symbol": _("Iterações"), "value": diagnostics.get("iterations"), "value_formatted": _formatar_valor(diagnostics.get("iterations"))},
        {"symbol": _("Status"), "value": diagnostics.get("status"), "value_formatted": diagnostics.get("status") or "-"},
    ]
    return gillies


def _traduzir_textos_graficos(valor):
    if isinstance(valor, dict):
        for chave, item in valor.items():
            if chave in {"name", "nome", "titulo"} and isinstance(item, str):
                valor[chave] = _(item)
            else:
                _traduzir_textos_graficos(item)
    elif isinstance(valor, list):
        for item in valor:
            _traduzir_textos_graficos(item)


def _salvar_ultimas_entradas_formulario(request, form, session_key=SLURRY_FORM_SESSION_KEY, excluded_prefixes=()):
    request.session[session_key] = {
        name: value
        for name in form.fields
        for value in [
            (
                form.cleaned_data.get("concentracao_informada")
                if name == "phi_total"
                else form.cleaned_data.get(name)
            )
        ]
        if value not in (None, "")
        and not any(name.startswith(prefix) for prefix in excluded_prefixes)
    }


def _initial_salvo(request, session_key, excluded_prefixes=()):
    initial = request.session.get(session_key) or {}
    if not isinstance(initial, dict):
        request.session.pop(session_key, None)
        return None
    cleaned = {
        key: value
        for key, value in initial.items()
        if value not in (None, "")
        and not any(key.startswith(prefix) for prefix in excluded_prefixes)
    }
    if cleaned != initial:
        request.session[session_key] = cleaned
    return cleaned or None


def _guardar_resultado_na_sessao(request, resultado):
    request.session["resultado_simulacao"] = resultado
    try:
        simulacao = Simulacao.objects.create(
            usuario=request.user,
            entradas=resultado["entradas"],
            resumo=resultado["resumo"],
        )
    except Exception as exc:
        request.session.pop("simulacao_id", None)
        messages.warning(
            request,
            _("Resultado calculado, mas não foi possível salvar o histórico da simulação: %(erro)s")
            % {"erro": str(exc)},
        )
    else:
        request.session["simulacao_id"] = simulacao.id


@login_required
def formulario(request):
    if request.method == "GET" and request.GET.get("reset") == "padrao":
        request.session.pop(SLURRY_FORM_SESSION_KEY, None)
        request.session.pop("entradas_pendentes_modelo", None)
        request.session.pop("resultado_heterogeneo_pendente", None)
        messages.info(request, _("Entradas restauradas para o padrão de fábrica."))
        return redirect("simulador:formulario")

    if request.method == "POST":
        if request.POST.get("decisao_modelo"):
            entradas = request.session.get("entradas_pendentes_modelo")
            heterogeneo_previo = request.session.get("resultado_heterogeneo_pendente")
            if not entradas:
                messages.error(request, _("Não encontrei a simulação pendente. Execute a simulação novamente."))
                return redirect("simulador:formulario")

            entradas["modelo_escoamento"] = request.POST.get("decisao_modelo")
            entradas["tipo_fluido_homogeneo"] = request.POST.get(
                "tipo_fluido_homogeneo",
                entradas.get("tipo_fluido_homogeneo", "bingham"),
            )
            resultado = heterogeneo_previo if entradas["modelo_escoamento"] == "heterogeneo" else executar_simulacao(entradas)
            resultado = _anexar_gillies(resultado, entradas)
            resultado = _anexar_4cm(resultado, entradas)
            if entradas["modelo_escoamento"] == "heterogeneo":
                resultado.setdefault("avisos", []).append(_("Critério de escoamento homogêneo atingido, mas o modelo heterogêneo foi selecionado."))

            _guardar_resultado_na_sessao(request, resultado)
            request.session.pop("entradas_pendentes_modelo", None)
            request.session.pop("resultado_heterogeneo_pendente", None)
            return redirect("simulador:resultado")

        form = SimulacaoForm(request.POST)
        if form.is_valid():
            _salvar_ultimas_entradas_formulario(
                request,
                form,
                SLURRY_FORM_SESSION_KEY,
                excluded_prefixes=SLURRY_SESSION_EXCLUDED_PREFIXES,
            )
            try:
                entradas = form.as_entradas()
                entradas["calculo_tipo"] = "perda_carga"
                resultado = executar_simulacao(entradas)
            except Exception as exc:
                messages.error(request, _(str(exc)))
            else:
                c0ca_total = float(resultado.get("resumo", {}).get("c0ca_total_percent") or 0)
                if entradas.get("modelo_escoamento") == "auto" and c0ca_total > 80:
                    request.session["entradas_pendentes_modelo"] = entradas
                    request.session["resultado_heterogeneo_pendente"] = resultado
                    return render(
                        request,
                        "simulador/selecionar_modelo.html",
                        {
                            "c0ca_total": c0ca_total,
                            "tipo_fluido_atual": entradas.get("tipo_fluido_homogeneo", "bingham"),
                        },
                    )
                resultado = _anexar_gillies(resultado, entradas)
                resultado = _anexar_4cm(resultado, entradas)
                _guardar_resultado_na_sessao(request, resultado)
                return redirect("simulador:resultado")
        else:
            messages.error(request, _("Revise os campos destacados antes de calcular."))
    else:
        form = SimulacaoForm(
            initial=_initial_salvo(
                request,
                SLURRY_FORM_SESSION_KEY,
                excluded_prefixes=SLURRY_SESSION_EXCLUDED_PREFIXES,
            )
        )
    return render(request, "simulador/formulario.html", {"form": form})


@login_required
def vscalc(request):
    if request.method == "GET" and request.GET.get("reset") == "padrao":
        request.session.pop(VSCALC_FORM_SESSION_KEY, None)
        messages.info(request, _("Entradas restauradas para o padrão de fábrica."))
        return redirect("simulador:vscalc")

    if request.method == "POST":
        form = SimulacaoForm(request.POST)
        if form.is_valid():
            _salvar_ultimas_entradas_formulario(request, form, VSCALC_FORM_SESSION_KEY)
            try:
                entradas = form.as_entradas()
                entradas["calculo_tipo"] = "vscalc"
                resultado = executar_vscalc({k: v for k, v in entradas.items() if v not in (None, "")})
            except Exception as exc:
                messages.error(request, _(str(exc)))
            else:
                _guardar_resultado_na_sessao(request, resultado)
                return redirect("simulador:resultado")
        else:
            messages.error(request, _("Revise os campos destacados antes de calcular."))
    else:
        form = SimulacaoForm(initial=_initial_salvo(request, VSCALC_FORM_SESSION_KEY))
    return render(request, "simulador/vscalc_formulario.html", {"form": form})


@login_required
def resultado(request):
    resultado_simulacao = request.session.get("resultado_simulacao")
    if not resultado_simulacao:
        messages.info(request, _("Execute uma simulação primeiro."))
        return redirect("simulador:formulario")

    resultado_tela = _preparar_resultado_para_tela(copy.deepcopy(resultado_simulacao))
    return render(
        request,
        "simulador/resultado.html",
        {
            "resultado": resultado_tela,
            "graficos": resultado_tela["graficos"],
        },
    )
