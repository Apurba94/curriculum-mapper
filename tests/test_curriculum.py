import random
import unittest

from curriculum_mapper import core, create_app
from curriculum_mapper.core import Assessment, Competency, Lesson, assessment_balance, check_order, coverage, gaps, plan_hours, sequence_problems, teaching_order

C = [Competency("C1", "Use a keyboard", 4, "Apply"), Competency("C2", "Write a document", 6, "Apply", ("C1",)), Competency("C3", "Make a budget sheet", 6, "Create", ("C1",))]


class TestCoverage(unittest.TestCase):
    def test_hours_split_across_a_shared_lesson(self):
        rows = coverage(C, [Lesson(1, "L", 4, {"C1": "Apply", "C2": "Understand"})], [])
        self.assertEqual((rows[0]["taught"], rows[1]["taught"]), (2, 2))

    def test_highest_levels_are_kept(self):
        rows = coverage(C, [Lesson(1, "a", 1, {"C1": "Apply"}), Lesson(2, "b", 1, {"C1": "Remember"})], [Assessment(1, "t", 10, {"C1": "Understand"})])
        self.assertEqual((rows[0]["top_taught"], rows[0]["top_assessed"]), ("Apply", "Understand"))

    def test_assessment_weight_shares(self):
        rows = coverage(C, [], [Assessment(1, "t", 30, {"C1": "Apply", "C2": "Apply", "C3": "Apply"})])
        self.assertEqual([r["assessed"] for r in rows], [10, 10, 10])


class TestGaps(unittest.TestCase):
    def msgs(self, *a):
        return [f"{code} {m}" for _, code, m in gaps(*a)]

    def test_never_taught_or_assessed(self):
        m = self.msgs([C[0]], [], [])
        self.assertIn("C1 is never taught", m)
        self.assertIn("C1 is never assessed", m)

    def test_assessed_above_what_was_taught(self):
        m = self.msgs([C[0]], [Lesson(1, "a", 4, {"C1": "Remember"})], [Assessment(1, "t", 10, {"C1": "Apply"})])
        self.assertTrue(any("assessed at Apply but taught only to Remember" in x for x in m))

    def test_target_not_reached(self):
        m = self.msgs([C[2]], [Lesson(1, "a", 6, {"C3": "Apply"})], [Assessment(1, "t", 10, {"C3": "Apply"})])
        self.assertTrue(any("targets Create but reaches only Apply" in x for x in m))

    def test_hours_mismatch(self):
        m = self.msgs([C[0]], [Lesson(1, "a", 10, {"C1": "Apply"})], [Assessment(1, "t", 10, {"C1": "Apply"})])
        self.assertTrue(any("10 teaching hours against 4 planned" in x for x in m))

    def test_undefined_codes(self):
        m = self.msgs([], [Lesson(1, "a", 1, {"X9": "Apply"})], [Assessment(1, "t", 10, {"Y1": "Apply"})])
        self.assertEqual(len(m), 2)

    def test_a_clean_map_has_no_problems(self):
        self.assertEqual(gaps([C[0]], [Lesson(1, "a", 4, {"C1": "Apply"})], [Assessment(1, "t", 10, {"C1": "Apply"})]), [])

    def test_bad_level(self):
        with self.assertRaises(ValueError):
            coverage(C, [Lesson(1, "a", 1, {"C1": "Vibes"}), Lesson(2, "b", 1, {"C1": "Apply"})], [])


class TestOrder(unittest.TestCase):
    def test_order_respects_prerequisites(self):
        rng = random.Random(1)
        for _ in range(100):
            codes = [f"C{i}" for i in range(12)]
            comps = []
            for i, c in enumerate(codes):
                comps.append(Competency(c, c, requires=tuple(rng.sample(codes[:i], min(i, rng.randint(0, 3))))))
            shuffled = comps[:]
            rng.shuffle(shuffled)
            order = teaching_order(shuffled)
            pos = {c: i for i, c in enumerate(order)}
            self.assertEqual(sorted(order), sorted(codes))
            for c in comps:
                for r in c.requires:
                    self.assertLess(pos[r], pos[c.code])

    def test_free_items_keep_the_given_order(self):
        self.assertEqual(teaching_order([Competency("B", "b"), Competency("A", "a")]), ["B", "A"])

    def test_loops(self):
        loop = [Competency("A", "a", requires=("B",)), Competency("B", "b", requires=("C",)), Competency("C", "c", requires=("A",))]
        self.assertIn("loop", check_order(loop)[0])
        with self.assertRaises(ValueError):
            teaching_order(loop)

    def test_missing_prerequisite(self):
        self.assertIn("not defined", check_order([Competency("A", "a", requires=("Z",))])[0])

    def test_lesson_before_its_prerequisite(self):
        p = sequence_problems(C, [Lesson(1, "doc", 2, {"C2": "Apply"}, 1), Lesson(2, "keys", 2, {"C1": "Apply"}, 3)])
        self.assertIn("C2 is taught in week 1, before its prerequisite C1", p)

    def test_right_order_is_clean(self):
        self.assertEqual(sequence_problems(C[:2], [Lesson(1, "keys", 2, {"C1": "Apply"}, 1), Lesson(2, "doc", 2, {"C2": "Apply"}, 2)]), [])


class TestBalance(unittest.TestCase):
    def test_balance(self):
        b = assessment_balance([Assessment(1, "a", 75, {"C1": "Remember"}), Assessment(2, "b", 25, {"C1": "Create"})])
        self.assertEqual(b, {"Remember": 0.75, "Create": 0.25})
        self.assertEqual(assessment_balance([]), {})

    def test_week_overload(self):
        self.assertEqual(plan_hours([Lesson(1, "a", 3, week=1), Lesson(2, "b", 3, week=1), Lesson(3, "c", 2, week=2)], 4), {1: 6})


class TestApp(unittest.TestCase):
    def setUp(self):
        self.a = create_app(":memory:")
        self.a.post("/competencies", code="C1", title="Keyboard", hours=4, level="Apply")
        self.a.post("/competencies", code="C2", title="Documents", hours=4, level="Apply", requires="C1")

    def home(self):
        return self.a.get("/").body.decode()

    def test_map_reports_then_clears_problems(self):
        self.assertIn("is never taught", self.home())
        self.a.post("/lessons", title="Keys", week=1, hours=4, teaches="C1:Apply")
        self.a.post("/lessons", title="Docs", week=2, hours=4, teaches="C2:Apply")
        self.a.post("/assessments", title="Test", weight=100, covers="C1:Apply, C2:Apply")
        page = self.home()
        self.assertIn("No gaps found", page)
        self.assertIn("C1 → C2", page)

    def test_sequence_warning_shows(self):
        self.a.post("/lessons", title="Docs", week=1, hours=4, teaches="C2:Apply")
        self.a.post("/lessons", title="Keys", week=2, hours=4, teaches="C1:Apply")
        self.assertIn("before its prerequisite", self.home())

    def test_loop_does_not_break_the_page(self):
        self.a.run("UPDATE competencies SET requires = ? WHERE code = 'C1'", '["C2"]')
        r = self.a.get("/")
        self.assertEqual(r.status, 200)
        self.assertIn("loop", r.body.decode())

    def test_bad_level_is_refused(self):
        self.assertEqual(self.a.post("/lessons", title="x", week=1, hours=1, teaches="C1:Magic").status, 400)

    def test_duplicate_code_is_refused(self):
        self.assertEqual(self.a.post("/competencies", code="C1", title="again", level="Apply").status, 409)


if __name__ == "__main__":
    unittest.main()
