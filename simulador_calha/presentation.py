import math

import numpy as np
from django.utils.translation import gettext as _

from .calha_core import (
    avaliar_regime_turbulento,
    calcular_para_h,
    velocidade_deposicao_abulnaga_1,
    velocidade_deposicao_green,
)


def formatar_valor(valor):
    if valor is None:
        return "-"
    if isinstance(valor, str):
        return valor
    try:
        numero = float(valor)
    except (TypeError, ValueError):
        return str(valor)
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


def linha(simbolo, descricao, valor, unidade="-"):
    valor_formatado = formatar_valor(valor)
    return {
        "simbolo": _(simbolo),
        "descricao": _(descricao),
        "valor": valor,
        "valor_formatado": _(valor_formatado) if isinstance(valor, str) else valor_formatado,
        "unidade": unidade,
    }


def montar_tabela(dados, r):
    massa, reol, final = r["massa"], r["reologia"], r["final"]
    liso, rugoso = r["liso"], r["rugoso"]
    dep, turb = r["deposicao"], r["turbulencia"]
    linhas = [
        linha("Q", "Vazão calculada", final["Q_m3h"], "m³/h"),
        linha("U", "Velocidade média", final["U"], "m/s"),
        linha("h", "Altura de fluxo", final["h"], "m"),
        linha("h/h<sub>máx</sub>", "Preenchimento da seção", final["preenchimento"] * 100, "%"),
        linha("Regime", "Regime de rugosidade adotado", _(r["regime_final"]).capitalize()),
        linha("A", "Área molhada", final["A"], "m²"),
        linha("P", "Perímetro molhado", final["P"], "m"),
        linha("R<sub>h</sub>", "Raio hidráulico", final["Rh"], "m"),
        linha("D<sub>h</sub>", "Diâmetro hidráulico", final["Dh"], "m"),
        linha("B<sub>topo</sub>", "Largura da lâmina livre", final["Btopo"], "m"),
        linha("θ", "Ângulo molhado da seção tubular", final["theta"], "rad"),
        linha("S", "Inclinação longitudinal", dados["S_percent"], "%"),
        linha("ε", "Rugosidade absoluta", dados["rugosidade_mm"], "mm"),
        linha("ε/D<sub>h</sub>", "Rugosidade relativa hidráulica", dados["rugosidade"] / final["Dh"], "-"),
        linha("ρ<sub>m</sub>", "Densidade da polpa", massa["rhom"], "kg/m³"),
        linha("φ<sub>w</sub>", "Concentração mássica", massa["phiw"] * 100, "%"),
        linha("φ<sub>V</sub>", "Concentração volumétrica", massa["phiv"] * 100, "%"),
        linha("V<sub>r</sub>", "Razão volumétrica de sólidos", massa["Vr"], "-"),
        linha("Entrada", "Modo de entrada reológica", "Parâmetros diretos" if dados.get("entrada_reologia") == "direta" else "Constantes laboratoriais"),
        linha("A", "Constante reológica interna equivalente", dados["A_lab"], "dyn/cm²"),
        linha("B", "Expoente reológico interno equivalente", dados["B_lab"], "-"),
        linha("B'", "Parâmetro de rigidez interno equivalente", dados["B_linha_lab"], "-"),
        linha("τ<sub>0</sub>", "Tensão de escoamento", reol["tau0_Pa"], "Pa"),
        linha("τ<sub>0</sub>", "Tensão de escoamento laboratorial", reol["tau0_dyn_cm2"], "dyn/cm²"),
        linha("η", "Coeficiente de rigidez", reol["eta_cP"], "cP"),
        linha("η", "Coeficiente de rigidez", reol["eta_Pa_s"], "Pa·s"),
        linha("Re", "Número de Reynolds operacional", final["Re"], "-"),
        linha("He", "Número de Hedstrom operacional", final["He"], "-"),
        linha("f<sub>F</sub>", "Fator de atrito de Fanning", final["fF"], "-"),
        linha("f<sub>D</sub>", "Fator de atrito de Darcy", final["fD"], "-"),
        linha("Fr", "Número de Froude", final["Fr"], "-"),
        linha("Fr", "Classificação hidráulica de Froude", final["classificacao_Fr"]),
        linha("Fr", "Avaliação operacional de Froude", final["avaliacao_Fr_polpa"]),
        linha("n", "Manning equivalente", r["n_manning"], "s/m^(1/3)"),
        linha("δ<sub>v</sub>", "Espessura da subcamada laminar", r["delta_v"], "m"),
        linha("U<sub>t1</sub>", "Velocidade mínima - Abulnaga 1", dep["Ut1"], "m/s"),
        linha("U<sub>t2</sub>", "Velocidade mínima - Green/Abulnaga", dep["Ut2"], "m/s"),
        linha("U<sub>t2,base</sub>", "Velocidade Green/Abulnaga antes do fator 2", r["Ut2_base"], "m/s"),
        linha("U<sub>t,ref</sub>", "Velocidade mínima de referência", dep["Ut_ref"], "m/s"),
        linha("U/U<sub>t</sub>", "Margem sobre velocidade mínima", dep["margem_U_sobre_Ut"], "-"),
        linha("Deposição", "Classificação de suspensão", _(dep["classificacao"]).capitalize()),
        linha("Re<sub>c,N</sub>", "Reynolds crítico de Naik", turb["Rec_naik"], "-"),
        linha("φ<sub>c,N</sub>", "Parâmetro crítico de Naik", turb["phi_c_naik"], "-"),
        linha("Re<sub>c,H</sub>", "Reynolds crítico de Hanks", turb["Rec_hanks"], "-"),
        linha("φ<sub>c,H</sub>", "Parâmetro crítico de Hanks", turb["phi_c_hanks"], "-"),
        linha("Re<sub>c,D</sub>", "Reynolds crítico de Durand", turb["Rec_durand"], "-"),
        linha("Re<sub>c,ref</sub>", "Reynolds crítico de referência", turb["Rec_ref"], "-"),
        linha("Re/Re<sub>c</sub>", "Margem sobre Reynolds crítico", turb["margem_Re_sobre_Rec"], "-"),
        linha("Regime", "Regime laminar/turbulento", _(turb["regime"]).capitalize()),
        linha("h<sub>liso</sub>", "Altura calculada para superfície lisa", liso["h"], "m"),
        linha("U<sub>liso</sub>", "Velocidade para superfície lisa", liso["U"], "m/s"),
        linha("f<sub>D,liso</sub>", "Fator de Darcy para superfície lisa", liso["fD"], "-"),
        linha("h<sub>rugoso</sub>", "Altura calculada para superfície rugosa", rugoso["h"], "m"),
        linha("U<sub>rugoso</sub>", "Velocidade para superfície rugosa", rugoso["U"], "m/s"),
        linha("f<sub>D,rugoso</sub>", "Fator de Darcy para superfície rugosa", rugoso["fD"], "-"),
    ]
    return linhas


def montar_avisos(r):
    avisos = []
    final, dep, turb = r["final"], r["deposicao"], r["turbulencia"]
    if final["avaliacao_Fr_polpa"] != "adequado":
        avisos.append(
            _("Número de Froude avaliado como %(status)s.")
            % {"status": _(final["avaliacao_Fr_polpa"])}
        )
    if final["avaliacao_preenchimento"] != "adequado":
        avisos.append(
            _("Preenchimento da seção avaliado como %(status)s.")
            % {"status": _(final["avaliacao_preenchimento"])}
        )
    if dep["margem_U_sobre_Ut"] < 1:
        avisos.append(_(dep["mensagem"]))
    if turb["margem_Re_sobre_Rec"] < 1:
        avisos.append(_(turb["mensagem"]))
    return avisos


def amostrar_curvas(dados, resultado, pontos=61):
    limite = dados["hmax"] if dados["geometria"] == "trapezoidal" else dados["D"]
    alturas = np.linspace(limite * 0.02, limite * 0.98, pontos)
    dados_calc = {**dados, **resultado["massa"], **resultado["reologia"]}
    series = {"h": [], "liso": [], "rugoso": []}
    for h in alturas:
        try:
            liso = calcular_para_h(float(h), "liso", dados_calc)
            rugoso = calcular_para_h(float(h), "rugoso", dados_calc)
        except (ValueError, ArithmeticError, OverflowError):
            continue
        series["h"].append(float(h))
        series["liso"].append(liso)
        series["rugoso"].append(rugoso)
    return series


def secao_plotly(dados, resultado):
    final = resultado["final"]
    h = final["h"]
    tipo = dados.get("geometria_tipo", dados["geometria"])
    base_data = {
        "tipo": tipo,
        "h": h,
        "B": final["Btopo"],
        "A": final["A"],
        "P": final["P"],
        "Rh": final["Rh"],
        "Dh": final["Dh"],
        "preenchimento": final["preenchimento"] * 100,
    }
    if dados["geometria"] == "trapezoidal":
        b, hmax, m = dados["b"], dados["hmax"], dados["m"]
        contorno_x = [-b / 2 - m * hmax, -b / 2, b / 2, b / 2 + m * hmax]
        contorno_y = [hmax, 0, 0, hmax]
        agua_x = [-b / 2 - m * h, -b / 2, b / 2, b / 2 + m * h, -b / 2 - m * h]
        agua_y = [h, 0, 0, h, h]
        return {
            **base_data,
            "contorno_x": contorno_x, "contorno_y": contorno_y,
            "agua_x": agua_x, "agua_y": agua_y,
            "b": b, "m": m, "hmax": hmax,
            "largura_max": b + 2 * m * hmax,
        }

    D, pontos = dados["D"], 181
    R = D / 2
    t = np.linspace(0, 2 * math.pi, pontos)
    contorno_x = (R * np.cos(t)).tolist()
    contorno_y = (R + R * np.sin(t)).tolist()
    y = np.linspace(0, h, 100)
    xr = np.sqrt(np.maximum(R**2 - (y - R) ** 2, 0))
    agua_x = np.concatenate([-xr, xr[::-1], [-xr[0]]]).tolist()
    agua_y = np.concatenate([y, y[::-1], [y[0]]]).tolist()
    return {
        **base_data,
        "contorno_x": contorno_x, "contorno_y": contorno_y,
        "agua_x": agua_x, "agua_y": agua_y,
        "D": D, "theta": final["theta"], "theta_graus": math.degrees(final["theta"]),
    }


def montar_graficos(dados, r):
    amostra = amostrar_curvas(dados, r)
    h = amostra["h"]
    liso, rugoso = amostra["liso"], amostra["rugoso"]
    final = r["final"]
    rec_liso, rec_rugoso, ut1, ut2 = [], [], [], []
    for rl, rr in zip(liso, rugoso):
        rec_liso.append(avaliar_regime_turbulento(rl["Re"], rl["He"])["Rec_ref"])
        rec_rugoso.append(avaliar_regime_turbulento(rr["Re"], rr["He"])["Rec_ref"])
        ut1.append(velocidade_deposicao_abulnaga_1(rr["Rh"], dados["rhos"], r["massa"]["rhom"], dados["d85"]))
        ut2.append(velocidade_deposicao_green(dados["dp"], dados["rhos"], r["massa"]["rhom"], rr["fD"])[0])
    return {
        "hq": {
            "h": h, "q_liso": [x["Q_m3h"] for x in liso], "q_rugoso": [x["Q_m3h"] for x in rugoso],
            "operacao_q": final["Q_m3h"], "operacao_h": final["h"], "q_requerida": dados["Qreq_m3h"],
        },
        "secao": secao_plotly(dados, r),
        "velocidade": {
            "h": h, "u_liso": [x["U"] for x in liso], "u_rugoso": [x["U"] for x in rugoso],
            "ut1": ut1, "ut2": ut2, "operacao_h": final["h"], "operacao_u": final["U"],
        },
        "froude": {
            "h": h, "liso": [x["Fr"] for x in liso], "rugoso": [x["Fr"] for x in rugoso],
            "operacao_h": final["h"], "operacao_y": final["Fr"],
        },
        "atrito": {
            "h": h, "f_liso": [x["fD"] for x in liso], "f_rugoso": [x["fD"] for x in rugoso],
            "operacao_h": final["h"], "operacao_y": final["fD"],
        },
        "reynolds": {
            "h": h, "re_liso": [x["Re"] for x in liso], "re_rugoso": [x["Re"] for x in rugoso],
            "rec_liso": rec_liso, "rec_rugoso": rec_rugoso,
            "operacao_h": final["h"], "operacao_y": final["Re"],
        },
    }


def montar_apresentacao(dados, resultado):
    final = resultado["final"]
    return {
        "resumo": {
            "vazao": final["Q_m3h"],
            "velocidade": final["U"],
            "altura": final["h"],
            "preenchimento": final["preenchimento"] * 100,
            "froude": final["Fr"],
            "margem_deposicao": resultado["deposicao"]["margem_U_sobre_Ut"],
            "regime_superficie": _(resultado["regime_final"]),
            "superficie_rotulo": {
                "rugosa": _("Superfície rugosa"),
                "lisa": _("Superfície lisa"),
            }.get(resultado["regime_final"], _(resultado["regime_final"])),
            "regime_turbulencia": _(resultado["turbulencia"]["regime"]),
            "geometria": {
                "retangular": _("Retangular"),
                "trapezoidal": _("Trapezoidal"),
                "triangular": _("Triangular"),
                "tubo": _("Tubular"),
            }.get(dados.get("geometria_tipo", dados["geometria"]), "Seção"),
        },
        "avisos": montar_avisos(resultado),
        "tabela_resultados": montar_tabela(dados, resultado),
        "graficos": montar_graficos(dados, resultado),
    }
