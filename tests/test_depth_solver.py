import unittest

from spt_piles import depth_solver as ds
from spt_piles.models import PileGeometry, SPTProfile


def increasing_resistance_profile() -> SPTProfile:
    profile = SPTProfile()
    for depth in range(1, 21):
        n_value = 4 + depth  # resistência cresce com a profundidade
        profile.add(depth, n_value, "areia")
    return profile


class TestDepthSolver(unittest.TestCase):
    def test_finds_required_depth_both_methods(self):
        profile = increasing_resistance_profile()
        geometry = PileGeometry(diameter_cm=40)
        result = ds.solve(
            profile, geometry, "helice_continua", load_kn=300.0, method=ds.METHOD_BOTH, safety_factor=2.0
        )
        self.assertIsNotNone(result.required_depth_m)
        for row in result.rows:
            if row.depth_m == result.required_depth_m:
                self.assertGreaterEqual(row.qadm_governing_kn, 300.0)

        # nenhuma profundidade anterior deveria já atender a carga
        earlier_rows = [r for r in result.rows if r.depth_m < result.required_depth_m]
        self.assertTrue(all(r.qadm_governing_kn < 300.0 for r in earlier_rows))

    def test_governing_is_minimum_of_both_methods(self):
        profile = increasing_resistance_profile()
        geometry = PileGeometry(diameter_cm=40)
        result = ds.solve(profile, geometry, "escavada", load_kn=1.0, method=ds.METHOD_BOTH)
        for row in result.rows:
            self.assertAlmostEqual(
                row.qadm_governing_kn, min(row.qadm_dq_kn, row.qadm_av_kn), places=6
            )

    def test_unreachable_load_returns_none(self):
        profile = increasing_resistance_profile()
        geometry = PileGeometry(diameter_cm=20)
        result = ds.solve(profile, geometry, "escavada", load_kn=1_000_000.0, method=ds.METHOD_DQ)
        self.assertIsNone(result.required_depth_m)

    def test_single_method_only_populates_that_column(self):
        profile = increasing_resistance_profile()
        geometry = PileGeometry(diameter_cm=40)
        result = ds.solve(profile, geometry, "escavada", load_kn=300.0, method=ds.METHOD_DQ)
        self.assertTrue(all(r.qadm_av_kn is None for r in result.rows))
        self.assertTrue(all(r.qadm_dq_kn is not None for r in result.rows))

    def test_invalid_load_raises(self):
        profile = increasing_resistance_profile()
        geometry = PileGeometry(diameter_cm=40)
        with self.assertRaises(ValueError):
            ds.solve(profile, geometry, "escavada", load_kn=0)


if __name__ == "__main__":
    unittest.main()
