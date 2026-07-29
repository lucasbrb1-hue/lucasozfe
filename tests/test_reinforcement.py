import unittest

from spt_piles.models import PileGeometry
from spt_piles.reinforcement import default_rho_min_pct, design_reinforcement, effective_armor_length_m

DEFAULT_RHO_40CM = default_rho_min_pct(40)


class TestReinforcement(unittest.TestCase):
    def test_default_rho_min_thresholds(self):
        self.assertEqual(default_rho_min_pct(20), 0.8)
        self.assertEqual(default_rho_min_pct(25), 0.8)
        self.assertEqual(default_rho_min_pct(40), 0.6)
        self.assertEqual(default_rho_min_pct(60), 0.6)
        self.assertEqual(default_rho_min_pct(80), 0.5)

    def test_design_meets_as_min(self):
        geometry = PileGeometry(diameter_cm=40)
        result = design_reinforcement(geometry, axial_load_kn=500.0)

        self.assertAlmostEqual(
            result.as_min_cm2, (DEFAULT_RHO_40CM / 100.0) * result.gross_area_cm2, places=6
        )
        self.assertIsNotNone(result.longitudinal)
        self.assertGreaterEqual(result.longitudinal.as_provided_cm2, result.as_min_cm2)
        self.assertGreaterEqual(result.longitudinal.n_bars, 6)

    def test_larger_pile_lower_rho(self):
        small = design_reinforcement(PileGeometry(diameter_cm=30), axial_load_kn=500.0)
        large = design_reinforcement(PileGeometry(diameter_cm=80), axial_load_kn=500.0)
        self.assertGreater(small.rho_min_pct, large.rho_min_pct)

    def test_custom_rho_min_overrides_default(self):
        geometry = PileGeometry(diameter_cm=40)
        result = design_reinforcement(geometry, axial_load_kn=500.0, rho_min_pct=1.0)
        self.assertEqual(result.rho_min_pct, 1.0)
        self.assertAlmostEqual(result.as_min_cm2, 0.01 * result.gross_area_cm2, places=6)

    def test_confinement_length_scales_with_diameter(self):
        geometry = PileGeometry(diameter_cm=50)
        result = design_reinforcement(geometry, axial_load_kn=500.0, confinement_length_factor=3.0)
        self.assertAlmostEqual(result.confinement_length_m, 3.0 * 0.5, places=6)

    def test_invalid_diameter_raises(self):
        with self.assertRaises(ValueError):
            design_reinforcement(PileGeometry(diameter_cm=0), axial_load_kn=500.0)

    def test_default_armor_length_is_none_full_length(self):
        geometry = PileGeometry(diameter_cm=40)
        result = design_reinforcement(geometry, axial_load_kn=500.0)
        self.assertIsNone(result.requested_armor_length_m)
        self.assertEqual(effective_armor_length_m(result, pile_depth_m=12.0), 12.0)

    def test_partial_armor_length_is_stored_and_capped_by_pile_depth(self):
        geometry = PileGeometry(diameter_cm=40)
        result = design_reinforcement(geometry, axial_load_kn=500.0, armor_length_m=6.0)
        self.assertEqual(result.requested_armor_length_m, 6.0)
        # profundidade da estaca maior que o pedido -> usa o pedido
        self.assertEqual(effective_armor_length_m(result, pile_depth_m=12.0), 6.0)
        # profundidade da estaca menor que o pedido -> nunca ultrapassa o fundo da estaca
        self.assertEqual(effective_armor_length_m(result, pile_depth_m=4.0), 4.0)

    def test_partial_armor_length_emits_warning(self):
        geometry = PileGeometry(diameter_cm=40)
        result = design_reinforcement(geometry, axial_load_kn=500.0, armor_length_m=6.0)
        self.assertTrue(any("Armadura parcial" in w for w in result.warnings))

    def test_armor_length_below_confinement_zone_warns(self):
        geometry = PileGeometry(diameter_cm=60)  # confinamento = 3 * 0.6 = 1.8 m
        result = design_reinforcement(geometry, axial_load_kn=500.0, armor_length_m=1.0)
        self.assertTrue(any("zona de confinamento" in w for w in result.warnings))

    def test_invalid_armor_length_raises(self):
        geometry = PileGeometry(diameter_cm=40)
        with self.assertRaises(ValueError):
            design_reinforcement(geometry, axial_load_kn=500.0, armor_length_m=0)


if __name__ == "__main__":
    unittest.main()
