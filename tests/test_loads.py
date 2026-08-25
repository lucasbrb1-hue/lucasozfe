import unittest

from spt_piles.loads import FoundationLoad, LoadCombination, LoadSet


class TestFoundationLoad(unittest.TestCase):
    def test_load_per_pile_divides_by_n_piles(self):
        load = FoundationLoad("P1", characteristic_load_kn=900.0, n_piles=3)
        self.assertAlmostEqual(load.load_per_pile_kn, 300.0)

    def test_moment_and_shear_default_to_none(self):
        load = FoundationLoad("P1", characteristic_load_kn=300.0)
        self.assertIsNone(load.moment_kn_m)
        self.assertIsNone(load.shear_kn)
        self.assertIsNone(load.moment_per_pile_knm)
        self.assertIsNone(load.shear_per_pile_kn)

    def test_moment_and_shear_divided_by_n_piles(self):
        load = FoundationLoad("B1", characteristic_load_kn=900.0, n_piles=3, moment_kn_m=60.0, shear_kn=30.0)
        self.assertAlmostEqual(load.moment_per_pile_knm, 20.0)
        self.assertAlmostEqual(load.shear_per_pile_kn, 10.0)

    def test_negative_moment_raises(self):
        with self.assertRaises(ValueError):
            FoundationLoad("P1", characteristic_load_kn=300.0, moment_kn_m=-5.0)

    def test_negative_shear_raises(self):
        with self.assertRaises(ValueError):
            FoundationLoad("P1", characteristic_load_kn=300.0, shear_kn=-5.0)

    def test_zero_load_raises(self):
        with self.assertRaises(ValueError):
            FoundationLoad("P1", characteristic_load_kn=0.0)

    def test_empty_id_raises(self):
        with self.assertRaises(ValueError):
            FoundationLoad("", characteristic_load_kn=300.0)

    def test_raw_components_default_to_none(self):
        load = FoundationLoad("P1", characteristic_load_kn=300.0)
        self.assertIsNone(load.moment_x_knm)
        self.assertIsNone(load.moment_y_knm)
        self.assertIsNone(load.shear_x_kn)
        self.assertIsNone(load.shear_y_kn)

    def test_raw_components_stored_for_traceability(self):
        load = FoundationLoad(
            "P1", characteristic_load_kn=700.0, moment_kn_m=150.0, shear_kn=50.0,
            moment_x_knm=90.0, moment_y_knm=120.0, shear_x_kn=30.0, shear_y_kn=40.0,
        )
        self.assertAlmostEqual(load.moment_x_knm, 90.0)
        self.assertAlmostEqual(load.moment_y_knm, 120.0)
        self.assertAlmostEqual(load.shear_x_kn, 30.0)
        self.assertAlmostEqual(load.shear_y_kn, 40.0)
        # os componentes não substituem o cálculo, que sempre usa a resultante
        self.assertAlmostEqual(load.moment_kn_m, 150.0)
        self.assertAlmostEqual(load.shear_kn, 50.0)


class TestLoadSet(unittest.TestCase):
    def test_add_without_moment(self):
        loads = LoadSet()
        loads.add("P1", 300.0)
        self.assertFalse(loads.has_moment_data())

    def test_add_with_raw_components(self):
        loads = LoadSet()
        loads.add("P1", 700.0, moment_kn_m=150.0, moment_x_knm=90.0, moment_y_knm=120.0)
        self.assertAlmostEqual(loads.items[0].moment_x_knm, 90.0)
        self.assertAlmostEqual(loads.items[0].moment_y_knm, 120.0)

    def test_has_moment_data_true_if_any_item_has_it(self):
        loads = LoadSet()
        loads.add("P1", 300.0)
        loads.add("P2", 400.0, moment_kn_m=50.0)
        self.assertTrue(loads.has_moment_data())

    def test_is_valid(self):
        loads = LoadSet()
        self.assertFalse(loads.is_valid())
        loads.add("P1", 300.0)
        self.assertTrue(loads.is_valid())

    def test_has_moment_data_true_for_combinations_even_without_scalar_moment(self):
        loads = LoadSet()
        loads.add(
            "B1", 200.0,
            combinations=[LoadCombination(label="G1+G2", n_kn=200.0, moment_x_knm=10.0)],
        )
        self.assertTrue(loads.has_moment_data())


class TestLoadCombination(unittest.TestCase):
    def test_moment_and_shear_are_resultants_of_components(self):
        combo = LoadCombination(label="G1+G2", n_kn=100.0, moment_x_knm=3.0, moment_y_knm=4.0, shear_x_kn=6.0, shear_y_kn=8.0)
        self.assertAlmostEqual(combo.moment_kn_m, 5.0)  # sqrt(3^2+4^2)
        self.assertAlmostEqual(combo.shear_kn, 10.0)  # sqrt(6^2+8^2)

    def test_defaults_to_zero_components(self):
        combo = LoadCombination(label="G1", n_kn=50.0)
        self.assertAlmostEqual(combo.moment_kn_m, 0.0)
        self.assertAlmostEqual(combo.shear_kn, 0.0)


class TestFoundationLoadCombinations(unittest.TestCase):
    def test_combinations_per_pile_divides_all_fields_by_n_piles(self):
        load = FoundationLoad(
            "B1", characteristic_load_kn=400.0, n_piles=2,
            combinations=[
                LoadCombination(label="G1+G2", n_kn=400.0, moment_x_knm=20.0, moment_y_knm=10.0, shear_x_kn=8.0, shear_y_kn=4.0),
            ],
        )
        per_pile = load.combinations_per_pile()
        self.assertEqual(len(per_pile), 1)
        combo = per_pile[0]
        self.assertEqual(combo.label, "G1+G2")
        self.assertAlmostEqual(combo.n_kn, 200.0)
        self.assertAlmostEqual(combo.moment_x_knm, 10.0)
        self.assertAlmostEqual(combo.moment_y_knm, 5.0)
        self.assertAlmostEqual(combo.shear_x_kn, 4.0)
        self.assertAlmostEqual(combo.shear_y_kn, 2.0)

    def test_combinations_empty_by_default(self):
        load = FoundationLoad("P1", characteristic_load_kn=300.0)
        self.assertEqual(load.combinations, [])
        self.assertEqual(load.combinations_per_pile(), [])


if __name__ == "__main__":
    unittest.main()
