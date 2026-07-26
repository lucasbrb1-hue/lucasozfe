import unittest

from spt_piles import aoki_velloso as av
from spt_piles.models import PileGeometry, SPTProfile


def uniform_sand_profile(n_value: int = 10, max_depth: int = 10) -> SPTProfile:
    profile = SPTProfile()
    for depth in range(1, max_depth + 1):
        profile.add(depth, n_value, "areia")
    return profile


class TestAokiVelloso(unittest.TestCase):
    def test_hand_calculation_single_layer(self):
        profile = SPTProfile()
        profile.add(1.0, 10, "areia")
        geometry = PileGeometry(diameter_cm=40)

        result = av.calc_at_depth(profile, geometry, "escavada", depth_m=1.0, safety_factor=2.0)

        # rp = K*Np/F1 ; K(areia)=1.00 MPa=1000 kPa ; F1(escavada)=3.0
        expected_rp = (1000.0 * 10) / 3.0
        expected_qp = expected_rp * geometry.area_m2
        self.assertAlmostEqual(result.qp_kn, expected_qp, places=3)

        # camada única com profundidade 1.0 m (sem vizinhos, thickness = depth)
        expected_rl = (1.4 / 100.0) * 1000.0 * 10 / 6.0
        expected_ql = expected_rl * geometry.perimeter_m * 1.0
        self.assertAlmostEqual(result.ql_kn, expected_ql, places=3)

    def test_qu_increases_with_depth(self):
        profile = uniform_sand_profile(n_value=15, max_depth=12)
        geometry = PileGeometry(diameter_cm=50)
        results = av.calc_profile(profile, geometry, "pre_moldada", safety_factor=2.0, min_depth_m=1.0)
        qu_values = [r.qu_kn for r in results]
        self.assertTrue(all(b >= a - 1e-9 for a, b in zip(qu_values, qu_values[1:])))

    def test_layer_thickness_sums_to_total_depth(self):
        profile = uniform_sand_profile(n_value=10, max_depth=6)
        geometry = PileGeometry(diameter_cm=40)
        # ql deve ser proporcional à profundidade total para perfil uniforme
        result_shallow = av.calc_at_depth(profile, geometry, "escavada", depth_m=3.0)
        result_deep = av.calc_at_depth(profile, geometry, "escavada", depth_m=6.0)
        ratio = result_deep.ql_kn / result_shallow.ql_kn
        self.assertAlmostEqual(ratio, 2.0, places=2)

    def test_invalid_profile_raises(self):
        empty_profile = SPTProfile()
        geometry = PileGeometry(diameter_cm=40)
        with self.assertRaises(ValueError):
            av.calc_at_depth(empty_profile, geometry, "escavada", depth_m=5.0)


if __name__ == "__main__":
    unittest.main()
