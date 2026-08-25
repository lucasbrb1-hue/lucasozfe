import unittest

from spt_piles.models import SPTProfile
from spt_piles.pile_type_advisor import SiteConstraints, recommend_pile_types


def _uniform_profile(n_spt: int, max_depth: int = 15) -> SPTProfile:
    profile = SPTProfile()
    for depth in range(1, max_depth + 1):
        profile.add(depth, n_spt, "areia")
    return profile


class TestPileTypeAdvisor(unittest.TestCase):
    def test_invalid_profile_raises(self):
        with self.assertRaises(ValueError):
            recommend_pile_types(SPTProfile())

    def test_returns_all_four_pile_types_ranked(self):
        rec = recommend_pile_types(_uniform_profile(10))
        self.assertEqual(len(rec.assessments), 4)
        scores = [a.score for a in rec.assessments]
        self.assertEqual(scores, sorted(scores, reverse=True))
        self.assertIsNotNone(rec.best)

    def test_shallow_water_without_drilling_fluid_favors_helice_continua(self):
        rec = recommend_pile_types(
            _uniform_profile(10),
            water_table_found=True,
            water_table_depth_m=1.5,
            constraints=SiteConstraints(avoid_drilling_fluid=True),
        )
        self.assertEqual(rec.best.pile_type, "helice_continua")
        by_type = {a.pile_type: a for a in rec.assessments}
        self.assertLess(by_type["escavada"].score, by_type["helice_continua"].score)
        self.assertTrue(any("desmoronamento" in c for c in by_type["escavada"].concerns))

    def test_vibration_sensitive_neighbors_penalizes_pre_moldada(self):
        rec = recommend_pile_types(
            _uniform_profile(10),
            constraints=SiteConstraints(vibration_sensitive_neighbors=True),
        )
        by_type = {a.pile_type: a for a in rec.assessments}
        self.assertLess(by_type["pre_moldada"].score, 0)
        self.assertTrue(any("vibração" in c for c in by_type["pre_moldada"].concerns))
        self.assertNotEqual(rec.best.pile_type, "pre_moldada")

    def test_limited_access_favors_strauss_and_escavada_over_helice_e_cravada(self):
        rec = recommend_pile_types(
            _uniform_profile(10),
            constraints=SiteConstraints(limited_access_large_equipment=True),
        )
        by_type = {a.pile_type: a for a in rec.assessments}
        self.assertGreater(by_type["strauss"].score, by_type["helice_continua"].score)
        self.assertGreater(by_type["escavada"].score, by_type["helice_continua"].score)
        self.assertLess(by_type["pre_moldada"].score, by_type["strauss"].score)

    def test_shallow_resistant_layer_flags_prep_moldada_concern_and_profile_note(self):
        profile = SPTProfile()
        profile.add(1, 35, "areia")
        profile.add(2, 38, "areia")
        profile.add(10, 40, "areia")
        rec = recommend_pile_types(profile)
        self.assertTrue(any("nega" in n for n in rec.profile_notes))
        by_type = {a.pile_type: a for a in rec.assessments}
        self.assertTrue(any("nega prematura" in c for c in by_type["pre_moldada"].concerns))

    def test_very_high_nspt_flags_profile_note_and_helice_continua_concern(self):
        rec = recommend_pile_types(_uniform_profile(50))
        self.assertTrue(any("torque" in n or "muito alto" in n for n in rec.profile_notes))
        by_type = {a.pile_type: a for a in rec.assessments}
        self.assertTrue(any("torque" in c for c in by_type["helice_continua"].concerns))

    def test_small_scale_budget_favors_strauss(self):
        rec = recommend_pile_types(
            _uniform_profile(10), constraints=SiteConstraints(small_scale_budget=True)
        )
        by_type = {a.pile_type: a for a in rec.assessments}
        self.assertGreater(by_type["strauss"].score, by_type["helice_continua"].score)

    def test_unanswered_constraints_do_not_score_either_way(self):
        rec_default = recommend_pile_types(_uniform_profile(10))
        rec_explicit_false = recommend_pile_types(
            _uniform_profile(10),
            constraints=SiteConstraints(
                vibration_sensitive_neighbors=False,
                noise_restriction=False,
                limited_access_large_equipment=False,
                limited_headroom=False,
                avoid_drilling_fluid=False,
                small_scale_budget=False,
            ),
        )
        scores_default = {a.pile_type: a.score for a in rec_default.assessments}
        scores_explicit_false = {a.pile_type: a.score for a in rec_explicit_false.assessments}
        self.assertEqual(scores_default, scores_explicit_false)


if __name__ == "__main__":
    unittest.main()
