import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from qq_cf_bot.codeforces import CodeforcesClient, _fetch_json_from_codeforces_variants
from qq_cf_bot.models import CFProblem


class _FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.close()


class CodeforcesClientTest(unittest.TestCase):
    def test_fetch_json_falls_back_when_primary_is_non_ok(self):
        seen_urls = []

        def fake_urlopen(request, timeout):
            del timeout
            seen_urls.append(request.full_url)
            status = "FAILED" if request.full_url.startswith("https://codeforces.com/") else "OK"
            return _FakeResponse(json.dumps({"status": status, "result": []}).encode("utf-8"))

        with patch("qq_cf_bot.codeforces.urllib.request.urlopen", side_effect=fake_urlopen):
            payload = _fetch_json_from_codeforces_variants(
                "/api/problemset.problems",
                ("https://codeforces.com", "https://m1.codeforces.com"),
                timeout_seconds=20,
            )

        self.assertEqual(payload["status"], "OK")
        self.assertEqual(
            seen_urls,
            [
                "https://codeforces.com/api/problemset.problems",
                "https://m1.codeforces.com/api/problemset.problems",
            ],
        )

    def test_resolve_problem_maps_combined_round_alias_to_canonical_problem(self):
        with tempfile.TemporaryDirectory() as tmp:
            client = CodeforcesClient(Path(tmp) / "problemset.json")
            catalog = [
                CFProblem(2263, "A", "Min Max Game", 800),
                CFProblem(2263, "B", "Min Matrices", 900),
                CFProblem(2262, "A2", "Floor of MEX (Hard Version)", 1800),
            ]
            standings = {
                "status": "OK",
                "result": {
                    "problems": [
                        {
                            "contestId": 2263,
                            "index": "C2",
                            "name": "Floor of MEX (Hard Version)",
                            "rating": 1800,
                            "tags": ["dp"],
                        }
                    ]
                },
            }
            with (
                patch.object(client, "fetch_problems", return_value=catalog),
                patch("qq_cf_bot.codeforces._fetch_json_from_codeforces_variants", return_value=standings) as fetch,
            ):
                problem = client.resolve_problem(2263, "c2")

        self.assertIsNotNone(problem)
        self.assertEqual(problem.cf_id, "2262A2")
        fetch.assert_called_once_with(
            "/api/contest.standings?contestId=2263",
            client.base_urls,
            timeout_seconds=20,
        )

    def test_resolve_problem_uses_catalog_without_fetching_standings(self):
        with tempfile.TemporaryDirectory() as tmp:
            client = CodeforcesClient(Path(tmp) / "problemset.json")
            expected = CFProblem(1704, "F", "Colouring Game", 2400)
            with (
                patch.object(client, "fetch_problems", return_value=[expected]),
                patch("qq_cf_bot.codeforces._fetch_json_from_codeforces_variants") as fetch,
            ):
                problem = client.resolve_problem(1704, "f")

        self.assertEqual(problem, expected)
        fetch.assert_not_called()

    def test_fetch_gym_contest_keeps_unrated_problems(self):
        payload = {
            "status": "OK",
            "result": {
                "contest": {
                    "id": 105001,
                    "name": "Example Gym",
                    "phase": "FINISHED",
                    "durationSeconds": 18000,
                },
                "problems": [
                    {"contestId": 105001, "index": "A", "name": "Warmup", "tags": ["math"]},
                    {"contestId": 105001, "index": "B", "name": "Finale", "rating": 2100},
                ],
            },
        }
        with tempfile.TemporaryDirectory() as tmp:
            client = CodeforcesClient(Path(tmp) / "problemset.json")
            with patch("qq_cf_bot.codeforces._fetch_json_from_codeforces_variants", return_value=payload):
                contest, problems = client.fetch_contest(105001)

        self.assertTrue(contest.is_gym)
        self.assertEqual(contest.duration_seconds, 18000)
        self.assertEqual([problem.cf_id for problem in problems], ["105001A", "105001B"])
        self.assertEqual([problem.rating for problem in problems], [0, 2100])
        self.assertEqual(problems[0].cf_url, "https://codeforces.com/gym/105001/problem/A")


if __name__ == "__main__":
    unittest.main()
