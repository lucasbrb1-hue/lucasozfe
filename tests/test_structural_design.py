import math
import unittest

from spt_piles.models import PileGeometry
from spt_piles.structural_design import (
    ALPHA_C,
    GAMMA_C,
    GAMMA_S,
    build_interaction_diagram,
    check_flexo_compression,
    design_shear,
    moment_capacity_at_n,
)


class TestInteractionDiagram(unittest.TestCase):
    def test_nrd_is_monotonic_nondecreasing(self):
        geometry = PileGeometry(diameter_cm=50)
        diagram = build_interaction_diagram(
            geometry, cover_cm=4.0, stirrup_diameter_mm=6.3, bar_diameter_mm=20.0, n_bars=10,
            fck_mpa=25.0, fyk_mpa=500.0,
        )
        for a, b in zip(diagram.nrd_kn, diagram.nrd_kn[1:]):
            self.assertGreaterEqual(b, a - 1e-6)

    def test_pure_compression_limit_matches_theoretical_formula(self):
        geometry = PileGeometry(diameter_cm=50)
        fck, fyk = 25.0, 500.0
        n_bars, bar_diameter_mm = 10, 20.0
        diagram = build_interaction_diagram(
            geometry, cover_cm=4.0, stirrup_diameter_mm=6.3, bar_diameter_mm=bar_diameter_mm,
            n_bars=n_bars, fck_mpa=fck, fyk_mpa=fyk,
        )

        radius_cm = geometry.diameter_cm / 2.0
        ac_cm2 = math.pi * radius_cm ** 2
        bar_area_cm2 = math.pi * (bar_diameter_mm / 20.0) ** 2
        as_total_cm2 = n_bars * bar_area_cm2
        fcd = fck / GAMMA_C
        fyd = fyk / GAMMA_S
        n_max_theoretical_kn = ALPHA_C * fcd * (ac_cm2 - as_total_cm2) * 0.1 + fyd * as_total_cm2 * 0.1

        n_max_numeric = diagram.nrd_kn[-1]
        self.assertAlmostEqual(n_max_numeric, n_max_theoretical_kn, delta=0.01 * n_max_theoretical_kn)

    def test_moment_capacity_drops_to_near_zero_at_pure_compression(self):
        geometry = PileGeometry(diameter_cm=50)
        diagram = build_interaction_diagram(
            geometry, cover_cm=4.0, stirrup_diameter_mm=6.3, bar_diameter_mm=20.0, n_bars=10,
            fck_mpa=25.0, fyk_mpa=500.0,
        )
        self.assertLess(diagram.mrd_knm[-1], 1.0)

    def test_more_reinforcement_increases_capacity(self):
        geometry = PileGeometry(diameter_cm=50)
        small = check_flexo_compression(
            geometry, cover_cm=4.0, stirrup_diameter_mm=6.3, bar_diameter_mm=16.0, n_bars=8,
            fck_mpa=25.0, fyk_mpa=500.0, n_design_kn=800.0, m_design_knm=150.0,
        )
        large = check_flexo_compression(
            geometry, cover_cm=4.0, stirrup_diameter_mm=6.3, bar_diameter_mm=25.0, n_bars=14,
            fck_mpa=25.0, fyk_mpa=500.0, n_design_kn=800.0, m_design_knm=150.0,
        )
        self.assertGreater(large.m_capacity_knm, small.m_capacity_knm)
        self.assertLess(large.utilization, small.utilization)

    def test_adequate_flag_reflects_utilization(self):
        geometry = PileGeometry(diameter_cm=50)
        ok = check_flexo_compression(
            geometry, cover_cm=4.0, stirrup_diameter_mm=6.3, bar_diameter_mm=25.0, n_bars=16,
            fck_mpa=25.0, fyk_mpa=500.0, n_design_kn=800.0, m_design_knm=150.0,
        )
        self.assertTrue(ok.adequate)

        inadequate = check_flexo_compression(
            geometry, cover_cm=4.0, stirrup_diameter_mm=6.3, bar_diameter_mm=8.0, n_bars=6,
            fck_mpa=25.0, fyk_mpa=500.0, n_design_kn=800.0, m_design_knm=800.0,
        )
        self.assertFalse(inadequate.adequate)

    def test_moment_capacity_none_beyond_pure_compression_capacity(self):
        geometry = PileGeometry(diameter_cm=30)
        diagram = build_interaction_diagram(
            geometry, cover_cm=4.0, stirrup_diameter_mm=6.3, bar_diameter_mm=10.0, n_bars=6,
            fck_mpa=20.0, fyk_mpa=500.0,
        )
        self.assertIsNone(moment_capacity_at_n(diagram, diagram.nrd_kn[-1] * 2))
        self.assertIsNone(moment_capacity_at_n(diagram, -10.0))

    def test_invalid_geometry_raises(self):
        geometry = PileGeometry(diameter_cm=20)
        with self.assertRaises(ValueError):
            build_interaction_diagram(
                geometry, cover_cm=8.0, stirrup_diameter_mm=6.3, bar_diameter_mm=32.0, n_bars=10,
                fck_mpa=25.0, fyk_mpa=500.0,
            )


class TestShearDesign(unittest.TestCase):
    def test_low_shear_needs_no_extra_stirrups(self):
        geometry = PileGeometry(diameter_cm=50)
        result = design_shear(geometry, v_design_kn=50.0, stirrup_diameter_mm=6.3, fck_mpa=25.0)
        self.assertTrue(result.crushing_ok)
        self.assertIsNone(result.required_spacing_cm)

    def test_moderate_shear_requires_spacing(self):
        geometry = PileGeometry(diameter_cm=50)
        result = design_shear(geometry, v_design_kn=400.0, stirrup_diameter_mm=6.3, fck_mpa=25.0)
        self.assertTrue(result.crushing_ok)
        self.assertIsNotNone(result.required_spacing_cm)
        self.assertGreater(result.required_spacing_cm, 0)

    def test_excessive_shear_fails_crushing_check(self):
        geometry = PileGeometry(diameter_cm=30)
        result = design_shear(geometry, v_design_kn=1000.0, stirrup_diameter_mm=6.3, fck_mpa=20.0)
        self.assertFalse(result.crushing_ok)
        self.assertIsNone(result.required_spacing_cm)
        self.assertTrue(any("Vrd2" in w for w in result.warnings))

    def test_higher_shear_needs_tighter_spacing(self):
        geometry = PileGeometry(diameter_cm=50)
        low = design_shear(geometry, v_design_kn=200.0, stirrup_diameter_mm=6.3, fck_mpa=25.0)
        high = design_shear(geometry, v_design_kn=500.0, stirrup_diameter_mm=6.3, fck_mpa=25.0)
        self.assertLess(high.required_spacing_cm, low.required_spacing_cm)


if __name__ == "__main__":
    unittest.main()
