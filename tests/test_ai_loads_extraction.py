import unittest

from spt_piles.ai_extraction import AIExtractionError, _parse_loads_tool_output


class TestParseLoadsToolOutput(unittest.TestCase):
    def test_parses_valid_items(self):
        data = {
            "items": [
                {
                    "element_id": "P12",
                    "characteristic_load_kn": 850.0,
                    "n_piles": 2,
                    "original_description": "P12 - Nk = 85 tf (bloco B04, 2 estacas)",
                },
                {
                    "element_id": "P13",
                    "characteristic_load_kn": 400.0,
                    "n_piles": 1,
                    "original_description": "P13 - Nk = 400 kN",
                },
            ],
            "notes": "Cargas extraídas da combinação quase-permanente.",
        }
        result = _parse_loads_tool_output(data, "/tmp/cargas.pdf", "claude-sonnet-5")

        self.assertEqual(len(result.items), 2)
        self.assertEqual(result.items[0].element_id, "P12")
        self.assertEqual(result.items[0].n_piles, 2)
        self.assertAlmostEqual(result.items[0].characteristic_load_kn, 850.0)
        self.assertEqual(result.source_pdf_path, "/tmp/cargas.pdf")
        self.assertEqual(result.model_used, "claude-sonnet-5")

    def test_defaults_n_piles_to_one_when_missing_or_invalid(self):
        data = {
            "items": [
                {"element_id": "P1", "characteristic_load_kn": 300.0, "original_description": "x"},
                {"element_id": "P2", "characteristic_load_kn": 300.0, "n_piles": 0, "original_description": "x"},
            ]
        }
        result = _parse_loads_tool_output(data, "x.pdf", "m")
        self.assertEqual(result.items[0].n_piles, 1)
        self.assertEqual(result.items[1].n_piles, 1)

    def test_filters_out_non_positive_loads_and_empty_ids(self):
        data = {
            "items": [
                {"element_id": "P1", "characteristic_load_kn": 300.0, "n_piles": 1, "original_description": "ok"},
                {"element_id": "P2", "characteristic_load_kn": -10.0, "n_piles": 1, "original_description": "invalido"},
                {"element_id": "", "characteristic_load_kn": 200.0, "n_piles": 1, "original_description": "sem id"},
            ]
        }
        result = _parse_loads_tool_output(data, "x.pdf", "m")
        self.assertEqual(len(result.items), 1)
        self.assertEqual(result.items[0].element_id, "P1")

    def test_no_valid_items_raises(self):
        with self.assertRaises(AIExtractionError):
            _parse_loads_tool_output({"items": []}, "x.pdf", "m")

    def test_moment_and_shear_parsed_when_present(self):
        data = {
            "items": [
                {
                    "element_id": "P1", "characteristic_load_kn": 300.0, "n_piles": 1,
                    "moment_kn_m": 45.0, "shear_kn": 20.0, "original_description": "x",
                },
            ]
        }
        result = _parse_loads_tool_output(data, "x.pdf", "m")
        self.assertAlmostEqual(result.items[0].moment_kn_m, 45.0)
        self.assertAlmostEqual(result.items[0].shear_kn, 20.0)

    def test_moment_and_shear_default_to_none_when_absent(self):
        data = {
            "items": [
                {"element_id": "P1", "characteristic_load_kn": 300.0, "n_piles": 1, "original_description": "x"},
            ]
        }
        result = _parse_loads_tool_output(data, "x.pdf", "m")
        self.assertIsNone(result.items[0].moment_kn_m)
        self.assertIsNone(result.items[0].shear_kn)

    def test_negative_moment_and_shear_are_stored_as_absolute_value(self):
        data = {
            "items": [
                {
                    "element_id": "P1", "characteristic_load_kn": 300.0, "n_piles": 1,
                    "moment_kn_m": -45.0, "shear_kn": -20.0, "original_description": "x",
                },
            ]
        }
        result = _parse_loads_tool_output(data, "x.pdf", "m")
        self.assertAlmostEqual(result.items[0].moment_kn_m, 45.0)
        self.assertAlmostEqual(result.items[0].shear_kn, 20.0)

    def test_moment_components_combined_into_resultant(self):
        data = {
            "items": [
                {
                    "element_id": "P1", "characteristic_load_kn": 700.0, "n_piles": 1,
                    "moment_x_knm": 90.0, "moment_y_knm": 120.0, "original_description": "x",
                },
            ]
        }
        result = _parse_loads_tool_output(data, "x.pdf", "m")
        item = result.items[0]
        self.assertAlmostEqual(item.moment_x_knm, 90.0)
        self.assertAlmostEqual(item.moment_y_knm, 120.0)
        self.assertAlmostEqual(item.moment_kn_m, 150.0)  # sqrt(90^2+120^2) = 150

    def test_shear_components_combined_into_resultant(self):
        data = {
            "items": [
                {
                    "element_id": "P1", "characteristic_load_kn": 700.0, "n_piles": 1,
                    "shear_x_kn": 30.0, "shear_y_kn": 40.0, "original_description": "x",
                },
            ]
        }
        result = _parse_loads_tool_output(data, "x.pdf", "m")
        item = result.items[0]
        self.assertAlmostEqual(item.shear_x_kn, 30.0)
        self.assertAlmostEqual(item.shear_y_kn, 40.0)
        self.assertAlmostEqual(item.shear_kn, 50.0)  # sqrt(30^2+40^2) = 50

    def test_components_take_priority_over_direct_resultant_if_both_given(self):
        # A IA foi instruída a nunca preencher os dois, mas o parser deve ser
        # robusto e priorizar os componentes (calculados de forma confiável
        # em Python) sobre um valor direto porventura também presente.
        data = {
            "items": [
                {
                    "element_id": "P1", "characteristic_load_kn": 700.0, "n_piles": 1,
                    "moment_x_knm": 90.0, "moment_y_knm": 120.0, "moment_kn_m": 999.0,
                    "original_description": "x",
                },
            ]
        }
        result = _parse_loads_tool_output(data, "x.pdf", "m")
        self.assertAlmostEqual(result.items[0].moment_kn_m, 150.0)

    def test_single_component_only_still_computes_resultant(self):
        data = {
            "items": [
                {
                    "element_id": "P1", "characteristic_load_kn": 300.0, "n_piles": 1,
                    "moment_x_knm": 45.0, "original_description": "x",
                },
            ]
        }
        result = _parse_loads_tool_output(data, "x.pdf", "m")
        self.assertAlmostEqual(result.items[0].moment_kn_m, 45.0)
        self.assertIsNone(result.items[0].moment_y_knm)

    def test_components_default_to_none_when_absent(self):
        data = {
            "items": [
                {"element_id": "P1", "characteristic_load_kn": 300.0, "n_piles": 1, "original_description": "x"},
            ]
        }
        result = _parse_loads_tool_output(data, "x.pdf", "m")
        item = result.items[0]
        self.assertIsNone(item.moment_x_knm)
        self.assertIsNone(item.moment_y_knm)
        self.assertIsNone(item.shear_x_kn)
        self.assertIsNone(item.shear_y_kn)


if __name__ == "__main__":
    unittest.main()
