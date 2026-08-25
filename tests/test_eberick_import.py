import os
import tempfile
import unittest

try:
    import openpyxl

    HAS_OPENPYXL = True
except ImportError:
    HAS_OPENPYXL = False


def _write_sample_workbook(path: str) -> None:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Pav1_Fundacao_Combinacoes"

    rows = [
        ("OBRA", None, None, None, None, None, None),
        ("Tipo", "", None, None, None, None, None),
        (None, None, None, None, None, None, None),
        ("Relatório de Esforços nas Fundações por Elementos", None, None, None, None, None, None),
        (None, None, None, None, None, None, None),
        ("Fundação B1", None, None, None, None, None, None),
        ("Combinação", "N\n(kN)", "Mx \n (kN.m)", "My \n (kN.m)", "Vx \n (kN)", "Vy \n (kN)", "Mt\n(kN/m)"),
        ("Peso próprio (G1)", 100.0, -1.0, -0.5, 1.0, 2.0, -0.1),
        ("Vento X+ (V1)", -10.0, -0.5, 10.0, 5.0, 0.5, -0.1),
        ("G1+G2", 150.0, 0.5, 2.0, -10.0, 8.0, 0.5),
        ("G1+G2+V1+0.56D1", 120.0, -0.3, 15.0, -5.0, 9.0, 0.4),
        (None, None, None, None, None, None, None),
        ("Fundação B2", None, None, None, None, None, None),
        ("Combinação", "N\n(kN)", "Mx \n (kN.m)", "My \n (kN.m)", "Vx \n (kN)", "Vy \n (kN)", "Mt\n(kN/m)"),
        ("Peso próprio (G1)", 200.0, 0, 0, 0, 0, 0),
        ("G1+G2", 250.0, 1.0, 1.0, -2.0, 2.0, 0.1),
        (None, None, None, None, None, None, None),
        ("Legenda", None, None, None, None, None, None),
        ("", None, "- Caso: indica o caso de carregamento...", None, None, None, None),
        ("AltoQi | Tecnologia aplicada à engenharia.", None, None, None, None, None, None),
    ]
    for row in rows:
        ws.append(row)
    wb.save(path)


@unittest.skipUnless(HAS_OPENPYXL, "openpyxl não instalado")
class TestEberickImport(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.tmpdir.name, "combinacoes.xlsx")
        _write_sample_workbook(self.path)

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_parses_two_elements(self):
        from spt_piles.eberick_import import parse_eberick_combinations_xlsx

        loads = parse_eberick_combinations_xlsx(self.path)
        self.assertEqual(len(loads), 2)
        self.assertEqual({ld.element_id for ld in loads}, {"B1", "B2"})

    def test_skips_individual_load_cases_keeps_only_combinations(self):
        from spt_piles.eberick_import import parse_eberick_combinations_xlsx

        loads = parse_eberick_combinations_xlsx(self.path)
        b1 = next(ld for ld in loads if ld.element_id == "B1")
        # 2 combinações (G1+G2, G1+G2+V1+0.56D1) - os 2 casos individuais
        # (Peso próprio, Vento X+) devem ter sido ignorados.
        self.assertEqual(len(b1.combinations), 2)
        labels = {c.label for c in b1.combinations}
        self.assertEqual(labels, {"G1+G2", "G1+G2+V1+0.56D1"})

    def test_combination_values_preserved_concomitant(self):
        from spt_piles.eberick_import import parse_eberick_combinations_xlsx

        loads = parse_eberick_combinations_xlsx(self.path)
        b1 = next(ld for ld in loads if ld.element_id == "B1")
        combo = next(c for c in b1.combinations if c.label == "G1+G2+V1+0.56D1")
        self.assertAlmostEqual(combo.n_kn, 120.0)
        self.assertAlmostEqual(combo.moment_x_knm, -0.3)
        self.assertAlmostEqual(combo.moment_y_knm, 15.0)
        self.assertAlmostEqual(combo.shear_x_kn, -5.0)
        self.assertAlmostEqual(combo.shear_y_kn, 9.0)

    def test_characteristic_load_is_max_absolute_n_among_combinations(self):
        from spt_piles.eberick_import import parse_eberick_combinations_xlsx

        loads = parse_eberick_combinations_xlsx(self.path)
        b1 = next(ld for ld in loads if ld.element_id == "B1")
        # max(|150|, |120|) = 150
        self.assertAlmostEqual(b1.characteristic_load_kn, 150.0)

    def test_default_n_piles_is_one(self):
        from spt_piles.eberick_import import parse_eberick_combinations_xlsx

        loads = parse_eberick_combinations_xlsx(self.path)
        self.assertTrue(all(ld.n_piles == 1 for ld in loads))

    def test_second_element_parsed_independently(self):
        from spt_piles.eberick_import import parse_eberick_combinations_xlsx

        loads = parse_eberick_combinations_xlsx(self.path)
        b2 = next(ld for ld in loads if ld.element_id == "B2")
        self.assertEqual(len(b2.combinations), 1)
        self.assertEqual(b2.combinations[0].label, "G1+G2")
        self.assertAlmostEqual(b2.combinations[0].n_kn, 250.0)

    def test_missing_file_raises_friendly_error(self):
        from spt_piles.eberick_import import EberickImportError, parse_eberick_combinations_xlsx

        with self.assertRaises(EberickImportError):
            parse_eberick_combinations_xlsx("/no/such/file.xlsx")

    def test_workbook_without_any_foundation_raises(self):
        from spt_piles.eberick_import import EberickImportError, parse_eberick_combinations_xlsx

        empty_path = os.path.join(self.tmpdir.name, "empty.xlsx")
        wb = openpyxl.Workbook()
        wb.active.append(("nada aqui",))
        wb.save(empty_path)
        with self.assertRaises(EberickImportError):
            parse_eberick_combinations_xlsx(empty_path)


if __name__ == "__main__":
    unittest.main()
