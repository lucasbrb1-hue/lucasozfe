import unittest

from spt_piles import depth_solver as ds
from spt_piles import pile_group as pg
from spt_piles.loads import FoundationLoad
from spt_piles.models import PileGeometry, SPTProfile


def increasing_resistance_profile() -> SPTProfile:
    profile = SPTProfile()
    for depth in range(1, 26):
        profile.add(depth, 4 + depth, "areia")
    return profile


class TestComputeIndividualDesigns(unittest.TestCase):
    def test_load_per_pile_divides_by_n_piles(self):
        profile = increasing_resistance_profile()
        geometry = PileGeometry(diameter_cm=40)
        loads = [
            FoundationLoad("P1", characteristic_load_kn=300.0, n_piles=1),
            FoundationLoad("B2", characteristic_load_kn=900.0, n_piles=3),  # 300 kN/estaca
        ]
        designs = pg.compute_individual_designs(loads, profile, geometry, "pre_moldada")
        self.assertAlmostEqual(designs[0].load_per_pile_kn, 300.0)
        self.assertAlmostEqual(designs[1].load_per_pile_kn, 300.0)
        # mesma carga por estaca -> mesma profundidade individual necessária
        self.assertEqual(designs[0].individual_required_depth_m, designs[1].individual_required_depth_m)

    def test_deeper_required_for_higher_load(self):
        profile = increasing_resistance_profile()
        geometry = PileGeometry(diameter_cm=40)
        loads = [
            FoundationLoad("P1", characteristic_load_kn=200.0),
            FoundationLoad("P2", characteristic_load_kn=800.0),
        ]
        designs = pg.compute_individual_designs(loads, profile, geometry, "pre_moldada")
        self.assertLess(designs[0].individual_required_depth_m, designs[1].individual_required_depth_m)

    def test_empty_loads_raises(self):
        profile = increasing_resistance_profile()
        geometry = PileGeometry(diameter_cm=40)
        with self.assertRaises(ValueError):
            pg.compute_individual_designs([], profile, geometry, "pre_moldada")

    def test_unreachable_load_yields_none_depth(self):
        profile = increasing_resistance_profile()
        geometry = PileGeometry(diameter_cm=20)
        loads = [FoundationLoad("P1", characteristic_load_kn=1_000_000.0)]
        designs = pg.compute_individual_designs(loads, profile, geometry, "escavada")
        self.assertIsNone(designs[0].individual_required_depth_m)


class TestUniformization(unittest.TestCase):
    def _sample_designs(self):
        return [
            pg.PileDesign("P1", 1, 100.0, individual_required_depth_m=3.0),
            pg.PileDesign("P2", 1, 200.0, individual_required_depth_m=5.0),
            pg.PileDesign("P3", 1, 250.0, individual_required_depth_m=6.0),
            pg.PileDesign("P4", 1, 400.0, individual_required_depth_m=9.0),
            pg.PileDesign("P5", 1, 420.0, individual_required_depth_m=10.0),
            pg.PileDesign("P6", 1, 500.0, individual_required_depth_m=12.0),
        ]

    def test_no_uniformization_keeps_individual_depths(self):
        designs = self._sample_designs()
        pg.apply_no_uniformization(designs)
        for d in designs:
            self.assertEqual(d.adopted_depth_m, d.individual_required_depth_m)
            self.assertIsNone(d.group_label)

    def test_adopted_depth_never_less_than_individual(self):
        designs = self._sample_designs()
        pg.apply_group_uniformization(designs, n_groups=2)
        for d in designs:
            self.assertGreaterEqual(d.adopted_depth_m, d.individual_required_depth_m)

    def test_number_of_distinct_adopted_depths_matches_groups(self):
        designs = self._sample_designs()
        pg.apply_group_uniformization(designs, n_groups=3)
        distinct = {d.adopted_depth_m for d in designs}
        self.assertEqual(len(distinct), 3)

    def test_more_groups_than_piles_caps_at_pile_count(self):
        designs = self._sample_designs()
        pg.apply_group_uniformization(designs, n_groups=100)
        distinct = {d.adopted_depth_m for d in designs}
        self.assertEqual(len(distinct), len(designs))
        for d in designs:
            self.assertEqual(d.adopted_depth_m, d.individual_required_depth_m)

    def test_single_group_adopts_max_for_everyone(self):
        designs = self._sample_designs()
        pg.apply_group_uniformization(designs, n_groups=1)
        for d in designs:
            self.assertEqual(d.adopted_depth_m, 12.0)

    def test_infeasible_piles_are_excluded_from_grouping(self):
        designs = self._sample_designs()
        designs.append(pg.PileDesign("P7", 1, 900.0, individual_required_depth_m=None))
        pg.apply_group_uniformization(designs, n_groups=2)
        infeasible = [d for d in designs if d.element_id == "P7"][0]
        self.assertIsNone(infeasible.adopted_depth_m)
        self.assertEqual(infeasible.group_label, "Inviável")
        # demais estacas ainda formam 2 grupos normalmente
        feasible_groups = {d.adopted_depth_m for d in designs if d.element_id != "P7"}
        self.assertEqual(len(feasible_groups), 2)

    def test_invalid_group_count_raises(self):
        designs = self._sample_designs()
        with self.assertRaises(ValueError):
            pg.apply_group_uniformization(designs, n_groups=0)


if __name__ == "__main__":
    unittest.main()
