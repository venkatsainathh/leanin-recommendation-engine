import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from app.database import connect
from app.ranking import recommend, timestamp
from seed import seed


class RecommendationScenarios(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        folder = cls.enterClassContext(tempfile.TemporaryDirectory())
        path = Path(folder) / "circles.sqlite3"
        seed(path)
        cls.db = cls.enterClassContext(closing(connect(path)))
        snapshot = cls.db.execute(
            "SELECT value FROM dataset_metadata WHERE key = 'snapshot_at'"
        ).fetchone()[0]
        cls.as_of = timestamp(snapshot)

    def results(self, user_id):
        return recommend(self.db, user_id, 50, self.as_of)

    def circle_ids(self, user_id):
        return [row["circle_id"] for row in self.results(user_id)["recommendations"]]

    def test_new_member_gets_discovery_results(self):
        result = self.results(42)
        self.assertTrue(result["metadata"]["cold_start"])
        self.assertEqual(result["metadata"]["strategy"], "discovery")
        self.assertTrue(result["recommendations"])

    def test_stated_interests_match_top_results(self):
        self.assertTrue({5, 6}.issubset(self.circle_ids(7)[:3]))

    def test_negotiation_results_include_variety(self):
        ids = self.circle_ids(15)
        similar = {10, 11, 12}
        self.assertTrue(similar.intersection(ids[:3]))
        self.assertLessEqual(len(similar.intersection(ids)), 2)

    def test_full_and_inactive_matches_are_excluded(self):
        ids = self.circle_ids(23)
        self.assertEqual(ids[0], 22)
        self.assertTrue({20, 21}.isdisjoint(ids))
