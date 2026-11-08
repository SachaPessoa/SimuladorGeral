
"""Núcleo de cálculo do simulador de calha/canal parcialmente cheio.

Extraído da versão Tkinter original e mantido sem dependências de interface.
"""
import math
import numpy as np

def fmt(x, casas=6):
    try:
        return f"{x:.{casas}f}".replace(".", ",")
    except:
        return str(x)
# ============================================================
# 1. BALANÇO DE MASSA
# ============================================================

def balanco_massa_polpa(rhos, rhol, phiw):
    if rhos <= 0 or rhol <= 0:
        raise ValueError("As densidades devem ser maiores que zero.")

    if rhos <= rhol:
        raise ValueError(
            "A densidade dos sólidos deve ser maior que a densidade do líquido.\n\n"
            "Use kg/m³. Exemplo: 4,02 g/cm³ = 4020 kg/m³."
        )

    if not (0 < phiw < 1):
        raise ValueError("A concentração mássica φw deve estar entre 0 e 1. Exemplo: 50% = 0.50.")

    rhom = 1 / (phiw / rhos + (1 - phiw) / rhol)
    phiv = (phiw * rhol) / (phiw * rhol + (1 - phiw) * rhos)
    Vr = phiv / (1 - phiv)

    return {
        "rhom": rhom,
        "phiw": phiw,
        "phiv": phiv,
        "Vr": Vr
    }


# ============================================================
# 2. REOLOGIA
# ============================================================

def reologia_polpa(phiv, Vr, A_lab, B_lab, B_linha_lab, mu_l_Pa_s):
    if not (0 <= phiv < 1):
        raise ValueError("φv deve estar entre 0 e menor que 1.")

    if Vr < 0:
        raise ValueError("Vr não pode ser negativo.")

    if mu_l_Pa_s <= 0:
        raise ValueError("A viscosidade da água deve ser maior que zero.")

    expoente_eta = Vr * B_linha_lab

    if expoente_eta > 50:
        raise ValueError(
            "A viscosidade calculada ficou excessivamente alta.\n\n"
            "Verifique concentração, densidade dos sólidos e unidades."
        )

    # Água: Pa.s -> cP
    mu_l_cP = mu_l_Pa_s * 1000

    # Correlação nativa de laboratório
    tau0_dyn_cm2 = A_lab * (phiv ** B_lab)
    eta_cP = (10 ** expoente_eta) * mu_l_cP

    # Conversões para SI
    tau0_Pa = tau0_dyn_cm2 * 0.1
    eta_Pa_s = eta_cP * 0.001

    return {
        "tau0_dyn_cm2": tau0_dyn_cm2,
        "tau0_Pa": tau0_Pa,
        "eta_cP": eta_cP,
        "eta_Pa_s": eta_Pa_s
    }


# ============================================================
# 3. GEOMETRIA
# ============================================================

def geometria_trapezoidal(b, h, m, hmax):
    if b < 0:
        raise ValueError("b não pode ser negativo.")

    if h <= 0:
        raise ValueError("h deve ser maior que zero.")

    if hmax <= 0:
        raise ValueError("hmax deve ser maior que zero.")

    if h >= hmax:
        raise ValueError("A altura calculada atingiu ou superou hmax.")

    if m < 0:
        raise ValueError("m não pode ser negativo.")

    A = (b + m * h) * h
    P = b + 2 * h * math.sqrt(1 + m**2)

    if P <= 0:
        raise ValueError("Perímetro molhado inválido. Verifique b, h e m.")

    Rh = A / P
    Dh = 4 * Rh
    Btopo = b + 2 * m * h
    preenchimento = h / hmax

    return {
        "theta": None,
        "A": A,
        "P": P,
        "Rh": Rh,
        "Dh": Dh,
        "Btopo": Btopo,
        "preenchimento": preenchimento
    }


def geometria_tubo(D, h):
    if D <= 0:
        raise ValueError("D deve ser maior que zero.")

    if not (0 < h < D):
        raise ValueError("h deve estar entre 0 e D.")

    theta = 2 * math.acos(1 - 2 * h / D)

    A = (D**2 / 8) * (theta - math.sin(theta))
    P = theta * D / 2

    if P <= 0:
        raise ValueError("Perímetro molhado inválido.")

    Rh = A / P
    Dh = 4 * Rh
    Btopo = D * math.sin(theta / 2)
    preenchimento = h / D

    return {
        "theta": theta,
        "A": A,
        "P": P,
        "Rh": Rh,
        "Dh": Dh,
        "Btopo": Btopo,
        "preenchimento": preenchimento
    }


# ============================================================
# 4. ADIMENSIONAIS E ATRITO
# ============================================================

def reynolds(rho, U, Dh, eta):
    return rho * U * Dh / eta


def hedstrom(rho, Dh, tau0, eta):
    return rho * Dh**2 * tau0 / eta**2


def fanning_para_darcy(fF):
    return 4 * fF


def fator_liso(Re, He):
    if Re <= 0:
        raise ValueError("Reynolds inválido.")

    A_liso = -1.47 * (1 + 0.146 * math.exp(-2.9e-5 * He))
    return (10 ** A_liso) * (Re ** -0.193)


def fator_rugoso_wood(Re, Dh, rugosidade, phiw):
    """
    Equação de Wood modificada conforme planilha.

    fD = [
        0,026*erel^0,225
        + 0,133*erel
        + 22*erel^0,44*Re^(-1,62*erel^0,134)*(1 - 0,33*phiw)
    ] * 4

    Esta função retorna fF.
    """

    if Re <= 0:
        raise ValueError("Reynolds inválido.")

    if Dh <= 0:
        raise ValueError("Dh inválido.")

    if rugosidade <= 0:
        raise ValueError("A rugosidade deve ser maior que zero.")

    if not (0 < phiw < 1):
        raise ValueError("φw deve estar entre 0 e 1.")

    erel = rugosidade / Dh

    fF = (
        0.026 * erel**0.225
        + 0.133 * erel
        + (
            22
            * erel**0.44
            * Re**(-1.62 * erel**0.134)
            * (1 - 0.33 * phiw)
        )
    )

    return fF


def subcamada_laminar(Dh, Re, fD):
    if Dh <= 0 or Re <= 0 or fD <= 0:
        raise ValueError("Dh, Re e fD devem ser maiores que zero.")

    return (5 * Dh / Re) * math.sqrt(8 / fD)


# ============================================================
# 5. HIDRÁULICA
# ============================================================

def velocidade_darcy(S, Rh, fD, g=9.81):
    if S <= 0:
        raise ValueError("S deve ser maior que zero. Exemplo: 1% = 0.01.")

    if Rh <= 0:
        raise ValueError("Rh deve ser maior que zero.")

    if fD <= 0:
        raise ValueError("fD deve ser maior que zero.")

    return math.sqrt((8 * g * Rh * S) / fD)


def froude(U, A, Btopo, g=9.81):
    if U <= 0 or A <= 0 or Btopo <= 0:
        raise ValueError("U, A e Btopo devem ser maiores que zero.")

    return U / math.sqrt(g * A / Btopo)


def classificar_froude(Fr):
    if Fr < 1:
        return "subcrítico"
    elif Fr > 1:
        return "supercrítico"
    return "crítico"


def avaliar_froude_polpa(Fr):
    if Fr < 1.5:
        return "baixo para polpa"
    elif Fr > 5:
        return "alto para controle operacional"
    return "adequado"


def avaliar_preenchimento(preenchimento):
    if preenchimento < 0.30:
        return "baixo"
    elif preenchimento > 0.60:
        return "alto"
    return "adequado"


def manning_por_darcy(fD, Rh, g=9.81):
    """
    Coeficiente de Manning equivalente usando fator de Darcy.

    n = sqrt(fD * Rh^(1/3) / (8g))
    """

    if fD <= 0:
        raise ValueError("fD deve ser maior que zero.")

    if Rh <= 0:
        raise ValueError("Rh deve ser maior que zero.")

    return math.sqrt((fD * Rh**(1 / 3)) / (8 * g))


# ============================================================
# 6. VELOCIDADE DE DEPOSIÇÃO / MÍNIMA
# ============================================================

def velocidade_deposicao_abulnaga_1(Rh, rhos, rhom, d85, g=9.81):
    """
    Ut1 = 1,833 * sqrt(8*g*Rh*(rhos-rhom)/rhom) * (d85/Rh)^0,158
    """

    if Rh <= 0:
        raise ValueError("Rh deve ser maior que zero para Ut1.")

    if rhos <= rhom:
        raise ValueError("ρs deve ser maior que ρm para Ut1.")

    if d85 <= 0:
        raise ValueError("d85 deve ser maior que zero.")

    return 1.833 * math.sqrt(
        8 * g * Rh * (rhos - rhom) / rhom
    ) * (d85 / Rh) ** 0.158


def velocidade_deposicao_green(dp, rhos, rhom, fD, Ke=0.8, g=9.81):
    """
    Equação Green / Abulnaga com fator 2.

    Ut2_base = sqrt((8*Ke/fD) * dp*g * ((rhos-rhom)/rhom))
    Ut2 = 2 * Ut2_base
    """

    if dp <= 0:
        raise ValueError("dp deve ser maior que zero.")

    if rhos <= rhom:
        raise ValueError("ρs deve ser maior que ρm para Ut2.")

    if fD <= 0:
        raise ValueError("fD deve ser maior que zero para Ut2.")

    Ut2_base = math.sqrt(
        (8 * Ke / fD) * dp * g * ((rhos - rhom) / rhom)
    )

    Ut2 = 2 * Ut2_base

    return Ut2, Ut2_base


def avaliar_deposicao(U, Ut1, Ut2):
    Ut_ref = max(Ut1, Ut2)

    if U >= Ut_ref:
        classificacao = "homogêneo"
        mensagem = "Velocidade média acima da velocidade mínima de deposição."
    else:
        classificacao = "heterogêneo"
        mensagem = "Velocidade média abaixo da velocidade mínima. Condição indesejada."

    return {
        "Ut1": Ut1,
        "Ut2": Ut2,
        "Ut_ref": Ut_ref,
        "classificacao": classificacao,
        "mensagem": mensagem,
        "margem_U_sobre_Ut": U / Ut_ref
    }


# ============================================================
# 7. REYNOLDS CRÍTICO / REGIME TURBULENTO
# ============================================================

def resolver_phi_c(He, denominador, tolerancia=1e-10, max_iter=200):
    """
    Resolve:
        phi_c / (1 - phi_c)^3 = He / denominador
    """

    if He <= 0:
        raise ValueError("He deve ser maior que zero.")

    alvo = He / denominador

    phi_min = 1e-12
    phi_max = 1 - 1e-12

    for _ in range(max_iter):
        phi_mid = (phi_min + phi_max) / 2
        valor = phi_mid / ((1 - phi_mid) ** 3)
        erro = valor - alvo

        if abs(erro) < tolerancia:
            return phi_mid

        if erro > 0:
            phi_max = phi_mid
        else:
            phi_min = phi_mid

    return phi_mid


def reynolds_critico_naik(He):
    phi_c = resolver_phi_c(He, denominador=48000)

    Rec = (He / (12 * phi_c)) * (
        1 - 1.5 * phi_c + 0.5 * phi_c**3
    )

    return Rec, phi_c


def reynolds_critico_hanks(He):
    phi_c = resolver_phi_c(He, denominador=16800)

    Rec = He * (
        1 - (4 / 3) * phi_c + (phi_c**3) / 3
    ) / (8 * phi_c)

    return Rec, phi_c


def reynolds_critico_durand(He, ReTN=4000):
    if He <= 0:
        raise ValueError("He deve ser maior que zero.")

    if ReTN <= 0:
        raise ValueError("ReTN deve ser maior que zero.")

    Rec = (ReTN / 2) * (
        1 + math.sqrt(1 + (2 * He) / (3 * ReTN))
    )

    return Rec


def avaliar_regime_turbulento(Re_sistema, He):
    Rec_naik, phi_naik = reynolds_critico_naik(He)
    Rec_hanks, phi_hanks = reynolds_critico_hanks(He)
    Rec_durand = reynolds_critico_durand(He)

    Rec_ref = max(Rec_naik, Rec_hanks, Rec_durand)

    if Re_sistema > Rec_ref:
        regime = "turbulento"
        mensagem = "Reynolds do sistema acima do Reynolds crítico de referência."
    else:
        regime = "laminar/transicional"
        mensagem = "Reynolds do sistema abaixo do Reynolds crítico de referência. Condição indesejada."

    return {
        "Rec_naik": Rec_naik,
        "phi_c_naik": phi_naik,
        "Rec_hanks": Rec_hanks,
        "phi_c_hanks": phi_hanks,
        "Rec_durand": Rec_durand,
        "Rec_ref": Rec_ref,
        "Re_sistema": Re_sistema,
        "regime": regime,
        "mensagem": mensagem,
        "margem_Re_sobre_Rec": Re_sistema / Rec_ref
    }


# ============================================================
# 8. CÁLCULO PARA UM h
# ============================================================

def calcular_para_h(h, regime, dados):
    if dados["geometria"] == "trapezoidal":
        geom = geometria_trapezoidal(
            dados["b"],
            h,
            dados["m"],
            dados["hmax"]
        )
    else:
        geom = geometria_tubo(
            dados["D"],
            h
        )

    Rh = geom["Rh"]
    Dh = geom["Dh"]
    A = geom["A"]
    Btopo = geom["Btopo"]

    U = 0.1

    for _ in range(100):
        Re = reynolds(dados["rhom"], U, Dh, dados["eta_Pa_s"])
        He = hedstrom(dados["rhom"], Dh, dados["tau0_Pa"], dados["eta_Pa_s"])

        if regime == "liso":
            fF = fator_liso(Re, He)
        else:
            fF = fator_rugoso_wood(Re, Dh, dados["rugosidade"], dados["phiw"])

        fD = fanning_para_darcy(fF)
        U_novo = velocidade_darcy(dados["S"], Rh, fD)

        if abs(U_novo - U) < 1e-7:
            U = U_novo
            break

        U = U_novo

    Q_m3s = U * A
    Q_m3h = Q_m3s * 3600
    Fr = froude(U, A, Btopo)

    return {
        **geom,
        "h": h,
        "U": U,
        "Q_m3h": Q_m3h,
        "Re": Re,
        "He": He,
        "fF": fF,
        "fD": fD,
        "Fr": Fr,
        "classificacao_Fr": classificar_froude(Fr),
        "avaliacao_Fr_polpa": avaliar_froude_polpa(Fr),
        "avaliacao_preenchimento": avaliar_preenchimento(geom["preenchimento"])
    }


# ============================================================
# 9. SOLVER DE h POR BISSEÇÃO
# ============================================================

def resolver_altura(regime, dados):
    Qreq = dados["Qreq_m3h"]

    if Qreq <= 0:
        raise ValueError("A vazão requerida deve ser maior que zero.")

    if dados["geometria"] == "trapezoidal":
        h_min = dados["hmax"] * 0.001
        h_max = dados["hmax"] * 0.999
    else:
        h_min = dados["D"] * 0.001
        h_max = dados["D"] * 0.999

    res_max = calcular_para_h(h_max, regime, dados)

    if res_max["Q_m3h"] < Qreq:
        raise ValueError(
            f"A geometria não atinge a vazão requerida no regime {regime}.\n\n"
            f"Q máxima calculada = {res_max['Q_m3h']:.3f} m³/h\n"
            f"Q requerida = {Qreq:.3f} m³/h"
        )

    for _ in range(200):
        h_mid = (h_min + h_max) / 2
        res_mid = calcular_para_h(h_mid, regime, dados)

        erro = res_mid["Q_m3h"] - Qreq

        if abs(erro) < 0.0001:
            return res_mid

        if erro > 0:
            h_max = h_mid
        else:
            h_min = h_mid

    return res_mid


# ============================================================
# 10. CÁLCULO PRINCIPAL
# ============================================================

def calcular_modelo(dados):
    massa = balanco_massa_polpa(
        dados["rhos"],
        dados["rhol"],
        dados["phiw"]
    )

    reol = reologia_polpa(
        massa["phiv"],
        massa["Vr"],
        dados["A_lab"],
        dados["B_lab"],
        dados["B_linha_lab"],
        dados["mu_l_Pa_s"]
    )

    dados_calc = {
        **dados,
        **massa,
        **reol
    }

    resultado_liso = resolver_altura("liso", dados_calc)
    resultado_rugoso = resolver_altura("rugoso", dados_calc)

    delta_v = subcamada_laminar(
        resultado_rugoso["Dh"],
        resultado_rugoso["Re"],
        resultado_rugoso["fD"]
    )

    if delta_v > dados["rugosidade"]:
        regime_final = "liso"
        resultado_final = resultado_liso
    else:
        regime_final = "rugoso"
        resultado_final = resultado_rugoso

    Ut1 = velocidade_deposicao_abulnaga_1(
        Rh=resultado_final["Rh"],
        rhos=dados["rhos"],
        rhom=massa["rhom"],
        d85=dados["d85"]
    )

    Ut2, Ut2_base = velocidade_deposicao_green(
        dp=dados["dp"],
        rhos=dados["rhos"],
        rhom=massa["rhom"],
        fD=resultado_final["fD"]
    )

    deposicao = avaliar_deposicao(
        U=resultado_final["U"],
        Ut1=Ut1,
        Ut2=Ut2
    )

    turbulencia = avaliar_regime_turbulento(
        Re_sistema=resultado_final["Re"],
        He=resultado_final["He"]
    )

    n_manning = manning_por_darcy(
        fD=resultado_final["fD"],
        Rh=resultado_final["Rh"]
    )

    return {
        "massa": massa,
        "reologia": reol,
        "liso": resultado_liso,
        "rugoso": resultado_rugoso,
        "delta_v": delta_v,
        "regime_final": regime_final,
        "final": resultado_final,
        "deposicao": deposicao,
        "Ut2_base": Ut2_base,
        "turbulencia": turbulencia,
        "n_manning": n_manning
    }


# ============================================================
# 11. INTERFACE TKINTER
# ============================================================
