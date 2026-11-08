import math
import numpy as np
import pandas as pd
from django.utils.translation import gettext as _

def Bingfric(Re, He, eD=0.0, Resp=0):
    """
    Fator de atrito para fluido Bingham.

    Entradas:
        Re: Reynolds (-)
        He: Hedstrom (-)
        eD: rugosidade relativa epsilon/D [-]
        Resp:
            0 = fator combinado
            1 = fator laminar
            2 = fator turbulento
            3 = Re
            4 = He
            5 = fator_rug
            6 = convergiu_laminar
    """

    # -----------------------------
    # Proteções básicas
    # -----------------------------
    if Re <= 0 or not np.isfinite(Re):
        return np.nan

    if He < 0 or not np.isfinite(He):
        He = 0.0

    if eD < 0 or not np.isfinite(eD):
        eD = 0.0

    # -----------------------------
    # Cálculo laminar Bingham
    # -----------------------------
    # Equação:
    # F = (16/Re) * [1 + He/(6Re) - He^4/(3 F^3 Re^7)]
    #
    # Forma residual:
    # g(F) = -F + (16/Re)*(1 + He/(6Re) - He^4/(3 F^3 Re^7)) = 0

    # Chute inicial mais estável que F0 = 5
    fl_newtoniano = 16.0 / Re
    fl_aprox = fl_newtoniano * (1.0 + He / (6.0 * Re))

    F = max(fl_aprox, 1e-8)

    tol = 1e-8
    max_iter = 50
    convergiu = False

    for _ in range(max_iter):

        F = max(F, 1e-12)

        termo_base = 1.0 + He / (6.0 * Re)
        termo_bingham = (He ** 4) / (3.0 * (F ** 3) * (Re ** 7))

        g = -F + (16.0 / Re) * (termo_base - termo_bingham)

        # Derivada analítica de g(F)
        # d/dF[-F] = -1
        # d/dF[-C/F^3] = +3C/F^4
        dg = -1.0 + (16.0 / Re) * ((He ** 4) / ((F ** 4) * (Re ** 7)))

        if abs(dg) < 1e-30 or not np.isfinite(dg):
            break

        F_new = F - g / dg

        # Proteção contra passo ruim
        if not np.isfinite(F_new) or F_new <= 0:
            F_new = 0.5 * F

        # Amortecimento se o salto for exagerado
        if F_new > 10.0 * F:
            F_new = 10.0 * F
        elif F_new < 0.1 * F:
            F_new = 0.1 * F

        erro = abs(F_new - F)

        F = F_new

        if erro < tol:
            convergiu = True
            break

    fl = max(F, 1e-12)

    # Fallback de segurança
    # Se por algum motivo o Newton produzir algo absurdo, usa aproximação laminar simples.
    if not np.isfinite(fl) or fl <= 0:
        fl = max(fl_aprox, 16.0 / Re, 1e-12)
        convergiu = False

    # -----------------------------
    # Fator turbulento Bingham
    # -----------------------------
    A = -1.378 * (1.0 + 0.146 * np.exp(-0.000029 * He))

    ft_liso = (10.0 ** A) * (Re ** (-0.193))

    if not np.isfinite(ft_liso) or ft_liso <= 0:
        ft_liso = 0.001

    # Rugosidade aplicada somente no turbulento
    fator_rug = fator_rugosidade_newtoniano(Re, eD)

    if not np.isfinite(fator_rug) or fator_rug <= 0:
        fator_rug = 1.0

    ft = ft_liso * fator_rug

    # -----------------------------
    # Combinação laminar/turbulento
    # -----------------------------
    m = 1.7 + (40000.0 / Re)

    # Proteção contra overflow em fl**m e ft**m
    if m > 100:
        # Para Re muito baixo, o maior termo domina.
        # Como m alto aproxima max(fl, ft), usa forma segura.
        f_comb = max(fl, ft)
    else:
        f_comb = ((fl ** m) + (ft ** m)) ** (1.0 / m)

    if not np.isfinite(f_comb) or f_comb <= 0:
        f_comb = max(fl, ft, 1e-12)

    # -----------------------------
    # Respostas
    # -----------------------------
    if Resp == 0:
        return f_comb
    elif Resp == 1:
        return fl
    elif Resp == 2:
        return ft
    elif Resp == 3:
        return Re
    elif Resp == 4:
        return He
    elif Resp == 5:
        return fator_rug
    elif Resp == 6:
        return convergiu
    else:
        return f_comb
# ===========================================================
# Função Bingtrans: Transição Bingham
# -----------------------------------------------------------
# Calcula a velocidade crítica Uc, número de Reynolds Re ou número de Hedstrom He
# para fluidos tipo Bingham em transição.
# Equações:
#   He = D^2 * Tau0 * Ros / Eta^2
#   Re = (Retn/2) * (1 + sqrt(1 + 2*He/(3*Retn)))
#   Uc = Re * Eta / (D * Ros)
# Entradas:
#   D: diâmetro interno do tubo (m)
#   Ros: densidade da suspensão (kg/m³)
#   Tau0: limite de escoamento (Pa)
#   Eta: viscosidade plástica (Pa.s)
#   Retn: número de Reynolds de transição (-)
#   Resp: 0=Uc, 1=Re, 2=He
# Saída: Uc, Re ou He conforme Resp
# ===========================================================
def Bingtrans(D, Ros, Tau0, Eta, Retn, Resp=0):
    """
    Calcula a velocidade crítica Uc, número de Reynolds Re ou número de Hedstrom He para fluidos tipo Bingham em transição.
    Entradas:
        D: diâmetro interno do tubo (m)
        Ros: densidade da suspensão (kg/m³)
        Tau0: limite de escoamento (Pa)
        Eta: viscosidade plástica (Pa.s)
        Retn: número de Reynolds de transição (-)
        Resp: 0=Uc, 1=Re, 2=He
    """
    # Número de Hedstrom
    He = (D ** 2) * Tau0 * Ros / (Eta ** 2)
    # Número de Reynolds efetivo para transição
    Re = (Retn / 2) * (1 + (1 + (2 * He / (3 * Retn))) ** 0.5)
    # Velocidade crítica
    Uc = Re * Eta / (D * Ros)
    if Resp == 0:
        return Uc
    elif Resp == 1:
        return Re
    elif Resp == 2:
        return He
    else:
        return Uc
#=========================================================
#FUNÇÃO: Bingtrans
#OBJETIVO: Alternativa para cálculo de Uc, Re ou He para fluidos tipo Bingham
#BASE: Swamee & Aggarwal (2011) - conforme Pessoa (2018), Seção 5.1.2.1, Equação 5.49
#ENTRADAS: D (pol), Ros (kg/m³), tau0 (dyn/cm²), Eta (cP), Retn (-), resp (0,1,2)
#UNIDADES AJUSTADAS: D para m, tau0 para Pa, Eta para Pa.s
#==========================================================
def Bingtrans2(D, Ros, Tau0, Eta, Resp):
    """
    Alternativa para cálculo de Uc, Re ou He para fluidos tipo Bingham (Swamee & Aggarwal, 2011).
    Entradas:    
        D: diâmetro interno do tubo (pol)
        Ros: densidade da suspensão (kg/m³)
        Tau0: limite de escoamento (Pa)
        Eta: viscosidade plástica (Pa.s)
        Resp: 0=Uc, 1=Re, 2=He
    """
    D = D * 0.0254
    Tau0 = Tau0 * 0.1
    Eta = Eta * 0.001
    He = (D ** 2) * Tau0 * Ros / (Eta ** 2)
    if He < 1e8:
        Re = 2100 * ((1 + (He / 3600)) ** 0.35)
    else:
        Re = 161 * (He ** 0.334)
    Uc = Re * Eta / (D * Ros)
    if Resp == 0:
        return Uc
    elif Resp == 1:
        return Re
    elif Resp == 2:
        return He

# ===========================================================
# Função velterminal_levenspiel: Velocidade terminal de partícula
# -----------------------------------------------------------
# Calcula a velocidade terminal de uma partícula esférica em fluido newtoniano,
# método iterativo de Newton-Raphson, baseado em Levenspiel (1986) e Wasp (1977).
# Equação de equilíbrio de forças:
#   -((4*g*Dp*(Ros-Rol))/(3*Rol*Ut^2)) + (24/Re)*(1+0.173*Re^0.657) + 0.413/(1+16300*Re^-1.09) = 0
# Entradas:
#   Dp: diâmetro da partícula (m)
#   Ros: densidade da partícula (kg/m³)
#   Rol: densidade do fluido (kg/m³)
#   Mil: viscosidade do fluido (Pa.s)
# Saída: Ut (m/s)
# ===========================================================
def velterminal_levenspiel(Dp, Ros, Rol, Mil):
    """
    Velocidade terminal (Levenspiel) robusta para qualquer viscosidade.
    Parâmetros em SI: Dp [m], Ros/Rol [kg/m³], Mil [Pa.s]
    Retorna Ut [m/s]
    """
    import math

    g = 9.81
    # Correl. de Cd (a mesma que você usa: "composta" tipo Levenspiel)
    def _Cd_from_Re(Re):
        # piso para evitar estouro em potências
        Re_min = 1e-12
        Re = max(Re, Re_min)
        return ((24.0 / Re) * (1.0 + 0.173 * (Re ** 0.657))
                + 0.413 / (1.0 + 16300.0 * (Re ** -1.09)))

    # Equilíbrio de forças escrito como F(Ut) = 0:
    # F = Cd(Re)* (3/4)*(Rol*Ut^2)/(Dp*(Ros-Rol)) - g
    # (equivalente à sua forma; muda só a organização)
    def F(Ut):
        if Ut <= 0.0:
            return float("inf")  # impede Ut <= 0 em Newton/bisseção
        Re = (Dp * Ut * Rol) / Mil
        Cd = _Cd_from_Re(Re)
        return (Cd * (3.0/4.0) * (Rol * Ut * Ut) / (Dp * (Ros - Rol))) - g

    # Derivada numérica estável (para Newton amortecido)
    def dF(Ut):
        h = max(1e-8, 1e-6 * Ut)
        f1 = F(Ut)
        f2 = F(Ut + h)
        return (f2 - f1) / h

    # --- CHUTES E LIMITES FÍSICOS ---
    # Stokes (Re << 1) como chute baixo
    Ut_stokes = ( (Ros - Rol) * g * (Dp ** 2) ) / (18.0 * Mil )
    Ut_lo = max(1e-10, 0.25 * Ut_stokes)  # >0
    # Limite alto com Cd≈0.44 (regime inercial) como “pior caso”
    # Ut ≈ sqrt( (4/3) * g * Dp * (Δρ/Rol) / Cd )
    try:
        Ut_hi = math.sqrt( (4.0/3.0) * g * Dp * ((Ros - Rol)/Rol) / 0.44 )
    except ValueError:
        Ut_hi = max(10.0 * Ut_stokes, 1e-6)

    # Garante Ut_hi > Ut_lo
    if not (Ut_hi > Ut_lo):
        Ut_hi = Ut_lo * 100.0

    # Verifica mudança de sinal e tenta bisseção robusta
    f_lo = F(Ut_lo)
    f_hi = F(Ut_hi)

    # Se não há mudança de sinal, *amplia* o intervalo algumas vezes
    expand_tries = 0
    while (f_lo * f_hi > 0.0) and (expand_tries < 6):
        Ut_lo *= 0.5
        Ut_hi *= 2.0
        f_lo = F(Ut_lo)
        f_hi = F(Ut_hi)
        expand_tries += 1

    # --- Bisseção se houver mudança de sinal ---
    if f_lo * f_hi <= 0.0:
        a, b = Ut_lo, Ut_hi
        for _ in range(80):
            c = 0.5 * (a + b)
            fc = F(c)
            if abs(fc) < 1e-12 or (b - a) < 1e-12:
                return c
            if f_lo * fc <= 0.0:
                b = c
                f_hi = fc
            else:
                a = c
                f_lo = fc
        return 0.5 * (a + b)

    # --- Caso não haja mudança de sinal: Newton amortecido com *clamp* ---
    Ut = max(Ut_stokes, 1e-9)
    for _ in range(80):
        f = F(Ut)
        if not math.isfinite(f):
            Ut = max(1e-9, min(Ut_hi, max(Ut_lo, Ut_stokes)))
            continue
        if abs(f) < 1e-12:
            return Ut
        df = dF(Ut)
        if not math.isfinite(df) or df == 0.0:
            # passo pequeno para o lado do menor |F|
            Ut_try = Ut * 1.1
            if abs(F(Ut_try)) >= abs(f):
                Ut_try = Ut * 0.9
            Ut = max(Ut_lo, min(Ut_hi, Ut_try))
            continue
        # passo de Newton com amortecimento
        step = -f / df
        lam = 1.0
        for _inner in range(12):
            Ut_new = Ut + lam * step
            if Ut_new <= Ut_lo or Ut_new >= Ut_hi or not math.isfinite(Ut_new):
                lam *= 0.5
                continue
            if abs(F(Ut_new)) < abs(f):
                Ut = Ut_new
                break
            lam *= 0.5
        else:
            # não melhorou: dá um passo conservador
            Ut = max(Ut_lo, min(Ut_hi, Ut * 0.9))
    return Ut

# ===========================================================
# Função Powertrans: Velocidade crítica, Re modificado ou Re típico para Power Law
# -----------------------------------------------------------
# OBJETIVO: Cálculo da velocidade crítica Uc, Re modificado ou Re típico para fluidos Power Law
# BASE: Ryan & Johnson (1959) - conforme Pessoa (2018), Seção 5.1.2.2, Equação 5.50
# ENTRADAS: u (m/s), D (pol), Ros (kg/m³), Mis (cP), n (-), resp
# ===========================================================
def Powertrans(u, D, Ros, Mis, n, resp):
    """
    Cálculo da velocidade crítica Uc, Re modificado ou Re típico para fluidos Power Law.
    BASE: Ryan & Johnson (1959) - Pessoa (2018), Eq. 5.50
    ENTRADAS:
        u: velocidade média (m/s)
        D: diâmetro do tubo (pol)
        Ros: densidade da suspensão (kg/m³)
        Mis: viscosidade aparente (cP)
        n: índice de comportamento (-)
        resp: 0=Uc, 1=Ret, 2=Re
    """
    D = D * 0.0254
    Mis = Mis * 0.001
    Ret = (6464 * n * ((n + 2) ** ((n + 2) / (n + 1)))) / ((1 + 3 * n) ** 2)
    Re = ((D * u * Ros) / Mis) * ((4 * n / (3 * n + 1)) ** n) * ((D / (8 * u)) ** (n - 1))
    Uc = ((((Mis * (((0.75 + (0.25 / n))) ** n)) * (8 ** (n - 1)) * Ret)) / (((D) ** n * Ros))) ** (1 / (2 - n))
    if resp == 0:
        return Uc
    elif resp == 1:
        return Ret
    elif resp == 2:
        return Re

# ===========================================================
# Função Newtoniano: Fator de atrito para fluidos Newtonianos
# -----------------------------------------------------------
# OBJETIVO: Cálculo do fator de atrito para fluidos Newtonianos
# BASE:
# - Laminar: Hagen-Poiseuille (f = 16/Re) - Pessoa (2018), Seção 5.1.1
# - Transição: correlação empírica de ajuste
# - Turbulento: Colebrook-White (1939) - Pessoa (2018), Seção 5.1.3.1
# ENTRADAS: Re (-), eD (rugosidade relativa)
# ===========================================================
def Newtoniano(Re, eD):
    """
    Cálculo do fator de atrito para fluidos Newtonianos.
    ENTRADAS:
        Re: número de Reynolds (-)
        eD: rugosidade relativa
    """
    import numpy as np
    if Re <= 2000:
        f = 16 / Re
    elif Re > 2000 and Re <= 4000:
        f = 0.0008 + (0.0553 / (Re ** 0.237))
    else:
        # Colebrook-White (iterativo)
        F0 = (0.3164 / 4) * Re ** (-0.25)
        erro = 1
        while erro >= 1e-12:
            func = 1 / (F0 ** 0.5) + 4 * np.log10(eD / 3.72 + 1.256 / (Re * (F0 ** 0.5)))
            dfunc = (-1.256 * 2) / (np.log(10) * F0 ** (3 / 2) * Re * (eD / 3.72 + 1.256 / (Re * (F0 ** 0.5)))) - 1 / (2 * F0 ** (3 / 2))
            f_new = F0 - func / dfunc
            erro = abs(F0 - f_new)
            F0 = f_new
        f = f_new
    return f

# ===========================================================
# Função Powerfric: Fator de atrito para fluidos Power Law
# -----------------------------------------------------------
# OBJETIVO: Cálculo do fator de atrito para fluidos do tipo Power Law
# BASE:
# - Laminar: Heywood (1991) - Pessoa (2018), Seção 5.1.1.2
# - Turbulento: Dodge & Metzner (1959) - Pessoa (2018), Seção 5.1.3.2
# ENTRADAS: Re (-), n (índice de comportamento), resp (0-3)
# ===========================================================
# ===========================================================
# Função auxiliar: fator_rugosidade_newtoniano
# -----------------------------------------------------------
# Calcula o fator de correção de rugosidade baseado na razão:
# f_newtoniano_rugoso / f_newtoniano_liso
# ===========================================================
def fator_rugosidade_newtoniano(Re, eD):
    """
    Fator multiplicador de correção de rugosidade baseado na razão:
        f_newtoniano_rugoso / f_newtoniano_liso

    ENTRADAS:
        Re: número de Reynolds (-)
        eD: rugosidade relativa epsilon/D [-]

    SAÍDA:
        fator adimensional >= 1 aproximadamente
    """
    if eD <= 0:
        return 1.0
    
    if Re <= 0:
        return 1.0
    
    f_liso = Newtoniano(Re, 0.0)
    f_rugoso = Newtoniano(Re, eD)
    
    if f_liso <= 0:
        return 1.0
    
    return f_rugoso / f_liso

# ===========================================================
# Função Powerfric: Fator de atrito para fluidos Power Law
# -----------------------------------------------------------
# OBJETIVO: Cálculo do fator de atrito para fluidos do tipo Power Law
# BASE:
# - Laminar: Heywood (1991) - Pessoa (2018), Seção 5.1.1.2
# - Turbulento: Dodge & Metzner (1959) - Pessoa (2018), Seção 5.1.3.2
# ENTRADAS: Re (-), n (índice de comportamento), eD (rugosidade relativa), resp (0-5)
# ===========================================================
def Powerfric(Re, n, eD=0.0, resp=0):
    """
    Cálculo do fator de atrito para fluidos do tipo Power Law.
    ENTRADAS:
        Re: número de Reynolds (-)
        n: índice de comportamento
        eD: rugosidade relativa epsilon/D [-]
        resp: 0=f, 1=Ret, 2=ft, 3=Re, 4=fl, 5=fator_rug
    """
    Ret = (6464 * n * ((n + 2) ** ((n + 2) / (n + 1)))) / ((1 + 3 * n) ** 2)
    F0 = 0.0001
    h = 1e-10
    erro = 0.5
    import numpy as np
    while erro >= 1e-9:
        func = -(1 / (F0 ** 0.5)) - (0.4 / (n ** 1.2)) + (4 / (n ** 0.75)) * (np.log10(Re * (F0 ** ((2 - n) / 2))))
        T0 = func
        T = -(1 / ((F0 + h) ** 0.5)) - (0.4 / (n ** 1.2)) + (4 / (n ** 0.75)) * (np.log10(Re * ((F0 + h) ** ((2 - n) / 2))))
        dfunc = (T - T0) / h
        f = F0 - func / dfunc
        erro = abs(F0 - f)
        F0 = f
    ft_liso = f
    
    # Aplicar fator de correção de rugosidade apenas na parcela turbulenta
    fator_rug = fator_rugosidade_newtoniano(Re, eD)
    ft = ft_liso * fator_rug
    
    fl = 16 / Re
    if Re >= Ret:
        f = ft
    else:
        f = fl
    if resp == 0:
        return f
    elif resp == 1:
        return Ret
    elif resp == 2:
        return ft
    elif resp == 3:
        return Re
    elif resp == 4:
        return fl
    elif resp == 5:
        return fator_rug

# ===========================================================
# Função GeneralizedRe: Número de Reynolds generalizado para não-newtonianos
# -----------------------------------------------------------
# OBJETIVO: Número de Reynolds generalizado para fluidos não-newtonianos
# BASE: K. Madlener, B. Frey, and H. K. Ciezki 2009, Progress in Propulsion Physics 1(2009) 237-250
# ENTRADAS: Tau0 (Pa), K (Pa.s), n (-), Ro (kg/m³), D (m), u (m/s), resp
# ===========================================================
def GeneralizedRe(Tau0, K, n, Ro, D, u, resp):
    """
    Número de Reynolds generalizado para fluidos não-newtonianos Herschel-Bulkley.
    ENTRADAS:
        Tau0: tensão de escoamento (Pa)
        K: viscosidade HB (Pa.s)
        n: fator reológico HB (-)
        Ro: densidade polpa (kg/m³)
        D: diâmetro interno (m)
        u: velocidade média (m/s)
        resp: 0=f, 1=ReG
    """
    A = Ro * (u ** (2 - n)) * D ** n
    B = Tau0 / 8
    C = (D / u) ** n
    E = ((8 * u) / D) ** n
    mm = n * K * E / (Tau0 + (K * E))
    G = (((3 * mm) + 1) / (4 * mm)) ** n
    h = 8 ** (n - 1)
    ReG = A / (B * C + (K * G * h))
    f = 16 / ReG
    #ft = (1 / ((1.767 * (np.log10(ReG / 0.002))) + 6 - (2.65 / n))) ** 2
    #m = 1.7 + (40000 / ReG)
    #f = ((fl ** m) + (ft ** m)) ** (1 / m)
    if resp == 0:
        return f
    elif resp == 1:
        return ReG
# =============================================
# FUNÇÃO: Herschfric
# OBJETIVO: Cálculo do fator de atrito para fluidos do tipo Herschel-Bulkley
# BASE:
# - Laminar: Malin (1998) - conforme Pessoa (2018), Seção 5.1.1.3
# - Turbulento: Torrance (1963) - conforme Pessoa (2018), Seção 5.1.3.3
# - Combinação Laminar-Turbulento: Churchill-Darby (1992) - conforme Pessoa (2018)
# ENTRADAS: Re (-), He (-), n (-), eD (rugosidade relativa), Resp (0-6)
# UNIDADES: adimensionais
# ============================================

def Herschfric(Re, He, n, eD=0.0, Resp=0):
    """
    Fator de atrito para fluidos Herschel-Bulkley.
    Malin (1998), Torrance (1963), Churchill-Darby (1992)

    Entradas:
        Re: Reynolds (-)
        He: Hedstrom (-)
        n: índice de comportamento (-)
        eD: rugosidade relativa epsilon/D [-]

    Resp:
        0 = f combinado
        1 = ft turbulento
        2 = fl laminar
        3 = T2
        4 = T1
        5 = x0
        6 = convergiu
    """

    # -----------------------------
    # Proteções básicas
    # -----------------------------
    if Re <= 0 or not np.isfinite(Re):
        return np.nan

    if He < 0 or not np.isfinite(He):
        He = 0.0

    if n <= 0 or not np.isfinite(n):
        n = 1.0

    if eD < 0 or not np.isfinite(eD):
        eD = 0.0

    # -----------------------------
    # Funções auxiliares
    # -----------------------------
    def calcula_psi(x):
        x = min(max(x, 1e-10), 0.999999)

        A = (1.0 - x) ** (n + 1.0)
        B = ((1.0 - x) ** 2.0) / (1.0 + 3.0 * n)
        C = (2.0 * x * (1.0 - x)) / (1.0 + 2.0 * n)
        D = (x ** 2.0) / (1.0 + n)

        psi = ((1.0 + 3.0 * n) ** n) * A * ((B + C + D) ** n)

        if not np.isfinite(psi) or psi <= 0:
            psi = 1e-12

        return psi

    def calcula_T(x):
        x = min(max(x, 1e-10), 0.999999)
        psi = calcula_psi(x)

        T = (
            -Re
            + (0.0625 * np.exp(2.085 * n))
            * He
            * ((n / (1.0 + 3.0 * n)) ** n)
            * ((psi / x) ** ((2.0 - n) / n))
        )

        return T

    # -----------------------------
    # Resolver x0 com Newton amortecido
    # -----------------------------
    x0 = 1e-6
    tol = 1e-10
    max_iter = 50
    convergiu = False

    T1 = calcula_T(x0)
    T2 = T1

    for _ in range(max_iter):
        h = max(1e-7, abs(x0) * 1e-5)

        T1 = calcula_T(x0)
        T2 = calcula_T(x0 + h)

        dfunc = (T2 - T1) / h

        if not np.isfinite(dfunc) or abs(dfunc) < 1e-30:
            break

        x = x0 - T1 / dfunc

        # Limite físico do plug ratio
        x = min(max(x, 1e-10), 0.999999)

        # Amortecimento para evitar salto excessivo
        if x > x0 * 10.0 and x0 > 0:
            x = x0 * 10.0
        elif x < x0 * 0.1:
            x = x0 * 0.1

        erro = abs(x - x0)
        x0 = x

        if erro < tol:
            convergiu = True
            break

    # Recalcular Psi final depois da convergência
    Psi0 = calcula_psi(x0)

    fl = 16.0 / (Re * Psi0)

    if not np.isfinite(fl) or fl <= 0:
        fl = 16.0 / Re

    # -----------------------------
    # Fator turbulento Dodge-Metzner
    # -----------------------------
    F0 = 0.0001
    h = 1e-10
    erro = 0.5

    while erro >= 1e-9:
        func = -(1 / (F0 ** 0.5)) - (0.4 / (n ** 1.2)) + (4 / (n ** 0.75)) * (np.log10(Re * (F0 ** ((2 - n) / 2))))
        T0_dm = func
        T_dm = -(1 / ((F0 + h) ** 0.5)) - (0.4 / (n ** 1.2)) + (4 / (n ** 0.75)) * (np.log10(Re * ((F0 + h) ** ((2 - n) / 2))))
        dfunc = (T_dm - T0_dm) / h
        ft_liso = F0 - func / dfunc
        erro = abs(F0 - ft_liso)
        F0 = ft_liso

    fator_rug = fator_rugosidade_newtoniano(Re, eD)
    ft = ft_liso * fator_rug

    # Equação turbulenta anterior de Torrance, mantida inativa como histórico:
    # 1/sqrt(f) = 1.767*log10(Re/eD) + 6 - 2.65/n
    #
    # if eD > 0:
    #     denom = (1.767 * np.log10(Re / eD)) + 6.0 - (2.65 / n)
    #     ft = (1.0 / denom) ** 2
    # else:
    #     eD_eff = 1e-6
    #     denom = (1.767 * np.log10(Re / eD_eff)) + 6.0 - (2.65 / n)
    #     ft = (1.0 / denom) ** 2

    if not np.isfinite(ft) or ft <= 0:
        ft = 0.001

    # -----------------------------
    # Combinação Churchill-Darby
    # -----------------------------
    m = 1.7 + (40000.0 / Re)

    # Proteção contra overflow em fl**m e ft**m
    if m > 100:
        f = max(fl, ft)
    else:
        f = ((fl ** m) + (ft ** m)) ** (1.0 / m)

    if not np.isfinite(f) or f <= 0:
        f = max(fl, ft, 1e-12)

    # -----------------------------
    # Retornos
    # -----------------------------
    if Resp == 0:
        return f
    elif Resp == 1:
        return ft
    elif Resp == 2:
        return fl
    elif Resp == 3:
        return T2
    elif Resp == 4:
        return T1
    elif Resp == 5:
        return x0
    elif Resp == 6:
        return convergiu
    else:
        return f
# =============================================
# FUNÇÃO: Herschfric2
# OBJETIVO: Cálculo do fator de atrito para fluidos do tipo Herschel-Bulkley
# BASE:
# - Laminar: Chilton & Stainsby (1998) - conforme Pessoa (2018), Seção 5.1.1.3
# - Turbulento: Dodge & Metzner (1959) - conforme Pessoa (2018), Seção 5.1.3.2
# - Combinação Laminar-Turbulento: Churchill-Darby (1992) - conforme Pessoa (2018)
# ENTRADAS: tau0 (Pa), n (-), U (m/s), D (m), K (Pa.s^n), Ro (kg/m³), resp (0-8)
# UNIDADES: adimensionais
# ============================================
def Herschfric2(Tau0, n, u, D, K, Ro, Resp):
    """
    Fator de atrito Herschel-Bulkley por ajuste direto da tensão de escoamento (tau0).
    Entradas:
        Tau0: tensão de escoamento (dyn/cm²)
        n: índice de comportamento (-)
        u: velocidade média (m/s)
        D: diâmetro do tubo (pol)
        K: consistência (cP)
        Ro: densidade (kg/m³)
        Resp: 0=x, 1=erro, 2=ReMR, 3=Miw, 4=R, 5=Rmod, 6=Tauw, 7=ff, 8=Re
    """
    Tau0 = Tau0 * 0.1  # dyn/cm² para Pa
    D = D * 0.0254     # pol para m
    K = K * 0.001      # cP para Pa.s
    x = 0.5
    x0 = 1e-7
    h = 1e-7
    erro = 0.5
    while erro >= 1e-8:
        A = K * (((8 * u) / D) ** n)
        B = (((3 * n) + 1) / (4 * n)) ** n
        C = 1 / (1 - x)
        E = (1 / ((2 * n) + 1)) * x
        f = ((2 * n) / ((n + 1) * ((2 * n) + 1))) * (x ** 2)
        G = (((2 * (n ** 2)) / ((n + 1) * ((2 * n) + 1)))) * (x ** 3)
        A0 = K * (((8 * u) / D) ** n)
        B0 = (((3 * n) + 1) / (4 * n)) ** n
        C0 = 1 / (1 - (x + h))
        E0 = (1 / ((2 * n) + 1)) * (x + h)
        F0 = ((2 * n) / ((n + 1) * ((2 * n) + 1))) * ((x + h) ** 2)
        G0 = (((2 * (n ** 2)) / ((n + 1) * ((2 * n) + 1)))) * ((x + h) ** 3)
        func = -x + (Tau0 / (A * B * C * ((1 / (1 - E - f - G)) ** n)))
        T0 = func
        T = -(x + h) + (Tau0 / (A0 * B0 * C0 * ((1 / (1 - E0 - F0 - G0)) ** n)))
        dfunc = (T - T0) / h
        x1 = x0 - func / dfunc
        erro = abs(x0 - x1)
        x0 = x1
        x = x1
    Tauw = A * B * C * ((1 / (1 - E - f - G)) ** n)
    A1 = K * (((8 * u) / D) ** (n - 1))
    ReMR = Ro * u * D / (A1 * B * C * ((1 / (1 - E - f - G)) ** n))
    Miw = (Tauw ** ((n - 1) / n)) * ((K / (1 - x)) ** (1 / n))
    R = Ro * u * D / (Miw * (((3 * n) + 1) / (4 * n)) * ((1 / (1 - E - f - G))))
    Rmod = R / ((n ** 2) * ((1 - x) ** 4))
    fl = 16 / R
    # Turbulento
    F0 = 0.0001
    h2 = 1e-10
    erro2 = 0.5
    while erro2 >= 1e-9:
        func2 = -(1 / (F0 ** 0.5)) - (0.4 / (n ** 1.2)) + (4 / (n ** 0.75)) * (np.log10(Re * (F0 ** ((2 - n) / 2))))
        T02 = func2
        T2 = -(1 / ((F0 + h2) ** 0.5)) - (0.4 / (n ** 1.2)) + (4 / (n ** 0.75)) * (np.log10(Re * ((F0 + h2) ** ((2 - n) / 2))))
        dfunc2 = (T2 - T02) / h2
        f2 = F0 - func2 / dfunc2
        erro2 = abs(F0 - f2)
        F0 = f2
    ft = f2
    if R > 5000:
        ff = ft
    else:
        ff = fl
    # Re para Herschel-Bulkley
    Re = Ro * (u ** (2 - n)) * (D ** n) / (Tau0 / 8 * (D / u) ** n + K * (((3 * n + 1) / (4 * n)) ** n) * (8 ** (n - 1)))
    if Resp == 0:
        return x
    elif Resp == 1:
        return erro
    elif Resp == 2:
        return ReMR
    elif Resp == 3:
        return Miw
    elif Resp == 4:
        return R
    elif Resp == 5:
        return Rmod
    elif Resp == 6:
        return Tauw
    elif Resp == 7:
        return ff
    elif Resp == 8:
        return Re
# ===========================================================
# Função principal do modelo Wasp aprimorada para cálculo de propriedades da polpa
# -----------------------------------------------------------
# Calcula propriedades da polpa e perdas de carga em escoamento bifásico heterogêneo.
# Principais etapas:
#   - Conversão de unidades (diâmetro, viscosidade, tubo)
#   - Cálculo de Tau0 (tensão de escoamento) e Eta (viscosidade plástica) por relações empíricas:
#       τ₀ = A·φ^B   [dyn/cm²], Eta = 10^{[φ/(1-φ)]·B'} [cP]
#   - Cálculo da velocidade terminal corrigida para cada fração (Levenspiel + Wasp)
#   - Propriedades da mistura: densidade, viscosidade efetiva (Bingham), Reynolds
#   - Iteração do fator de atrito (F) até convergência, recalculando propriedades do veículo (fração suspensa)
#   - Cálculo das perdas de carga: total, veículo, depositado, água
#   - Retorno de variáveis conforme parâmetro 'resultado'
# Entradas:
#   D: lista de diâmetros das partículas (micra)
#   c: lista de concentrações relativas de cada classe
#   Ros: densidade das partículas (kg/m³)
#   Rol: densidade do fluido (kg/m³)
#   Mil: viscosidade do fluido (cP)
#   D_tubo: diâmetro do tubo (pol)
#   eD: rugosidade relativa
#   U: velocidade média (m/s)
#   A, B, B_linha: parâmetros reológicos
#   Cv: fração volumétrica total de sólidos
#   resultado: define o que a função retorna
#   Cmax: concentração máxima
# Saídas: conforme 'resultado'
# ===========================================================
def wasp_mod_aprimorada(D, c, Ros, Rol, Mil, D_tubo, eD, U, A, B, B_linha, Cv, resultado, Cmax):
    """
    Função principal do modelo Wasp aprimorada para cálculo de propriedades da polpa
    D: lista de diâmetros das partículas (micra)
    c: lista de concentrações relativas de cada classe
    Ros: densidade das partículas
    Rol: densidade do fluido
    Mil: viscosidade do fluido
    D_tubo: diâmetro do tubo (pol)
    eD: rugosidade relativa
    U: velocidade média
    A, B, B_linha: parâmetros reológicos
    Cv: fração volumétrica total de sólidos
    resultado: define o que a função retorna
    Cmax: concentração máxima
    """
    dvals = np.array(D) * 1e-6  # converte diâmetro para metros
    cvals = np.array(c)
    Mil *= 0.001  # converte viscosidade do líquido base para Pa.s
    D_tubo *= 0.0254  # converte diâmetro do tubo para metros
    N = len(D)
    # Calcula Tau0 e Eta a partir de A, B, B' e Cv
    Tau0 = A * (Cv ** B)  # dyn/cm²
    Tau0_Pa = Tau0 * 0.1  # converte dyn/cm² para Pa
    # Ajuste de temperatura: multiplica pelo fator (mu_operacao / mu_20C)
    mu_agua_20C = 1.002  # cP (viscosidade da água a 20°C)
    fator_ajuste = Mil * 1000 / mu_agua_20C  # Mil está em Pa.s, multiplica por 1000 para cP
    Eta = fator_ajuste * (10 ** ((Cv / (1 - Cv)) * B_linha))  # cP
    Eta_Pa_s = Eta * 0.001  # converte cP para Pa.s    
    Mis = (Eta_Pa_s * (1 + (Tau0_Pa * D_tubo) / (6 * Eta_Pa_s * U)))
    # Propriedades da mistura
    Cw = (Cv * (Ros / 1000)) / (Cv * (Ros / 1000) + (1 - Cv) * (Rol / 1000))
    Rom = 100 / (((Cw * 100) / Ros) + ((100 - (100 * Cw)) / Rol))
        # Calcula velocidade terminal corrigida para cada diâmetro
    Ut = np.array([velterminal_levenspiel(dvals[i], Ros, Rol, Mil) * \
                   (10 ** ((-5.9 * Cv) / 2.303)) * \
                   (1 - (dvals[i] / D_tubo) ** 1.5) for i in range(N)])

    
    
    
    # Viscosidade efetiva por Bingham
    Re = Rom * U * D_tubo / (Mil)  # Número de Reynolds da mistura
    Re_agua = Rol * U * D_tubo / Mil  # Número de Reynolds da água
    He_bing = (D_tubo**2 * Tau0_Pa * Rom) / ((Eta_Pa_s)**2)
    Re_bing = Rom * U * D_tubo / Eta_Pa_s
    Re_trans = Bingtrans(D_tubo, Rom, Tau0_Pa, Eta_Pa_s, 2100, 1)  # Número
    # Cálculo do fator de atrito inicial
    if Re_bing <= Re_trans:
        F=Bingfric(Re_bing, He_bing, eD, 1)  # Fator de atrito laminar
    #    F = 16 / Re
    #elif Re <= 4000:
     #   F = 0.0008 + (0.0553 / (Re ** 0.237))
    else:
        #F=Bingfric(Re_bing, He_bing, eD, 0) 
        F = ((0.026 * (eD ** 0.225)) + (0.133 * eD) + (22 * (eD ** 0.44) * Re_bing ** (-1.62 * (eD ** 0.134))) * (1 - (0.33 * Cw)))
        #A = -1.47 * (1 + 0.146 * np.exp(-0.000029 * He_bing))
        #F = 1.5 * ((10 ** A) * (Re_bing ** (-0.193)))
    errof = 1.0
    iteracoes_wasp = 0
    max_iter_wasp = 100
    tol_wasp = 1e-7
    relax = 0.5
    F_old = F

    while errof > tol_wasp and iteracoes_wasp < max_iter_wasp:
        Uf = U * np.sqrt(F / 2)
        beta = 1 + 0.12504 * np.exp(4.22054 * (Cv / Cmax))
        fveiculo = F
        CvVeiculo = 0
        C0Ca = np.zeros(N)
        cvv = np.zeros(N)
        cvb = np.zeros(N)
        for i in range(N):
            Z = Ut[i] / (beta * 0.4 * Uf)
            C0Ca[i] = 10 ** (-1.8 * Z)
            cvv[i] = cvals[i] * C0Ca[i]
            cvb[i] = cvals[i] - cvv[i]
            CvVeiculo += cvv[i]
        CwV = (CvVeiculo * (Ros / 1000)) / (CvVeiculo * (Ros / 1000) + (1 - CvVeiculo) * (Rol / 1000))
        RomV = 100 / (((CwV * 100) / Ros) + ((100 - (100 * CwV)) / Rol))
        # Calcula Tau0 e Eta para o veículo com CvVeiculo
        Tau0V = A * (CvVeiculo ** B)  # dyn/cm²
        Tau0V_Pa = Tau0V * 0.1  # converte dyn/cm² para Pa
        EtaV = 10 ** ((CvVeiculo / (1 - CvVeiculo)) * B_linha)  # cP
        EtaV_ajustada = fator_ajuste * EtaV  # cP
        EtaV_Pa_s = EtaV_ajustada * 0.001  # converte cP para Pa.s
        # Viscosidade efetiva por Bingham para o veículo
        MisV = (EtaV_Pa_s * (1 + (Tau0V_Pa * D_tubo) / (6 * EtaV_Pa_s * U)))
        ReV = RomV * U * D_tubo / (Mil)
        He_bingV = (D_tubo**2 * Tau0V_Pa * RomV) / ((EtaV_Pa_s)**2)
        Re_bingV = RomV * U * D_tubo / EtaV_Pa_s
        Re_transV = Bingtrans(D_tubo, RomV, Tau0V_Pa, EtaV_Pa_s, 2100, 1)
        if Re_bingV <= Re_transV:
           F=Bingfric(Re_bingV, He_bingV, eD, 1)  # Fator de atrito laminar
        #if ReV <= 2000:
        #    F = 16 / ReV
        #elif ReV <= 4000:
        #    F = 0.0008 + (0.0553 / (ReV ** 0.237))
        else:
           #F=Bingfric(Re_bingV, He_bingV, eD, 0)
           F = ((0.026 * (eD ** 0.225)) + (0.133 * eD) + (22 * (eD ** 0.44) * Re_bingV ** (-1.62 * (eD ** 0.134))) * (1 - (0.33 * CwV)))
           #A = -1.47 * (1 + 0.146 * np.exp(-0.000029 * He_bingV))
           #F = 1.5 * ((10 ** A) * (Re_bingV ** (-0.193)))  0,
        F_calc = F

        # Relaxação para evitar oscilação
        F = relax * F_calc + (1.0 - relax) * fveiculo

        errof = abs(F - fveiculo)

        iteracoes_wasp += 1

    DeltaPveiculo = ((4 * F * (U ** 2)) / (2 * 9.8 * D_tubo))
    #fagua= Bingfric(Re, He, 0)
    #Fator de atrito e perda de carga da água usando Re_agua
    if Re_agua <= 2000:
        fagua = 16 / Re_agua
    elif Re_agua <= 4000:
        fagua = 0.0008 + (0.0553 / (Re_agua ** 0.237))
    else:
        fagua = (1 / (-1.8 * (np.log10(((eD / 3.7) ** 1.11) + (6.9 / Re_agua))))) ** 2 / 4
    DeltaPagua = ((4 * fagua * (U ** 2)) / (2 * 9.8 * D_tubo))
    Durand = 82
    Cd = (4 * 9.8 * dvals * (Ros - Rol)) / (3 * Rol * (Ut ** 2))
    DeltaPdepositado = Durand * DeltaPagua * cvb * (((9.8 * D_tubo * ((Ros / Rol) - 1)) / ((U ** 2) * np.sqrt(Cd))) ** 1.5) * (Rol / Rom)
    DeltaPdepTotal = np.sum(DeltaPdepositado)
    DeltaP = DeltaPveiculo + DeltaPdepTotal

    match resultado:
        case 1: return DeltaP
        case 2: return DeltaPveiculo
        case 3: return DeltaPdepTotal
        case 4: return CvVeiculo
        case 5: return np.sum(cvb)
        case 6: return C0Ca
        case 7: return cvv
        case 8: return cvb
        case 9: return Cd
        case 10: return Ut
        case 11: return Uf
        case 12: return F
        case 13: return iteracoes_wasp
        case 14: return Rom
        case 15: return Re
        case 16: return beta
        case 17: return DeltaPagua
        case 18: return RomV
        case _: return None

# ===========================================================
# Função u_estrela: Velocidade de cisalhamento
# -----------------------------------------------------------
# Equação: u* = U * sqrt(F/2)
# Entradas:
#   U: velocidade média (m/s)
#   F: fator de atrito (adimensional)
# Saída: u* (m/s)
# ===========================================================
def u_estrela(U, F):
    return U * np.sqrt(F / 2)

# ===========================================================
# Função calcular_el: Difusividade turbulenta do líquido
# -----------------------------------------------------------
# Equações segmentadas por faixa de y/D (Longwell 1977, Kaushal & Tomita 2002):
#   - yD < 0.337: el = 0.369 * u* * yR * (1 - yR)
#   - 0.337 <= yD <= 0.663: el = 0.1 * u* * sin(pi*yD)
#   - yD > 0.663: el = 0.369 * u* * (yR-1)*(2-yR)
# Entradas:
#   yD: elevação adimensional (y/D)
#   R: raio do tubo (m)
#   u_estrela: velocidade de cisalhamento (m/s)
# Saída: el (m²/s)
# ===========================================================
def calcular_el(yD, R, u_estrela):
    yR = 2 * yD
    if yD < 0.337:
        return 0.369 * u_estrela * yR * (1 - yR)
    elif yD <= 0.663:
        return 0.1 * u_estrela * np.sin(np.pi * yD)
    else:
        return 0.369 * u_estrela * (yR - 1) * (2 - yR)

# ===========================================================
# Função z_param: Parâmetro Z do perfil vertical
# -----------------------------------------------------------
# Equação 5.123 - perfil vertical
#   - Z = 4.65 + 19.5*djD, Re <= 0.2
#   - Z = (4.35 + 17.5*djD)*Re^-0.03, 0.2 < Re <= 1
#   - Z = (4.45 + 18*djD)*Re^-0.1, Re > 1
# Entradas:
#   Dp: diâmetro da partícula (m)
#   D: diâmetro do tubo (m)
#   Re: Reynolds da partícula (-)
# Saída: Z (-)
# ===========================================================
def z_param(Dp, D, Re):
    djD = Dp / D
    if Re <= 0.2:
        return 4.65 + 19.5 * djD
    elif Re <= 1:
        return (4.35 + 17.5 * djD) * Re**-0.03
    else:
        return (4.45 + 18 * djD) * Re**-0.1

# ===========================================================
# Função utj_corrigido: Velocidade terminal corrigida
# -----------------------------------------------------------
# Equação 5.122 - perfil vertical
#   Utj = Ut0 * (1 - phi)^Z
# Entradas:
#   Ut0: velocidade terminal inicial (m/s)
#   phi: fração volumétrica total (-)
#   Z: parâmetro Z (-)
# Saída: Utj (m/s)
# ===========================================================
def utj_corrigido(Ut0, phi, Z):
    return Ut0 * (1 - phi)**Z

# ===========================================================
# Função calcular_kj: Parâmetro Kj do perfil vertical
# -----------------------------------------------------------
# Equação 5.114 - perfil vertical
#   Kj = Utj / (zeta * u_estrela)
# Entradas:
#   Utj: velocidade terminal corrigida (m/s)
#   u_estrela: velocidade de cisalhamento (m/s)
#   zeta: difusividade adimensional (-)
# Saída: Kj (-)
# ===========================================================
def calcular_kj(Utj, u_estrela, zeta):
    return 0 if zeta <= 0 or u_estrela <= 0 else Utj / (zeta * u_estrela)

# ===========================================================
# Função ekj_aproximado: Fator de correção EKj
# -----------------------------------------------------------
# Equação 5.116 - perfil vertical
#   EKj = 1 + (Kj^2/8)*(1 + Kj^2/24)
# Entradas:
#   Kj: parâmetro Kj (-)
# Saída: EKj (-)
# ===========================================================
def ekj_aproximado(Kj):
    return 1 + (Kj**2 / 8) * (1 + (Kj**2 / 24))

# ===========================================================
# Função calcular_vj: Concentração relativa vj
# -----------------------------------------------------------
# Equação 5.118 - perfil vertical
#   vj = phi_i / (1 - phi_t)
# Entradas:
#   phi_i: fração volumétrica da classe i (-)
#   phi_t: fração volumétrica total (-)
# Saída: vj (-)
# ===========================================================
def calcular_vj(phi_i, phi_t):
    return phi_i / (1 - phi_t)

# ===========================================================
# Função phi_j_y: Concentração local da partícula j na elevação y*
# -----------------------------------------------------------
# Equação 5.117 - perfil vertical
#   phi_j(y*) = (vj/EKj) * exp(-Kj*y*) / [1 + sum_i (vi/EKi) * exp(-Ki*y*)]
# Entradas:
#   yStar: elevação adimensional (-)
#   vj: concentração relativa da classe j (-)
#   Kj: parâmetro Kj da classe j (-)
#   EKj: fator de correção da classe j (-)
#   vArr, KArr, EKArr: vetores para todas as classes
# Saída: phi_j(y*) (-)
# ===========================================================
def phi_j_y(yStar, vj, Kj, EKj, vArr, KArr, EKArr):
    # Limita o argumento do exponencial para evitar overflow
    LIMITE_EXP = 700
    arg_exp = np.clip(-Kj * yStar, -LIMITE_EXP, LIMITE_EXP)
    num = (vj / EKj) * np.exp(arg_exp)
    den = 1 + sum((vArr[i] / EKArr[i]) * np.exp(np.clip(-KArr[i] * yStar, -LIMITE_EXP, LIMITE_EXP)) for i in range(len(vArr)))
    return num / den

# ===========================================================
# Função gerar_vetor_elevacao: Gera vetor de elevações y/D
# -----------------------------------------------------------
# Gera pontos de elevação entre yMin e yMax, incluindo y/D=0.1 explicitamente.
# Entradas:
#   yMin: elevação mínima (adimensional)
#   yMax: elevação máxima (adimensional)
#   nPontosElev: número de pontos
# Saída: lista de yD
# ===========================================================
def gerar_vetor_elevacao(yMin, yMax, nPontosElev):
    yDvals = []
    passo = (yMax - yMin) / (nPontosElev - 1)
    incluiY01 = False
    for i in range(nPontosElev):
        yD = yMin + i * passo
        if not incluiY01 and yD > 0.1:
            yDvals.append(0.1)
            incluiY01 = True
        yDvals.append(yD)
    if not incluiY01:
        yDvals.append(0.1)
    return yDvals

# ===========================================================
# Função executar_modelo_karabelas: Modelo de perfil vertical
# -----------------------------------------------------------
# Executa o modelo completo de concentração vertical.
# Calcula o perfil vertical de concentração total e por classe.
# Entradas:
#   D: diâmetro do tubo (m)
#   U: velocidade média (m/s)
#   F: fator de atrito (-)
#   mu: viscosidade do fluido (Pa.s)
#   rho_l: densidade do fluido (kg/m³)
#   rho_s: densidade das partículas (kg/m³)
#   beta: parâmetro de difusividade adimensional (-)
#   phi_total: fração volumétrica total (-)
#   diametros: vetor de diâmetros das partículas (m)
#   phi_i: vetor de frações volumétricas por classe (-)
#   nPontosElev: número de pontos de elevação
#   yMin, yMax: limites de elevação (adimensional)
# Saída: matriz [yD, somaTotal]
# ===========================================================
def executar_modelo_karabelas(D, U, F, mu, rho_l, rho_s, beta, phi_total, diametros, phi_i, nPontosElev, yMin, yMax):
    R = D / 2
    u_star = u_estrela(U, F)
    yDlist = gerar_vetor_elevacao(yMin, yMax, nPontosElev)

    nParticulas = len(diametros)
    vArr = np.zeros(nParticulas)
    KArr = np.zeros(nParticulas)
    EKArr = np.zeros(nParticulas)

    resultado = []
    for yD in yDlist:
        yStar = 2 * yD - 1
        el = calcular_el(yD, R, u_star)
        es = beta * el
        zeta = es / (R * u_star)

        somaTotal = 0
        for j in range(nParticulas):
            # Substituir velterminal2 por velterminal_levenspiel
            Ut0 = velterminal_levenspiel(diametros[j], rho_s, rho_l, mu)
            Re = (diametros[j] * rho_l * Ut0) / mu
            Z = z_param(diametros[j], D, Re)
            Utj = utj_corrigido(Ut0, phi_total, Z)
            Kj = calcular_kj(Utj, u_star, zeta)
            EKj = ekj_aproximado(Kj)
            vj = calcular_vj(phi_i[j], phi_total)
            vArr[j] = vj
            KArr[j] = Kj
            EKArr[j] = EKj
        for j in range(nParticulas):
            phi_j = phi_j_y(yStar, vArr[j], KArr[j], EKArr[j], vArr, KArr, EKArr)
            somaTotal += phi_j

        resultado.append((yD, somaTotal))

    return np.array(resultado)

# ===========================================================
# Função faixa_anular: Área de faixa anular em seção circular
# -----------------------------------------------------------
# Calcula a largura da faixa anular para integração do perfil.
# Entradas:
#   R: raio do tubo (adimensional)
#   y1, y2: limites da faixa (adimensional)
#   Nint: número de subintervalos para integração
# Saída: área da faixa
# ===========================================================
def faixa_anular(R, y1, y2, Nint=10):
    dy = (y1 - y2) / Nint
    soma = 0
    for j in range(Nint + 1):
        y = y2 + j * dy
        if abs(y) <= R:
            largura = 2 * np.sqrt(R**2 - y**2)
            peso = 0.5 if j == 0 or j == Nint else 1
            soma += peso * largura
    return soma * dy

# ===========================================================
# Função altura_deposito_cv: Altura relativa do depósito
# -----------------------------------------------------------
# Calcula a altura relativa do depósito de partículas a partir do perfil de concentração.
# Entradas:
#   cv: vetor de concentrações verticais
#   cv_depositado: fração depositada
# Saída: altura relativa (y/D)
# ===========================================================
def altura_deposito_cv(cv: np.ndarray, cv_depositado: float) -> float:
    N = len(cv)
    dy = 1.0 / N
    R = 0.5
    y_rel = np.array([(i + 1) / N for i in range(N)])
    A = np.zeros(N)
    Acv = np.zeros(N)

    Atotal = 0
    for i in range(N):
        y1 = R - i * dy
        y2 = R - (i + 1) * dy
        A[i] = faixa_anular(R, y1, y2)
        Atotal += A[i]

    for i in range(N):
        Acv[i] = cv[i] * A[i]

    acumulado = 0
    for i in range(N):
        acumulado += Acv[i] / Atotal
        if acumulado >= cv_depositado:
            return y_rel[i]

    return -1  # Não encontrou a fração desejada

# ===========================================================
# Função calcular_homogeneo: Propriedades do escoamento homogêneo
# -----------------------------------------------------------
# OBJETIVO:
#   Calcula propriedades de escoamento homogêneo para polpas, permitindo escolha entre modelos reológicos:
#   - Plástico de Bingham (n=1, Tau0>0)
#   - Power Law (n≠1, Tau0=0)
#   - Herschel-Bulkley (n≠1, Tau0>0)
# PRINCIPAIS ETAPAS:
#   1. Interface gráfica para seleção do tipo de fluido homogêneo (Tkinter)
#   2. Cálculo das propriedades da mistura:
#      - Cw: concentração mássica (%)
#      - Rom: densidade da mistura (kg/m³)
#      - Tau0: tensão de escoamento (dyn/cm² → Pa)
#      - Eta: viscosidade plástica (cP → Pa.s)
#   3. Cálculo dos números adimensionais:
#      - He: Hedstrom (adimensional)
#      - Re: Reynolds generalizado (adimensional)
#      - ReG: Reynolds Herschel-Bulkley (adimensional)
#   4. Cálculo dos pontos de transição (Bingham/Power Law) e regimes de escoamento
#   5. Exibição dos resultados em janela de mensagem (Tkinter)
#   6. Geração de gráficos dos fatores de atrito para o regime selecionado
# ENTRADAS:
#   D         - diâmetro do tubo (m)
#   U         - velocidade média (m/s)
#   mu        - viscosidade do fluido base (Pa.s)
#   rho_l     - densidade do fluido (kg/m³)
#   rho_s     - densidade das partículas (kg/m³)
#   A, B      - parâmetros reológicos para Tau0
#   B_linha   - parâmetro reológico para Eta
#   n         - índice de comportamento reológico (-)
#   phi_total - fração volumétrica total de sólidos (-)
# SAÍDA:
#   Dicionário com propriedades calculadas e exibição gráfica dos resultados
# ===========================================================


DEFAULT_ENTRADAS = {
    "diametro_pol": 6.05,
    "rugosidade_relativa": 0.000489,
    "velocidade": 3.6,
    "phi_total": 0.141,
    "proporcoes_percent": [5.07, 12.47, 12.99, 11.05, 9.699997, 6.09, 6.66, 3.760002, 32.21],
    "diametros_um": [250, 149, 105, 74, 53, 37, 25, 20, 1],
    "rho_s": 2610,
    "rho_l": 1000,
    "mu_l_cp": 0.89,
    "A": 2667433.8,
    "B": 10.54,
    "B_linha": 2.2844,
    "n": 1.0,
    "n_pontos_elev": 200,
    "yD_min": 0.01,
    "yD_max": 0.99,
    "erro": 0.0001,
    "max_iter": 100,
    "U_inicial": 0.05,
    "U_final": 10.0,
    "U_passo": 0.05,
    "fator_perda": 1.1,
    "modelo_escoamento": "auto",
    "tipo_fluido_homogeneo": "bingham",
}


def _as_float(value, nome):
    if value is None or value == "":
        raise ValueError(_("Campo obrigatório: %(nome)s") % {"nome": _(nome)})
    try:
        return float(str(value).strip().replace(",", "."))
    except ValueError as exc:
        raise ValueError(_("Valor inválido em %(nome)s: %(valor)s") % {"nome": _(nome), "valor": value}) from exc


def _as_int(value, nome):
    valor = _as_float(value, nome)
    if not float(valor).is_integer():
        raise ValueError(_("%(nome)s deve ser inteiro.") % {"nome": _(nome)})
    return int(valor)


def _as_list_float(value, nome):
    if isinstance(value, (list, tuple, np.ndarray)):
        partes = value
    else:
        partes = [p.strip() for p in str(value).split(",") if p.strip()]
    if not partes:
        raise ValueError(_("Campo obrigatório: %(nome)s") % {"nome": _(nome)})
    try:
        return [float(str(p).replace(",", ".")) for p in partes]
    except ValueError as exc:
        raise ValueError(_("Lista inválida em %(nome)s. Use vírgula para separar itens.") % {"nome": _(nome)}) from exc


def _json_safe(value):
    if isinstance(value, np.ndarray):
        return [_json_safe(v) for v in value.tolist()]
    if isinstance(value, (np.floating, np.integer)):
        return value.item()
    if isinstance(value, float):
        if np.isnan(value) or np.isinf(value):
            return None
        return value
    if isinstance(value, dict):
        return {k: _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    return value


def _validar_resultados_criticos(**valores):
    for nome, valor in valores.items():
        try:
            valido = np.isfinite(float(valor))
        except (TypeError, ValueError):
            valido = False
        if not valido:
            raise ValueError(
                _("A simulação gerou resultado numérico inválido. Verifique as entradas físicas do modelo.")
                + f" ({nome})"
            )


def normalizar_entradas(entradas):
    dados = {**DEFAULT_ENTRADAS, **(entradas or {})}
    dados["diametro_pol"] = _as_float(dados["diametro_pol"], "DI - Diâmetro interno do tubo (pol)")
    dados["rugosidade_relativa"] = _as_float(dados["rugosidade_relativa"], "e/D - Rugosidade relativa")
    dados["velocidade"] = _as_float(dados["velocidade"], "U - Velocidade média")
    dados["phi_total"] = _as_float(dados["phi_total"], "φ - fração volumétrica total")
    dados["rho_s"] = _as_float(dados["rho_s"], "ρs - Densidade das partículas")
    dados["rho_l"] = _as_float(dados["rho_l"], "ρl - Densidade do fluido")
    dados["mu_l_cp"] = _as_float(dados["mu_l_cp"], "μl - Viscosidade do fluido")
    dados["A"] = _as_float(dados["A"], "A")
    dados["B"] = _as_float(dados["B"], "B")
    dados["B_linha"] = _as_float(dados["B_linha"], "B'")
    dados["n"] = _as_float(dados["n"], "n")
    dados["n_pontos_elev"] = _as_int(dados["n_pontos_elev"], "nPontosElev")
    dados["yD_min"] = _as_float(dados["yD_min"], "y/D Min")
    dados["yD_max"] = _as_float(dados["yD_max"], "y/D Max")
    dados["erro"] = _as_float(dados["erro"], "erro")
    dados["max_iter"] = min(_as_int(dados["max_iter"], "max_iter"), 100)
    dados["U_inicial"] = _as_float(dados["U_inicial"], "U inicial")
    dados["U_final"] = _as_float(dados["U_final"], "U final")
    dados["U_passo"] = _as_float(dados["U_passo"], "U passo")
    dados["fator_perda"] = _as_float(dados["fator_perda"], "Fator de ajuste")
    dados["proporcoes_percent"] = _as_list_float(dados["proporcoes_percent"], "φi")
    dados["diametros_um"] = _as_list_float(dados["diametros_um"], "di")
    dados["modelo_escoamento"] = str(dados.get("modelo_escoamento") or "auto")
    dados["tipo_fluido_homogeneo"] = str(dados.get("tipo_fluido_homogeneo") or "bingham")
    if dados["modelo_escoamento"] not in {"auto", "heterogeneo", "homogeneo"}:
        dados["modelo_escoamento"] = "auto"
    if dados["tipo_fluido_homogeneo"] not in {"bingham", "powerlaw", "hb"}:
        dados["tipo_fluido_homogeneo"] = "bingham"

    if len(dados["diametros_um"]) != len(dados["proporcoes_percent"]):
        raise ValueError(_("As listas de diâmetros e proporções devem ter a mesma quantidade de itens."))
    if dados["velocidade"] <= 0:
        raise ValueError(_("A velocidade operacional deve ser maior que zero."))
    if dados["rugosidade_relativa"] <= 0:
        raise ValueError(_("A rugosidade deve ser maior que zero."))
    if any(diametro <= 0 for diametro in dados["diametros_um"]):
        raise ValueError(_("Todos os diâmetros granulométricos devem ser maiores que zero."))
    if any(fracao < 0 for fracao in dados["proporcoes_percent"]):
        raise ValueError(_("As frações granulométricas não podem ser negativas."))
    if np.sum(dados["proporcoes_percent"]) <= 0:
        raise ValueError(_("A soma das frações granulométricas deve ser maior que zero."))
    if not np.isclose(np.sum(np.array(dados["proporcoes_percent"]) / 100), 1.0):
        raise ValueError(_("As proporções relativas devem somar 100%."))
    if dados["rho_s"] <= dados["rho_l"]:
        raise ValueError(_("Para o modelo atual, a densidade dos sólidos deve ser maior que a densidade do líquido."))
    if not 0 < dados["n"] < 2:
        raise ValueError(_("O índice reológico n deve estar entre 0 e 2."))
    if dados["U_passo"] <= 0:
        raise ValueError(_("U passo deve ser maior que zero."))
    if dados["U_final"] < dados["U_inicial"]:
        raise ValueError(_("U final deve ser maior ou igual a U inicial."))
    return dados


def calcular_homogeneo_web(dados, precheck=None):
    D = dados["diametro_pol"] * 0.0254
    U = dados["velocidade"]
    mu = dados["mu_l_cp"] * 0.001
    rho_l = dados["rho_l"]
    rho_s = dados["rho_s"]
    A = dados["A"]
    B = dados["B"]
    B_linha = dados["B_linha"]
    n = max(float(dados["n"]), 1e-6)
    phi_total = dados["phi_total"]
    e_D = dados["rugosidade_relativa"]
    fator_perda = dados["fator_perda"]
    modo = dados["tipo_fluido_homogeneo"]
    velocidades = np.arange(dados["U_inicial"], dados["U_final"] + dados["U_passo"] / 2, dados["U_passo"])

    diametros = np.array(dados["diametros_um"], dtype=float) * 1e-6
    proporcoes_relativas = np.array(dados["proporcoes_percent"], dtype=float) / 100
    phi_i = proporcoes_relativas * phi_total
    diametros_um_inv = (diametros * 1e6)[::-1].tolist()
    passante_input = []
    soma_input = 0
    for val in phi_i:
        passante_input.append(100 * (1 - soma_input / phi_total) if phi_total > 0 else 0)
        soma_input += val

    Cw = (phi_total * (rho_s / 1000)) / (phi_total * (rho_s / 1000) + (1 - phi_total) * (rho_l / 1000))
    Rom = 100 / (((Cw * 100) / rho_s) + ((100 - (100 * Cw)) / rho_l))
    Tau0 = A * (phi_total ** B)
    Tau0_Pa = Tau0 * 0.1
    mu_agua_20C = 1.002
    fator_ajuste = mu * 1000 / mu_agua_20C
    Eta = fator_ajuste * (10 ** ((phi_total / (1 - phi_total)) * B_linha))
    Eta_Pa_s = Eta * 0.001
    He = ((D ** 2) * Rom * (Tau0_Pa ** ((2 / n) - 1))) / (Eta_Pa_s ** (2 / n)) if Tau0_Pa > 0 and Eta_Pa_s > 0 else 0
    Re = (Rom * (U ** (2 - n)) * (D ** n)) / (Eta_Pa_s * ((0.75 + (0.25 / n)) ** n) * (8 ** (n - 1))) if Eta_Pa_s > 0 else 0
    try:
        ReG = GeneralizedRe(Tau0_Pa, Eta_Pa_s, n, Rom, D, U, 1)
    except Exception:
        ReG = float("nan")

    def perda_agua_em_velocidade(v):
        if v <= 0 or mu <= 0:
            return np.nan
        Re_agua = rho_l * v * D / mu
        if Re_agua <= 0:
            return np.nan
        if Re_agua <= 2000:
            fagua = 16 / Re_agua
        elif Re_agua <= 4000:
            fagua = 0.0008 + (0.0553 / (Re_agua ** 0.237))
        else:
            fagua = (1 / (-1.8 * (np.log10(((e_D / 3.7) ** 1.11) + (6.9 / Re_agua))))) ** 2 / 4
        return ((4 * fagua * (v ** 2)) / (2 * 9.8 * D)) * 1000

    def props_em_velocidade(v):
        Re_v = (Rom * (v ** (2 - n)) * (D ** n)) / (Eta_Pa_s * ((0.75 + (0.25 / n)) ** n) * (8 ** (n - 1))) if Eta_Pa_s > 0 and v > 0 else np.nan
        He_v = He
        if modo == "bingham":
            f_v = Bingfric(Re_v, He_v, e_D, 0)
            Re_plot = Re_v
        elif modo == "powerlaw":
            f_v = Powerfric(Re_v, n, e_D, 0)
            Re_plot = Re_v
        else:
            f_v = Herschfric(Re_v, He_v, n, e_D, 0)
            Re_plot = Re_v
        perda_v = ((4 * f_v * (v ** 2)) / (2 * 9.8 * D)) * 1000 * fator_perda if np.isfinite(f_v) and v > 0 else np.nan
        return Re_plot, f_v, perda_v

    re_oper, f_oper, DeltaP = props_em_velocidade(U)
    perdas_carga = []
    perdas_agua = []
    reynolds_operacao = []
    fatores_operacao = []
    for v in velocidades:
        re_v, f_v, perda_v = props_em_velocidade(v)
        reynolds_operacao.append(re_v)
        fatores_operacao.append(f_v)
        perdas_carga.append(perda_v)
        perdas_agua.append(perda_agua_em_velocidade(v))

    polpa_abaixo_agua = any(
        np.isfinite(perda_polpa) and np.isfinite(perda_agua) and perda_polpa < perda_agua
        for perda_polpa, perda_agua in zip(perdas_carga, perdas_agua)
    )

    Retn = 2100
    if modo == "bingham":
        Re_bt1 = Bingtrans(D, Rom, Tau0_Pa, Eta_Pa_s, Retn, 1)
        He_bt1 = Bingtrans(D, Rom, Tau0_Pa, Eta_Pa_s, Retn, 2)
        Uc_bt1 = Bingtrans(D, Rom, Tau0_Pa, Eta_Pa_s, Retn, 0)
        Re_bt2 = Bingtrans2(D / 0.0254, Rom, Tau0, Eta, 1)
        He_bt2 = Bingtrans2(D / 0.0254, Rom, Tau0, Eta, 2)
        Uc_bt2 = Bingtrans2(D / 0.0254, Rom, Tau0, Eta, 0)
        regime = "Turbulento" if U > Uc_bt1 else "Laminar"
    else:
        Re_bt1 = He_bt1 = Uc_bt1 = Re_bt2 = He_bt2 = Uc_bt2 = np.nan
        regime = ""

    if modo == "powerlaw":
        Uc_pw = Powertrans(U, D / 0.0254, Rom, Eta, n, 0)
        Ret_pw = Powertrans(U, D / 0.0254, Rom, Eta, n, 1)
        Re_pw = Powertrans(U, D / 0.0254, Rom, Eta, n, 2)
        regime = "Turbulento" if U > Uc_pw else "Laminar"
    else:
        Uc_pw = Ret_pw = Re_pw = np.nan

    if modo == "hb":
        regime = "Turbulento" if ReG > 3000 else "Laminar"

    Re_vals = np.logspace(3, 8, num=80)
    curvas = []
    if modo == "bingham":
        for he_test in [0, 100, 1000, 10000, 100000, 1000000, 10000000, 100000000]:
            curvas.append({"name": f"He={he_test:g}", "x": Re_vals.tolist(), "y": [Bingfric(r, he_test, e_D, 0) for r in Re_vals]})
        He_trans = np.logspace(1, 8, num=50)
        Re_trans_1 = [(Retn / 2) * (1 + (1 + (2 * he / (3 * Retn))) ** 0.5) for he in He_trans]
        Re_trans_2 = [2100 * ((1 + (he / 3600)) ** 0.35) for he in He_trans]
        curvas.append({
            "name": "Transição Bingham 1",
            "x": Re_trans_1,
            "y": [Bingfric(re_t, he, e_D, 0) for re_t, he in zip(Re_trans_1, He_trans)],
            "dash": "dashdot",
            "width": 3,
        })
        curvas.append({
            "name": "Transição Bingham 2",
            "x": Re_trans_2,
            "y": [Bingfric(re_t, he, e_D, 0) for re_t, he in zip(Re_trans_2, He_trans)],
            "dash": "dashdot",
            "width": 3,
        })
        titulo_grafico = "Fator de atrito homogêneo - Bingham"
        nome_modo = "Plástico de Bingham"
    elif modo == "powerlaw":
        for n_val in [0.2, 0.4, 0.6, 0.8, 1.0, 1.4, 2.0]:
            curvas.append({"name": f"n={n_val:g}", "x": Re_vals.tolist(), "y": [Powerfric(r, n_val, e_D, 0) for r in Re_vals]})
        n_trans = np.linspace(0.1, 2.0, num=50)
        Re_trans = [
            (6464 * n_val * ((n_val + 2) ** ((n_val + 2) / (n_val + 1)))) / ((1 + 3 * n_val) ** 2)
            for n_val in n_trans
        ]
        curvas.append({
            "name": "Transição Power Law",
            "x": Re_trans,
            "y": [Powerfric(re_t, n_val, e_D, 0) for re_t, n_val in zip(Re_trans, n_trans)],
            "dash": "dashdot",
            "width": 3,
        })
        titulo_grafico = "Fator de atrito homogêneo - Power Law"
        nome_modo = "Power Law"
    else:
        He_curvas = [0, 100, 1000, 10000, 100000, 1000000, 10000000, 100000000]
        for he_test in He_curvas:
            curvas.append({"name": f"He={he_test:g}", "x": Re_vals.tolist(), "y": [Herschfric(r, he_test, n, e_D, 0) for r in Re_vals]})

        def re_hb_na_transicao(he_test):
            if abs(2.0 - n) < 1e-8:
                tau0_trans = Tau0_Pa
            elif he_test <= 0:
                tau0_trans = 0.0
            else:
                tau0_trans = (
                    he_test * (Eta_Pa_s ** (2.0 / n)) / ((D ** 2) * Rom)
                ) ** (n / (2.0 - n))

            velocidade_min = 1e-8
            velocidade_max = max(U, 1.0)
            while GeneralizedRe(tau0_trans, Eta_Pa_s, n, Rom, D, velocidade_max, 1) < 3000:
                velocidade_max *= 2.0
                if velocidade_max > 1e6:
                    return np.nan

            for _ in range(80):
                velocidade_meio = 0.5 * (velocidade_min + velocidade_max)
                reg_meio = GeneralizedRe(tau0_trans, Eta_Pa_s, n, Rom, D, velocidade_meio, 1)
                if reg_meio < 3000:
                    velocidade_min = velocidade_meio
                else:
                    velocidade_max = velocidade_meio

            velocidade_trans = 0.5 * (velocidade_min + velocidade_max)
            return (
                Rom * (velocidade_trans ** (2 - n)) * (D ** n)
            ) / (Eta_Pa_s * ((0.75 + (0.25 / n)) ** n) * (8 ** (n - 1)))

        Re_trans_hb = [re_hb_na_transicao(he_test) for he_test in He_curvas]
        curvas.append({
            "name": "Transição Herschel-Bulkley (ReG=3000)",
            "x": Re_trans_hb,
            "y": [Herschfric(re_t, he_test, n, e_D, 0) for re_t, he_test in zip(Re_trans_hb, He_curvas)],
            "dash": "dashdot",
            "width": 3,
        })
        titulo_grafico = "Fator de atrito homogêneo - Herschel-Bulkley"
        nome_modo = "Herschel-Bulkley"

    curvas.append({
        "name": "Newtoniano (água)",
        "x": Re_vals.tolist(),
        "y": [Newtoniano(r, e_D) for r in Re_vals],
        "dash": "dot",
        "width": 3,
    })

    yD_vals = gerar_vetor_elevacao(dados["yD_min"], dados["yD_max"], dados["n_pontos_elev"])
    c0ca_total_percent = 100.0
    c0ca_precheck = (precheck or {}).get("c0ca_total_percent")
    if modo == "bingham":
        coeficiente_simbolo = "η"
        coeficiente_descricao = "Coeficiente de rigidez"
    elif modo == "powerlaw":
        coeficiente_simbolo = "K<sub>p</sub>"
        coeficiente_descricao = "Coeficiente de fluido tipo Power Law"
    else:
        coeficiente_simbolo = "K<sub>h</sub>"
        coeficiente_descricao = "Coeficiente de fluido tipo Herschel-Bulkley"
    tabela_resultados = [
        {"simbolo": "Modelo", "descricao": "Modelo de escoamento selecionado", "valor": nome_modo, "unidade": "-"},
        {"simbolo": "Regime", "descricao": "Regime estimado", "valor": regime, "unidade": "-"},
        {"simbolo": "Re", "descricao": "Número de Reynolds generalizado", "valor": Re, "unidade": "-"},
        {"simbolo": "He", "descricao": "Número de Hedstrom", "valor": He, "unidade": "-"},
        {"simbolo": "ReG", "descricao": "Reynolds generalizado Herschel-Bulkley", "valor": ReG, "unidade": "-"},
        {"simbolo": "f", "descricao": "Fator de atrito operacional", "valor": f_oper, "unidade": "-"},
        {"simbolo": "ΔP", "descricao": "Perda de carga homogênea", "valor": DeltaP, "unidade": "m/km"},
        {"simbolo": "C/Ca total", "descricao": "Sólidos suspensos / sólidos totais", "valor": c0ca_total_percent, "unidade": "%"},
        {"simbolo": "C/Ca prévio", "descricao": "C/Ca total calculado no teste heterogêneo", "valor": c0ca_precheck, "unidade": "%"},
        {"simbolo": "φ<sub>w</sub>", "descricao": "Concentração mássica da polpa", "valor": Cw * 100, "unidade": "%"},
        {"simbolo": "τ₀", "descricao": "Tensão de escoamento", "valor": Tau0_Pa, "unidade": "Pa"},
        {"simbolo": coeficiente_simbolo, "descricao": coeficiente_descricao, "valor": Eta, "unidade": "cP"},
        {"simbolo": "ρₘ", "descricao": "Densidade da mistura", "valor": Rom, "unidade": "kg/m³"},
        {"simbolo": "ΔP", "descricao": "Perda de carga total polpa", "valor": DeltaP, "unidade": "m/km"},
        {"simbolo": "ΔP", "descricao": "Perda de carga total polpa", "valor": DeltaP * Rom * 9.80665 / 1e5, "unidade": "bar/km"},
        {"simbolo": "Uc B1", "descricao": "Velocidade crítica Bingham 1", "valor": Uc_bt1, "unidade": "m/s"},
        {"simbolo": "Uc B2", "descricao": "Velocidade crítica Bingham 2", "valor": Uc_bt2, "unidade": "m/s"},
        {"simbolo": "Uc PL", "descricao": "Velocidade crítica Power Law", "valor": Uc_pw, "unidade": "m/s"},
        {"simbolo": "Ret PL", "descricao": "Reynolds de transição Power Law", "valor": Ret_pw, "unidade": "-"},
    ]

    avisos = [f"Modelo homogêneo selecionado ({nome_modo})."]
    if modo == "bingham" and not np.isclose(n, 1.0):
        avisos.append(_(
            "Atenção: para o modelo Bingham, o índice n deve ser igual a 1. "
            "Com n diferente de 1, o resultado será calculado, mas o modelo Bingham "
            "deve ser considerado conceitualmente inválido."
        ))
    if polpa_abaixo_agua:
        avisos.append(
            "A perda de carga calculada para a polpa ficou abaixo da perda de carga da água "
            "em parte da faixa do gráfico. Esse comportamento não é usualmente observado em campo; "
            "avalie os parâmetros e utilize o resultado com cautela."
        )

    _validar_resultados_criticos(
        perda_carga=DeltaP,
        fator_atrito=f_oper,
        reynolds=Re,
        hedstrom=He,
        concentracao_massica=Cw,
        densidade_mistura=Rom,
        coeficiente_reologico=Eta,
    )

    return _json_safe({
        "entradas": dados,
        "resumo": {
            "modelo_escoamento": "homogeneo",
            "tipo_fluido_homogeneo": modo,
            "velocidade_operacao": U,
            "perda_carga_operacao": DeltaP,
            "perda_carga_bar_km": DeltaP * Rom * 9.80665 / 1e5,
            "densidade_polpa": Rom,
            "phi_w_percent": Cw * 100,
            "c0ca_total_percent": c0ca_total_percent,
            "c0ca_precheck_percent": c0ca_precheck,
        },
        "avisos": avisos,
        "tabela_resultados": tabela_resultados,
        "graficos": {
            "concentracao_vertical": {
                "x_phi": [phi_total for _ in yD_vals],
                "yD": yD_vals,
                "phi_ref": phi_total,
                "phi_ref_yD": 0.1,
                "altura_deposito": 0,
            },
            "perda_carga": {
                "velocidades": velocidades.tolist(),
                "polpa": perdas_carga,
                "arraste": [],
                "agua": perdas_agua,
                "operacao_x": U,
                "operacao_y": DeltaP,
            },
            "cv_veiculo": {
                "velocidades": velocidades.tolist(),
                "percentual": [100 for _ in velocidades],
                "operacao_x": U,
                "operacao_y": c0ca_total_percent,
            },
            "c0ca": {
                "velocidades": velocidades.tolist(),
                "series": [{"diametro_um": float(d * 1e6), "valores": [100 for _ in velocidades]} for d in diametros],
                "operacao_x": U,
                "operacao_total_y": c0ca_total_percent,
            },
            "granulometria_concentracao": {
                "diametros_um": diametros_um_inv,
                "yD_005": phi_i[::-1].tolist(),
                "yD_050": phi_i[::-1].tolist(),
                "yD_095": phi_i[::-1].tolist(),
            },
            "granulometria_passante_modelo": {
                "diametros_um": diametros_um_inv,
                "yD_005": list(reversed(passante_input)),
                "yD_050": list(reversed(passante_input)),
                "yD_095": list(reversed(passante_input)),
            },
            "granulometria_passante_entrada": {
                "diametros_um": diametros_um_inv,
                "passante": list(reversed(passante_input)),
            },
            "homogeneo_fator_atrito": {
                "titulo": titulo_grafico,
                "series": curvas,
                "operacao_x": re_oper,
                "operacao_y": f_oper,
                "operacao_label": f"Re={re_oper:.2e}; f={f_oper:.4g}; ΔP={DeltaP:.2f} m/km",
                "reynolds_velocidades": reynolds_operacao,
                "fatores_velocidades": fatores_operacao,
            },
        },
    })


def executar_simulacao(entradas):
    dados = normalizar_entradas(entradas)

    D = dados["diametro_pol"] * 0.0254
    U = dados["velocidade"]
    mu = dados["mu_l_cp"] * 0.001
    rho_l = dados["rho_l"]
    rho_s = dados["rho_s"]
    A = dados["A"]
    B = dados["B"]
    B_linha = dados["B_linha"]
    phi_total = dados["phi_total"]
    n_pontos = dados["n_pontos_elev"]
    y_min = dados["yD_min"]
    y_max = dados["yD_max"]
    e_D = dados["rugosidade_relativa"]
    fator_perda = dados["fator_perda"]

    diametros = np.array(dados["diametros_um"]) * 1e-6
    proporcoes_relativas = np.array(dados["proporcoes_percent"]) / 100
    phi_i = proporcoes_relativas * phi_total
    velocidades = np.arange(dados["U_inicial"], dados["U_final"] + dados["U_passo"] / 2, dados["U_passo"])

    beta = 4.0
    F = 0.005
    df = None
    phi_ref = None
    Cvmax = None
    for i in range(dados["max_iter"]):
        resultado_karabelas = executar_modelo_karabelas(
            D, U, F, mu, rho_l, rho_s, beta, phi_total,
            diametros, phi_i, n_pontos, y_min, y_max
        )
        df = pd.DataFrame(resultado_karabelas, columns=["y/D", "phi_total"])
        yD_ref = 0.1
        phi_ref = df.loc[(df["y/D"] - yD_ref).abs().idxmin(), "phi_total"]
        Cvmax = phi_ref / (3 * phi_total)

        beta_novo = wasp_mod_aprimorada(
            diametros * 1e6, phi_i.tolist(), rho_s, rho_l, mu * 1000, D / 0.0254,
            e_D, U, A, B, B_linha, phi_total, 16, Cvmax
        )
        F_novo = wasp_mod_aprimorada(
            diametros * 1e6, phi_i.tolist(), rho_s, rho_l, mu * 1000, D / 0.0254,
            e_D, U, A, B, B_linha, phi_total, 12, Cvmax
        )
        erro_beta = abs(beta_novo - beta)
        erro_F = abs(F_novo - F)
        if max(erro_beta, erro_F) < dados["erro"]:
            beta = beta_novo
            F = F_novo
            break
        beta = beta_novo
        F = F_novo

    iteracoes_acoplamento = i + 1
    erro_beta = locals().get("erro_beta", 0)
    erro_F = locals().get("erro_F", 0)
    Cvveiculo = wasp_mod_aprimorada(
        diametros * 1e6, phi_i.tolist(), rho_s, rho_l, mu * 1000, D / 0.0254,
        e_D, U, A, B, B_linha, phi_total, 4, Cvmax
    )
    cv_deposito = phi_total - Cvveiculo
    altura_rel_deposito = altura_deposito_cv(df["phi_total"].values, cv_deposito)
    DeltaP = wasp_mod_aprimorada(
        diametros * 1e6, phi_i.tolist(), rho_s, rho_l, mu * 1000, D / 0.0254,
        e_D, U, A, B, B_linha, phi_total, 1, Cvmax
    ) * 1000 * fator_perda
    Beta_final = wasp_mod_aprimorada(
        diametros * 1e6, phi_i.tolist(), rho_s, rho_l, mu * 1000, D / 0.0254,
        e_D, U, A, B, B_linha, phi_total, 16, Cvmax
    )
    DeltaPveiculo = wasp_mod_aprimorada(
        diametros * 1e6, phi_i.tolist(), rho_s, rho_l, mu * 1000, D / 0.0254,
        e_D, U, A, B, B_linha, phi_total, 2, Cvmax
    ) * 1000 * fator_perda
    Rom = wasp_mod_aprimorada(
        diametros * 1e6, phi_i.tolist(), rho_s, rho_l, mu * 1000, D / 0.0254,
        e_D, U, A, B, B_linha, phi_total, 14, Cvmax
    )
    RomV = wasp_mod_aprimorada(
        diametros * 1e6, phi_i.tolist(), rho_s, rho_l, mu * 1000, D / 0.0254,
        e_D, U, A, B, B_linha, phi_total, 18, Cvmax
    )
    n_modelo = wasp_mod_aprimorada(
        diametros * 1e6, phi_i.tolist(), rho_s, rho_l, mu * 1000, D / 0.0254,
        e_D, U, A, B, B_linha, phi_total, 13, Cvmax
    )
    Cw = (phi_total * (rho_s / 1000)) / (phi_total * (rho_s / 1000) + (1 - phi_total) * (rho_l / 1000))
    Tau0 = A * (phi_total ** B)
    Tau0_Pa = Tau0 * 0.1
    Eta = 10 ** ((phi_total / (1 - phi_total)) * B_linha)
    mu_agua_20C = 1.002
    fator_ajuste = mu * 1000 / mu_agua_20C
    Eta_ajustada = fator_ajuste * Eta
    Eta_Pa_s = Eta_ajustada * 0.001
    Tau0V = A * (Cvveiculo ** B)
    Tau0V_Pa = Tau0V * 0.1
    EtaV = 10 ** ((Cvveiculo / (1 - Cvveiculo)) * B_linha) if Cvveiculo < 1 else float("inf")
    EtaV_ajustada = fator_ajuste * EtaV
    EtaV_Pa_s = EtaV_ajustada * 0.001
    Mis = Eta_Pa_s * (1 + (Tau0_Pa * D) / (6 * Eta_Pa_s * U)) if Eta_Pa_s > 0 and U > 0 else 0
    MisV = EtaV_Pa_s * (1 + (Tau0V_Pa * D) / (6 * EtaV_Pa_s * U)) if EtaV_Pa_s > 0 and U > 0 else 0
    Uc_bing = Bingtrans(D, Rom, Tau0_Pa, Eta_Pa_s, 2100, 0) if Eta_Pa_s > 0 else np.nan

    perdas_carga = [
        wasp_mod_aprimorada(diametros * 1e6, phi_i.tolist(), rho_s, rho_l, mu * 1000, D / 0.0254, e_D, v, A, B, B_linha, phi_total, 1, Cvmax) * 1000 * fator_perda
        for v in velocidades
    ]
    perdas_arraste = [
        wasp_mod_aprimorada(diametros * 1e6, phi_i.tolist(), rho_s, rho_l, mu * 1000, D / 0.0254, e_D, v, A, B, B_linha, phi_total, 3, Cvmax) * 1000 * fator_perda
        for v in velocidades
    ]
    perdas_agua = [
        wasp_mod_aprimorada(diametros * 1e6, phi_i.tolist(), rho_s, rho_l, mu * 1000, D / 0.0254, e_D, v, A, B, B_linha, phi_total, 17, Cvmax) * 1000
        for v in velocidades
    ]
    cv_veiculos = [
        wasp_mod_aprimorada(diametros * 1e6, phi_i.tolist(), rho_s, rho_l, mu * 1000, D / 0.0254, e_D, v, A, B, B_linha, phi_total, 4, Cvmax)
        for v in velocidades
    ]

    transicao_laminar_turbulento = None
    if np.isfinite(Uc_bing) and Uc_bing > 0:
        perda_transicao = wasp_mod_aprimorada(
            diametros * 1e6, phi_i.tolist(), rho_s, rho_l, mu * 1000, D / 0.0254,
            e_D, Uc_bing, A, B, B_linha, phi_total, 1, Cvmax
        ) * 1000 * fator_perda
        transicao_laminar_turbulento = {
            "velocidade": float(Uc_bing),
            "perda_carga": float(perda_transicao),
            "regime_antes": "Laminar",
            "regime_depois": "Turbulento",
        }

    limite_hom_het = None
    frac_arraste = np.array(perdas_arraste) / np.maximum(np.array(perdas_carga), 1e-12)
    for idx_limite, frac in enumerate(frac_arraste):
        if frac <= 0.10:
            vel_limite = float(velocidades[idx_limite])
            if transicao_laminar_turbulento and vel_limite < transicao_laminar_turbulento["velocidade"]:
                break
            limite_hom_het = {
                "velocidade": vel_limite,
                "perda_carga": float(perdas_carga[idx_limite]),
                "perda_arraste": float(perdas_arraste[idx_limite]),
                "frac_arraste_percent": float(frac * 100),
            }
            break

    c0ca_series = []
    for idx, d in enumerate(diametros):
        y = [
            100 * wasp_mod_aprimorada(diametros * 1e6, phi_i.tolist(), rho_s, rho_l, mu * 1000, D / 0.0254, e_D, v, A, B, B_linha, phi_total, 6, Cvmax)[idx]
            for v in velocidades
        ]
        c0ca_series.append({"diametro_um": float(d * 1e6), "valores": y})

    def perfil_por_classe_em_yD(yD):
        yStar = 2 * yD - 1
        R = D / 2
        u_star = u_estrela(U, F)
        el = calcular_el(yD, R, u_star)
        es = beta * el
        zeta = es / (R * u_star) if R > 0 and u_star > 0 else 0
        N = len(diametros)
        phi_j_abs = np.zeros(N)
        vArr = np.zeros(N)
        KArr = np.zeros(N)
        EKArr = np.zeros(N)
        for j in range(N):
            Ut0 = velterminal_levenspiel(diametros[j], rho_s, rho_l, mu)
            Re_particula = (diametros[j] * rho_l * Ut0) / mu
            Z = z_param(diametros[j], D, Re_particula)
            Utj = utj_corrigido(Ut0, phi_total, Z)
            Kj = calcular_kj(Utj, u_star, zeta)
            EKj = ekj_aproximado(Kj)
            vj = calcular_vj(phi_i[j], phi_total)
            vArr[j] = vj
            KArr[j] = Kj
            EKArr[j] = EKj
        for j in range(N):
            phi_j_abs[j] = phi_j_y(yStar, vArr[j], KArr[j], EKArr[j], vArr, KArr, EKArr)
        return phi_j_abs

    def phi_total_em_yD(yD):
        idx_y = np.argmin(np.abs(df["y/D"].values - yD))
        return df["phi_total"].values[idx_y]

    def acumulado_passante_granulometria(phi_j_abs, phi_total_elev):
        acumulado = []
        soma = 0
        for val in phi_j_abs:
            if phi_total_elev <= 0:
                acumulado.append(0)
            else:
                acumulado.append(100 * (1 - soma / phi_total_elev))
            soma += val
        return acumulado

    phi_y05 = perfil_por_classe_em_yD(0.05)
    phi_y50 = perfil_por_classe_em_yD(0.50)
    phi_y95 = perfil_por_classe_em_yD(0.95)

    passante_05 = acumulado_passante_granulometria(phi_y05, phi_total_em_yD(0.05))
    passante_50 = acumulado_passante_granulometria(phi_y50, phi_total_em_yD(0.50))
    passante_95 = acumulado_passante_granulometria(phi_y95, phi_total_em_yD(0.95))

    passante_input = []
    soma_input = 0
    for val in phi_i:
        passante_input.append(100 * (1 - soma_input / phi_total))
        soma_input += val

    diametros_um_inv = (diametros * 1e6)[::-1].tolist()

    c0ca_total_percent = 100 * Cvveiculo / phi_total if phi_total > 0 else 0
    if dados["modelo_escoamento"] == "homogeneo":
        return calcular_homogeneo_web(dados, {"c0ca_total_percent": c0ca_total_percent})

    tabela_resultados = [
        {"simbolo": "nₐ", "descricao": "Interações acoplamento", "valor": iteracoes_acoplamento, "unidade": "-"},
        {"simbolo": "nₘ", "descricao": "Interações internas modelo", "valor": n_modelo, "unidade": "-"},
        {"simbolo": "βₑ", "descricao": "Erro final β", "valor": erro_beta, "unidade": "-"},
        {"simbolo": "fₑ", "descricao": "Erro final f", "valor": erro_F, "unidade": "-"},
        {"simbolo": "φ₀,₁", "descricao": "Concentração Volumétrica em y/D=0,1", "valor": phi_ref * 100, "unidade": "%"},
        {"simbolo": "φₘₐₓ", "descricao": "Concentração compactação máxima", "valor": Cvmax * 100, "unidade": "%"},
        {"simbolo": "ΔP", "descricao": "Perda de carga total polpa", "valor": DeltaP, "unidade": "m/km"},
        {"simbolo": "ΔP", "descricao": "Perda de carga total polpa", "valor": DeltaP * Rom * 9.80665 / 1e5, "unidade": "bar/km"},
        {"simbolo": "φᵥ", "descricao": "Concentração Volumétrica Veículo", "valor": Cvveiculo * 100, "unidade": "%"},
        {"simbolo": "φ<sub>w</sub>", "descricao": "Concentração mássica da polpa", "valor": Cw * 100, "unidade": "%"},
        {"simbolo": "τ₀", "descricao": "Tensão de Escoamento", "valor": Tau0_Pa, "unidade": "Pa"},
        {"simbolo": "τ₀ᵥ", "descricao": "Tensão de Escoamento veículo", "valor": Tau0V_Pa, "unidade": "Pa"},
        {"simbolo": "ηₘ", "descricao": "Coeficiente de Rigidez Polpa ajustado pelo fluido", "valor": Eta_ajustada, "unidade": "cP"},
        {"simbolo": "ηᵥ", "descricao": "Coeficiente de Rigidez Veículo ajustado pelo fluido", "valor": EtaV_ajustada, "unidade": "cP"},
        {"simbolo": "μₘ", "descricao": "Viscosidade Efetiva Polpa", "valor": Mis * 1000, "unidade": "cP"},
        {"simbolo": "μᵥ", "descricao": "Viscosidade Efetiva Veículo", "valor": MisV * 1000, "unidade": "cP"},
        {"simbolo": "β", "descricao": "Difusividade Adimensional final", "valor": Beta_final, "unidade": "-"},
        {"simbolo": "f", "descricao": "Fator de atrito final", "valor": F, "unidade": "-"},
        {"simbolo": "ρₘ", "descricao": "Densidade da Polpa", "valor": Rom, "unidade": "kg/m³"},
        {"simbolo": "ρₘᵥ", "descricao": "Densidade do Veículo", "valor": RomV, "unidade": "kg/m³"},
        {"simbolo": "ΔPᵥ", "descricao": "Perda de carga veículo", "valor": DeltaPveiculo, "unidade": "m/km"},
        {"simbolo": "C/Ca total", "descricao": "Sólidos suspensos / sólidos totais", "valor": c0ca_total_percent, "unidade": "%"},
        {"simbolo": "h/D", "descricao": "Altura relativa do depósito", "valor": altura_rel_deposito, "unidade": "-"},
    ]

    avisos = [
        _(
            "Nota técnica: o ponto operacional é calculado com o acoplamento completo do Wasp modificado. "
            "Os demais pontos das curvas são aproximações que utilizam o Cvmax convergido da condição operacional, "
            "sem repetir o acoplamento completo para cada velocidade."
        )
    ]
    if Cvveiculo > 0.8 * phi_total:
        avisos.append("Critério de escoamento homogêneo atingido: sólidos suspensos acima de 80%.")
    falhas_convergencia = []
    if iteracoes_acoplamento >= dados["max_iter"] and max(erro_beta, erro_F) >= dados["erro"]:
        falhas_convergencia.append(_("acoplamento Wasp modificado"))
    if n_modelo >= 100:
        falhas_convergencia.append("Wasp modificado")
    if falhas_convergencia:
        avisos.append(
            _("Atenção: uma ou mais iterações atingiram o limite máximo sem convergência completa.")
            + " "
            + _("Iteração sem convergência completa: %(iteracoes)s.")
            % {"iteracoes": ", ".join(falhas_convergencia)}
        )

    _validar_resultados_criticos(
        perda_carga_total=DeltaP,
        perda_carga_veiculo=DeltaPveiculo,
        fator_atrito=F,
        beta=Beta_final,
        concentracao_veiculo=Cvveiculo,
        concentracao_massica=Cw,
        densidade_polpa=Rom,
        densidade_veiculo=RomV,
        cvmax=Cvmax,
    )

    resultado = {
        "entradas": dados,
        "resumo": {
            "modelo_escoamento": "heterogeneo",
            "velocidade_operacao": U,
            "perda_carga_operacao": DeltaP,
            "perda_carga_bar_km": DeltaP * Rom * 9.80665 / 1e5,
            "densidade_polpa": Rom,
            "perda_carga_veiculo": DeltaPveiculo,
            "phi_w_percent": Cw * 100,
            "beta_final": Beta_final,
            "cv_veiculo": Cvveiculo,
            "cv_deposito": cv_deposito,
            "c0ca_total_percent": c0ca_total_percent,
            "altura_rel_deposito": altura_rel_deposito,
            "iteracoes_acoplamento": iteracoes_acoplamento,
            "phi_ref_yD_01": phi_ref,
            "cvmax": Cvmax,
        },
        "avisos": avisos,
        "tabela_resultados": tabela_resultados,
        "graficos": {
            "concentracao_vertical": {
                "x_phi": df["phi_total"].tolist(),
                "yD": df["y/D"].tolist(),
                "phi_ref": phi_ref,
                "phi_ref_yD": 0.1,
                "altura_deposito": altura_rel_deposito,
            },
            "perda_carga": {
                "velocidades": velocidades.tolist(),
                "polpa": perdas_carga,
                "arraste": perdas_arraste,
                "agua": perdas_agua,
                "operacao_x": U,
                "operacao_y": DeltaP,
                "limite_hom_het": limite_hom_het,
                "transicao_laminar_turbulento": transicao_laminar_turbulento,
            },
            "cv_veiculo": {
                "velocidades": velocidades.tolist(),
                "percentual": [100 * v / phi_total for v in cv_veiculos],
                "operacao_x": U,
                "operacao_y": c0ca_total_percent,
            },
            "c0ca": {
                "velocidades": velocidades.tolist(),
                "series": c0ca_series,
                "operacao_x": U,
                "operacao_total_y": c0ca_total_percent,
            },
            "granulometria_concentracao": {
                "diametros_um": diametros_um_inv,
                "yD_005": phi_y05[::-1].tolist(),
                "yD_050": phi_y50[::-1].tolist(),
                "yD_095": phi_y95[::-1].tolist(),
            },
            "granulometria_passante_modelo": {
                "diametros_um": diametros_um_inv,
                "yD_005": list(reversed(passante_05)),
                "yD_050": list(reversed(passante_50)),
                "yD_095": list(reversed(passante_95)),
            },
            "granulometria_passante_entrada": {
                "diametros_um": diametros_um_inv,
                "passante": list(reversed(passante_input)),
            },
        },
    }
    return _json_safe(resultado)
