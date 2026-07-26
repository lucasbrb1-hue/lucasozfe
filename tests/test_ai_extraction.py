import unittest

from spt_piles.ai_extraction import AIExtractionError, _parse_spt_tool_output as _parse_tool_output


class TestParseToolOutput(unittest.TestCase):
    def test_parses_valid_readings_sorted_by_depth(self):
        data = {
            "readings": [
                {"depth_m": 2.0, "n_spt": 8, "soil_key": "argila", "soil_description_original": "Argila mole"},
                {"depth_m": 1.0, "n_spt": 4, "soil_key": "argila", "soil_description_original": "Argila mole"},
            ],
            "water_table_found": True,
            "water_table_depth_m": 1.5,
            "borehole_id": "SP-01",
            "notes": "Ensaio conforme NBR 6484",
        }
        result = _parse_tool_output(data, "/tmp/laudo.pdf", "claude-sonnet-5")

        self.assertEqual([r.depth_m for r in result.readings], [1.0, 2.0])
        self.assertTrue(result.water_table_found)
        self.assertEqual(result.water_table_depth_m, 1.5)
        self.assertEqual(result.borehole_id, "SP-01")
        self.assertEqual(result.source_pdf_path, "/tmp/laudo.pdf")
        self.assertEqual(result.model_used, "claude-sonnet-5")

    def test_filters_out_invalid_soil_key(self):
        data = {
            "readings": [
                {"depth_m": 1.0, "n_spt": 4, "soil_key": "argila", "soil_description_original": "Argila"},
                {"depth_m": 2.0, "n_spt": 6, "soil_key": "rocha_inexistente", "soil_description_original": "Rocha"},
            ],
            "water_table_found": False,
        }
        result = _parse_tool_output(data, "x.pdf", "m")
        self.assertEqual(len(result.readings), 1)
        self.assertEqual(result.readings[0].soil_key, "argila")

    def test_filters_out_malformed_entries(self):
        data = {
            "readings": [
                {"depth_m": 1.0, "n_spt": 4, "soil_key": "argila", "soil_description_original": "Argila"},
                {"depth_m": "não é número", "n_spt": 4, "soil_key": "argila", "soil_description_original": "x"},
                {"n_spt": 4, "soil_key": "argila", "soil_description_original": "faltando depth_m"},
            ],
            "water_table_found": False,
        }
        result = _parse_tool_output(data, "x.pdf", "m")
        self.assertEqual(len(result.readings), 1)

    def test_no_valid_readings_raises(self):
        data = {"readings": [], "water_table_found": False}
        with self.assertRaises(AIExtractionError):
            _parse_tool_output(data, "x.pdf", "m")

    def test_missing_api_key_raises_friendly_error(self):
        import os

        from spt_piles.ai_extraction import extract_spt_report

        old = os.environ.pop("ANTHROPIC_API_KEY", None)
        try:
            with self.assertRaises(AIExtractionError):
                extract_spt_report("/nonexistent/file.pdf")
        finally:
            if old is not None:
                os.environ["ANTHROPIC_API_KEY"] = old


if __name__ == "__main__":
    unittest.main()
