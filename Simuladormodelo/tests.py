from django.test import SimpleTestCase

from .codigo.calculos import DEFAULT_ENTRADAS
from .codigo.four_cm_engine import absoluta_para_passante, cv_to_cw, cw_to_cv, executar_4cm
from .codigo.vscalc_engine import executar_vscalc


class IntegracaoModelosTests(SimpleTestCase):
    def test_conversao_cv_cw_retorna_cv_original(self):
        cv = 0.141
        cw = cv_to_cw(cv, 2610, 1000)
        self.assertAlmostEqual(cw_to_cv(cw, 2610, 1000), cv, places=10)

    def test_psd_absoluta_para_passante_ordenada(self):
        psd = absoluta_para_passante([250, 149, 105, 74, 53, 37, 25, 20, 1], [5.07, 12.47, 12.99, 11.05, 9.699997, 6.09, 6.66, 3.760002, 32.21])
        diametros = [p["d"] for p in psd]
        passantes = [p["p"] for p in psd]
        self.assertEqual(diametros, sorted(diametros))
        self.assertAlmostEqual(passantes[0], 0.0)
        self.assertAlmostEqual(passantes[-1], 1.0)
        self.assertTrue(all(a <= b for a, b in zip(passantes, passantes[1:])))

    def test_psd_rejeita_soma_diferente_de_100(self):
        with self.assertRaises(ValueError):
            absoluta_para_passante([10, 100], [40, 40])

    def test_4cm_calcula_curva_e_componentes(self):
        resultado = executar_4cm(DEFAULT_ENTRADAS)
        self.assertTrue(resultado["converged"])
        self.assertGreater(resultado["results"]["headloss_m_polpa_km"], 0)
        self.assertEqual(len(resultado["graph"]["velocidades"]), 60)
        self.assertAlmostEqual(sum(c["fraction"] for c in resultado["components"]), 1.0, places=6)

    def test_4cm_sem_xp_nao_interrompe(self):
        entradas = {**DEFAULT_ENTRADAS, "diametros_um": [1, 10], "proporcoes_percent": [50, 50]}
        resultado = executar_4cm(entradas)
        self.assertEqual(resultado["results"]["Xp"], 0)
        self.assertGreaterEqual(resultado["results"]["headloss_m_polpa_km"], 0)

    def test_4cm_sem_xh_nao_interrompe(self):
        entradas = {**DEFAULT_ENTRADAS, "diametros_um": [10, 20], "proporcoes_percent": [50, 50]}
        resultado = executar_4cm(entradas)
        self.assertEqual(resultado["results"]["Xh"], 0)
        self.assertIsNone(resultado["results"]["Vsmh"])

    def test_4cm_sem_xs_nao_interrompe(self):
        entradas = {**DEFAULT_ENTRADAS, "diametros_um": [10, 50, 100], "proporcoes_percent": [30, 40, 30]}
        resultado = executar_4cm(entradas)
        self.assertEqual(resultado["results"]["Xs"], 0)
        self.assertIsNone(resultado["results"]["Vsms"])

    def test_vscalc_calcula_resultados_e_graficos(self):
        resultado = executar_vscalc(DEFAULT_ENTRADAS)
        self.assertEqual(resultado["tipo_resultado"], "vscalc")
        self.assertGreater(resultado["resumo"]["vsm"], 0)
        self.assertGreater(resultado["resumo"]["vs"], 0)
        self.assertEqual(len(resultado["graficos"]["vscalc_velocidade"]), 24)
        self.assertEqual(len(resultado["graficos"]["vscalc_diametro"]), 24)
