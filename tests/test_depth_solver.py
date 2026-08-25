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


def _strong_tip_layer_profile() -> SPTProfile:
    """Camada mole (N=3) até 2m, depois camada resistente (N=60) até 8m -
    perfil pequeno o suficiente para deixar a resistência de ponta dominar
    a capacidade última na profundidade necessária."""

    profile = SPTProfile()
    for depth in range(1, 3):
        profile.add(depth, 3, "areia")
    for depth in range(3, 9):
        profile.add(depth, 60, "areia")
    return profile


class TestSolveArmorLength(unittest.TestCase):
    def test_invalid_axial_load_or_depth_returns_none(self):
        profile = increasing_resistance_profile()
        geometry = PileGeometry(diameter_cm=40)
        self.assertIsNone(
            ds.solve_armor_length(profile, geometry, "helice_continua", 10.0, 0.0)
        )
        self.assertIsNone(
            ds.solve_armor_length(profile, geometry, "helice_continua", 0.0, 300.0)
        )

    def test_modest_load_on_large_pile_needs_only_shallow_armor(self):
        # Carga modesta perto do diâmetro grande da estaca: a capacidade do
        # concreto simples já cobre a força axial remanescente logo perto do
        # topo - a armadura sugerida deve ser bem menor que a profundidade
        # total da estaca.
        profile = increasing_resistance_profile()
        geometry = PileGeometry(diameter_cm=40)
        result = ds.solve(profile, geometry, "helice_continua", 300.0, method=ds.METHOD_DQ, safety_factor=2.0)
        self.assertIsNotNone(result.required_depth_m)
        armor = ds.solve_armor_length(
            profile, geometry, "helice_continua", result.required_depth_m, 300.0, method=ds.METHOD_DQ,
        )
        self.assertIsNotNone(armor)
        self.assertLess(armor, result.required_depth_m)

    def test_higher_load_needs_deeper_armor(self):
        profile = _strong_tip_layer_profile()
        geometry = PileGeometry(diameter_cm=25)
        result_low = ds.solve(profile, geometry, "pre_moldada", 500.0, method=ds.METHOD_DQ, safety_factor=2.0)
        result_high = ds.solve(profile, geometry, "pre_moldada", 800.0, method=ds.METHOD_DQ, safety_factor=2.0)
        self.assertIsNotNone(result_low.required_depth_m)
        self.assertIsNotNone(result_high.required_depth_m)
        armor_low = ds.solve_armor_length(
            profile, geometry, "pre_moldada", result_low.required_depth_m, 500.0, method=ds.METHOD_DQ,
        )
        armor_high = ds.solve_armor_length(
            profile, geometry, "pre_moldada", result_high.required_depth_m, 800.0, method=ds.METHOD_DQ,
        )
        self.assertIsNotNone(armor_low)
        self.assertIsNotNone(armor_high)
        self.assertGreaterEqual(armor_high, armor_low)

    def test_point_bearing_dominated_pile_with_huge_load_needs_full_length(self):
        # Quando mesmo a resistência de ponta isolada (na profundidade
        # adotada) supera a capacidade do concreto simples, não há
        # profundidade a partir da qual dispensar a armadura - retorna None
        # (armar toda a extensão).
        profile = _strong_tip_layer_profile()
        geometry = PileGeometry(diameter_cm=25)
        armor = ds.solve_armor_length(profile, geometry, "pre_moldada", 8.0, 5000.0, method=ds.METHOD_DQ)
        self.assertIsNone(armor)

    def test_result_depth_is_within_profile_and_adopted_depth(self):
        profile = _strong_tip_layer_profile()
        geometry = PileGeometry(diameter_cm=25)
        result = ds.solve(profile, geometry, "pre_moldada", 700.0, method=ds.METHOD_DQ, safety_factor=2.0)
        self.assertIsNotNone(result.required_depth_m)
        armor = ds.solve_armor_length(
            profile, geometry, "pre_moldada", result.required_depth_m, 700.0, method=ds.METHOD_DQ,
        )
        self.assertIsNotNone(armor)
        self.assertGreaterEqual(armor, 1.0)
        self.assertLessEqual(armor, result.required_depth_m)

    def test_invalid_profile_raises(self):
        empty_profile = SPTProfile()
        geometry = PileGeometry(diameter_cm=40)
        with self.assertRaises(ValueError):
            ds.solve_armor_length(empty_profile, geometry, "helice_continua", 10.0, 300.0)

    def test_invalid_load_factor_raises(self):
        profile = increasing_resistance_profile()
        geometry = PileGeometry(diameter_cm=40)
        with self.assertRaises(ValueError):
            ds.solve_armor_length(profile, geometry, "helice_continua", 10.0, 300.0, load_factor=0)


if __name__ == "__main__":
    unittest.main()
