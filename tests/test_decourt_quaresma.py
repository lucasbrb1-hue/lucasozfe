import math
import unittest

from spt_piles import decourt_quaresma as dq
from spt_piles.models import PileGeometry, SPTProfile


def uniform_clay_profile(n_value: int = 10, max_depth: int = 10) -> SPTProfile:
    profile = SPTProfile()
    for depth in range(1, max_depth + 1):
        profile.add(depth, n_value, "argila")
    return profile


class TestDecourtQuaresma(unittest.TestCase):
    def test_hand_calculation_escavada_clay(self):
        profile = uniform_clay_profile(n_value=10, max_depth=10)
        geometry = PileGeometry(diameter_cm=40)
        result = dq.calc_at_depth(profile, geometry, "escavada", depth_m=8.0, safety_factor=2.0)

        # Np = média(N7, N8, N9) = 10 ; K(argila) = 120 kPa ; alpha(escavada) = 0.85
        expected_rp = 0.85 * 120 * 10
        expected_qp = expected_rp * geometry.area_m2
        self.assertAlmostEqual(result.qp_kn, expected_qp, places=3)

        # Nl = média(N1..N8) = 10 (dentro de [3,50]) ; ql=10*(10/3+1) ; beta=0.80
        expected_rl = 0.80 * 10 * (10 / 3 + 1)
        expected_ql = expected_rl * geometry.perimeter_m * 8.0
        self.assertAlmostEqual(result.ql_kn, expected_ql, places=3)

        self.assertAlmostEqual(result.qu_kn, expected_qp + expected_ql, places=3)
        self.assertAlmostEqual(result.qadm_kn, (expected_qp + expected_ql) / 2.0, places=3)

    def test_qu_increases_with_depth(self):
        profile = uniform_clay_profile(n_value=12, max_depth=15)
        geometry = PileGeometry(diameter_cm=50)
        results = dq.calc_profile(profile, geometry, "helice_continua", safety_factor=2.0, min_depth_m=1.0)
        qu_values = [r.qu_kn for r in results]
        self.assertEqual(qu_values, sorted(qu_values))
        self.assertTrue(all(v > 0 for v in qu_values))

    def test_qu_increases_with_n_spt(self):
        geometry = PileGeometry(diameter_cm=40)
        low_n_profile = uniform_clay_profile(n_value=5, max_depth=10)
        high_n_profile = uniform_clay_profile(n_value=25, max_depth=10)

        low = dq.calc_at_depth(low_n_profile, geometry, "escavada", depth_m=10.0)
        high = dq.calc_at_depth(high_n_profile, geometry, "escavada", depth_m=10.0)
        self.assertGreater(high.qu_kn, low.qu_kn)

    def test_n_clip_applied_to_shaft_average(self):
        profile = SPTProfile()
        # valores extremos devem ser limitados a [3, 50] antes da média do fuste
        for depth, n in [(1, 1), (2, 60), (3, 10)]:
            profile.add(depth, n, "areia")
        geometry = PileGeometry(diameter_cm=40)
        result = dq.calc_at_depth(profile, geometry, "pre_moldada", depth_m=3.0)
        expected_nl = (3 + 50 + 10) / 3  # 1 -> clip 3 ; 60 -> clip 50 ; 10 -> 10
        self.assertAlmostEqual(result.nl_shaft, expected_nl, places=6)

    def test_invalid_profile_raises(self):
        empty_profile = SPTProfile()
        geometry = PileGeometry(diameter_cm=40)
        with self.assertRaises(ValueError):
            dq.calc_at_depth(empty_profile, geometry, "escavada", depth_m=5.0)

    def test_invalid_safety_factor_raises(self):
        profile = uniform_clay_profile()
        geometry = PileGeometry(diameter_cm=40)
        with self.assertRaises(ValueError):
            dq.calc_at_depth(profile, geometry, "escavada", depth_m=5.0, safety_factor=0)


if __name__ == "__main__":
    unittest.main()
