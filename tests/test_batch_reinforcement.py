import unittest

from spt_piles import pile_group as pg
from spt_piles.loads import FoundationLoad, LoadCombination
from spt_piles.models import PileGeometry


class TestComputeBatchReinforcement(unittest.TestCase):
    def test_without_moment_falls_back_to_minimum_design(self):
        geometry = PileGeometry(diameter_cm=40)
        loads = [FoundationLoad("P1", 300.0), FoundationLoad("P2", 500.0)]
        result = pg.compute_batch_reinforcement(loads, geometry)
        self.assertIsNone(result.structural)
        self.assertIsNotNone(result.longitudinal)

    def test_with_moment_populates_structural_and_governing_pile(self):
        geometry = PileGeometry(diameter_cm=50)
        loads = [
            FoundationLoad("P1", 300.0, moment_kn_m=10.0),
            FoundationLoad("P2", 800.0, moment_kn_m=180.0),  # mais exigente
            FoundationLoad("P3", 400.0, moment_kn_m=30.0),
        ]
        result = pg.compute_batch_reinforcement(loads, geometry)
        self.assertIsNotNone(result.structural)
        self.assertIsNotNone(result.longitudinal)
        self.assertTrue(result.structural.flexo_check.adequate)

    def test_reinforcement_adequate_for_every_pile_individually(self):
        from spt_piles.structural_design import check_flexo_compression

        geometry = PileGeometry(diameter_cm=50)
        loads = [
            FoundationLoad("P1", 300.0, moment_kn_m=10.0),
            FoundationLoad("P2", 800.0, moment_kn_m=180.0),
            FoundationLoad("P3", 400.0, moment_kn_m=30.0),
        ]
        result = pg.compute_batch_reinforcement(loads, geometry, load_factor=1.4)
        self.assertIsNotNone(result.longitudinal)

        for load in loads:
            check = check_flexo_compression(
                geometry, cover_cm=5.0, stirrup_diameter_mm=result.stirrup_diameter_mm,
                bar_diameter_mm=result.longitudinal.bar_diameter_mm, n_bars=result.longitudinal.n_bars,
                fck_mpa=30.0, fyk_mpa=500.0,
                n_design_kn=1.4 * load.load_per_pile_kn, m_design_knm=1.4 * load.moment_per_pile_knm,
            )
            self.assertTrue(check.adequate, f"estaca {load.element_id} deveria ser adequada")

    def test_divides_moment_by_n_piles_in_block(self):
        geometry = PileGeometry(diameter_cm=50)
        loads_single = [FoundationLoad("P1", 300.0, n_piles=1, moment_kn_m=60.0)]
        loads_block = [FoundationLoad("B1", 900.0, n_piles=3, moment_kn_m=180.0)]  # 300kN/60kNm por estaca
        r1 = pg.compute_batch_reinforcement(loads_single, geometry)
        r2 = pg.compute_batch_reinforcement(loads_block, geometry)
        self.assertAlmostEqual(r1.structural.n_design_kn, r2.structural.n_design_kn)
        self.assertAlmostEqual(r1.structural.m_design_knm, r2.structural.m_design_knm)

    def test_shear_reduces_stirrup_spacing(self):
        geometry = PileGeometry(diameter_cm=50)
        loads = [FoundationLoad("P1", 800.0, moment_kn_m=50.0, shear_kn=250.0)]
        result = pg.compute_batch_reinforcement(loads, geometry, stirrup_spacing_body_cm=20.0)
        self.assertIsNotNone(result.structural.shear)
        self.assertLessEqual(result.stirrup_spacing_body_cm, 20.0)

    def test_empty_loads_raises(self):
        geometry = PileGeometry(diameter_cm=40)
        with self.assertRaises(ValueError):
            pg.compute_batch_reinforcement([], geometry)

    def test_infeasible_moment_yields_no_longitudinal_and_warning(self):
        geometry = PileGeometry(diameter_cm=25)
        loads = [FoundationLoad("P1", 200.0, moment_kn_m=3000.0)]
        result = pg.compute_batch_reinforcement(loads, geometry)
        self.assertIsNone(result.longitudinal)
        self.assertTrue(any("Nenhuma combinação" in w for w in result.warnings))

    def test_envelope_checks_all_combinations_not_just_max_n(self):
        # Réplica do caso real que motivou a envoltória de combinações
        # (relatório de "Esforços nas Fundações por Elementos" do Eberick):
        # a combinação de maior N nem sempre é a mais exigente para a
        # armadura - uma combinação com N bem menor mas M bem maior pode
        # governar. A busca deve verificar TODAS as combinações e apontar a
        # mais exigente como governante, não assumir que é a de maior N.
        geometry = PileGeometry(diameter_cm=40)
        loads = [
            FoundationLoad(
                "B1", characteristic_load_kn=300.0, n_piles=1,
                combinations=[
                    LoadCombination(label="ALTO_N_BAIXO_M", n_kn=300.0, moment_x_knm=5.0),
                    LoadCombination(label="BAIXO_N_ALTO_M", n_kn=100.0, moment_x_knm=45.0),
                ],
            ),
        ]
        result = pg.compute_batch_reinforcement(loads, geometry)
        self.assertIsNotNone(result.longitudinal)
        self.assertTrue(any("BAIXO_N_ALTO_M" in w for w in result.warnings))
        self.assertFalse(any("ALTO_N_BAIXO_M" in w for w in result.warnings))

    def test_envelope_negative_n_combinations_are_skipped(self):
        # O diagrama N-M atual não cobre tração (N<0) - combinações de
        # levantamento devem ser ignoradas na busca, não travar o cálculo.
        geometry = PileGeometry(diameter_cm=40)
        loads = [
            FoundationLoad(
                "B1", characteristic_load_kn=300.0, n_piles=1,
                combinations=[
                    LoadCombination(label="TRACAO", n_kn=-50.0, moment_x_knm=5.0),
                    LoadCombination(label="COMPRESSAO", n_kn=300.0, moment_x_knm=20.0),
                ],
            ),
        ]
        result = pg.compute_batch_reinforcement(loads, geometry)
        self.assertIsNotNone(result.longitudinal)
        self.assertTrue(any("COMPRESSAO" in w for w in result.warnings))

    def test_envelope_shear_uses_worst_case_across_combinations(self):
        geometry = PileGeometry(diameter_cm=50)
        loads = [
            FoundationLoad(
                "B1", characteristic_load_kn=800.0, n_piles=1,
                combinations=[
                    LoadCombination(label="C1", n_kn=800.0, moment_x_knm=50.0, shear_x_kn=50.0),
                    LoadCombination(label="C2", n_kn=600.0, moment_x_knm=40.0, shear_x_kn=250.0),
                ],
            ),
        ]
        result = pg.compute_batch_reinforcement(loads, geometry)
        self.assertIsNotNone(result.structural.shear)
        self.assertAlmostEqual(result.structural.v_design_kn, 1.4 * 250.0)

    def test_fixed_bar_diameter_without_moment(self):
        geometry = PileGeometry(diameter_cm=40)
        loads = [FoundationLoad("P1", 300.0), FoundationLoad("P2", 500.0)]
        result = pg.compute_batch_reinforcement(loads, geometry, bar_diameter_mm=12.5)
        self.assertIsNotNone(result.longitudinal)
        self.assertAlmostEqual(result.longitudinal.bar_diameter_mm, 12.5)

    def test_fixed_bar_diameter_with_moment(self):
        geometry = PileGeometry(diameter_cm=50)
        loads = [
            FoundationLoad("P1", 300.0, moment_kn_m=10.0),
            FoundationLoad("P2", 800.0, moment_kn_m=180.0),
        ]
        result = pg.compute_batch_reinforcement(loads, geometry, bar_diameter_mm=20.0)
        self.assertIsNotNone(result.longitudinal)
        self.assertAlmostEqual(result.longitudinal.bar_diameter_mm, 20.0)

    def test_fixed_bar_diameter_too_small_yields_no_longitudinal(self):
        geometry = PileGeometry(diameter_cm=25)
        loads = [FoundationLoad("P1", 200.0, moment_kn_m=3000.0)]
        result = pg.compute_batch_reinforcement(loads, geometry, bar_diameter_mm=8.0)
        self.assertIsNone(result.longitudinal)
        self.assertTrue(any("bitola fixada" in w for w in result.warnings))

    def test_invalid_fixed_bar_diameter_raises(self):
        geometry = PileGeometry(diameter_cm=50)
        loads = [FoundationLoad("P1", 300.0, moment_kn_m=10.0)]
        with self.assertRaises(ValueError):
            pg.compute_batch_reinforcement(loads, geometry, bar_diameter_mm=0)


if __name__ == "__main__":
    unittest.main()
