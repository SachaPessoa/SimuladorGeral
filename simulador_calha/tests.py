from django.test import SimpleTestCase

from .calha_core import calcular_modelo
from .forms import DEFAULT_ENTRADAS, SimulacaoCalhaForm


class RegressaoMotorCalhaTests(SimpleTestCase):
    def test_caso_padrao_permanece_inalterado(self):
        form = SimulacaoCalhaForm(DEFAULT_ENTRADAS)
        self.assertTrue(form.is_valid(), form.errors)
        resultado = calcular_modelo(form.dados_motor())
        self.assertAlmostEqual(resultado["final"]["Q_m3h"], 199.99993988317894, places=5)
        self.assertAlmostEqual(resultado["final"]["U"], 2.9239146003231062, places=8)
        self.assertAlmostEqual(resultado["final"]["h"], 0.09500198612213134, places=8)
        self.assertEqual(resultado["regime_final"], "rugoso")


class GeometriasInterfaceTests(SimpleTestCase):
    def dados(self, **changes):
        dados = {**DEFAULT_ENTRADAS, **changes}
        return SimulacaoCalhaForm(dados)

    def test_retangular_forca_m_zero(self):
        form = self.dados(geometria="retangular", m=3)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.dados_motor()["m"], 0)
        self.assertEqual(form.dados_motor()["geometria"], "trapezoidal")

    def test_triangular_forca_b_zero(self):
        form = self.dados(geometria="triangular", b=3, m=1)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.dados_motor()["b"], 0)
        self.assertEqual(form.dados_motor()["geometria"], "trapezoidal")

    def test_trapezoidal_exige_b_e_m_maiores_que_zero(self):
        form = self.dados(geometria="trapezoidal", b=0.2, m=0)
        self.assertFalse(form.is_valid())
        self.assertIn("m", form.errors)


class UnidadesEReologiaTests(SimpleTestCase):
    def test_comprimentos_equivalentes_produzem_mesmo_motor(self):
        metro = SimulacaoCalhaForm(DEFAULT_ENTRADAS)
        milimetro = SimulacaoCalhaForm({
            **DEFAULT_ENTRADAS, "b": 200, "b_unidade": "mm",
            "hmax": 200, "hmax_unidade": "mm", "D": 250, "D_unidade": "mm",
        })
        self.assertTrue(metro.is_valid(), metro.errors)
        self.assertTrue(milimetro.is_valid(), milimetro.errors)
        for chave in ("b", "hmax", "D"):
            self.assertAlmostEqual(metro.dados_motor()[chave], milimetro.dados_motor()[chave])

    def test_reologia_direta_equivale_ao_caso_padrao(self):
        base_form = SimulacaoCalhaForm(DEFAULT_ENTRADAS)
        self.assertTrue(base_form.is_valid(), base_form.errors)
        dados = base_form.dados_motor()
        massa = __import__("simuladores.calha_core", fromlist=["balanco_massa_polpa"]).balanco_massa_polpa(
            dados["rhos"], dados["rhol"], dados["phiw"]
        )
        tau_dyn = dados["A_lab"] * massa["phiv"] ** dados["B_lab"]
        eta_ref = 10 ** (massa["Vr"] * dados["B_linha_lab"])
        direta = SimulacaoCalhaForm({
            **DEFAULT_ENTRADAS, "entrada_reologia": "direta",
            "tau0_direto": tau_dyn, "tau0_unidade": "dyn_cm2",
            "eta_direta": eta_ref, "eta_unidade": "cp",
        })
        self.assertTrue(direta.is_valid(), direta.errors)
        resultado_base = calcular_modelo(dados)
        resultado_direto = calcular_modelo(direta.dados_motor())
        self.assertAlmostEqual(resultado_base["final"]["h"], resultado_direto["final"]["h"], places=8)
        self.assertAlmostEqual(resultado_base["final"]["U"], resultado_direto["final"]["U"], places=8)

    def test_reologia_direta_exige_tau0_positivo(self):
        form = SimulacaoCalhaForm({
            **DEFAULT_ENTRADAS, "entrada_reologia": "direta",
            "tau0_direto": 0, "eta_direta": 2,
        })
        self.assertFalse(form.is_valid())
        self.assertIn("tau0_direto", form.errors)

