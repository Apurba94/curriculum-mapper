"""The offline web app."""
import json

from . import core
from .fieldkit import App, Fail, Raw, bar_chart, card, form, h, redirect, stats, table

SCHEMA = """
CREATE TABLE IF NOT EXISTS competencies (code TEXT PRIMARY KEY, title TEXT NOT NULL, hours REAL NOT NULL DEFAULT 0, level TEXT NOT NULL, requires TEXT NOT NULL DEFAULT '[]');
CREATE TABLE IF NOT EXISTS lessons (id INTEGER PRIMARY KEY, title TEXT NOT NULL, hours REAL NOT NULL, week INTEGER NOT NULL, teaches TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS assessments (id INTEGER PRIMARY KEY, title TEXT NOT NULL, weight REAL NOT NULL, covers TEXT NOT NULL);
"""
LEVELS = [(x, x) for x in core.BLOOM]


def parse_links(text):
    """Text such as 'C1:Apply, C2:Remember' becomes a mapping."""
    out = {}
    for part in text.split(","):
        part = part.strip()
        if part:
            code, _, lvl = part.partition(":")
            lvl = lvl.strip() or "Apply"
            if lvl not in core.BLOOM:
                raise Fail(f"{lvl} is not a Bloom level. Use one of: {', '.join(core.BLOOM)}")
            out[code.strip()] = lvl
    return out


def create_app(db="curriculum.db"):
    a = App("Curriculum Mapper", db, SCHEMA, [("Map", "/"), ("Competencies", "/competencies"), ("Lessons", "/lessons"), ("Assessments", "/assessments")])

    def data():
        comps = [core.Competency(r["code"], r["title"], r["hours"], r["level"], tuple(json.loads(r["requires"]))) for r in a.rows("SELECT * FROM competencies ORDER BY rowid")]
        lessons = [core.Lesson(r["id"], r["title"], r["hours"], json.loads(r["teaches"]), r["week"]) for r in a.rows("SELECT * FROM lessons ORDER BY week, id")]
        tests = [core.Assessment(r["id"], r["title"], r["weight"], json.loads(r["covers"])) for r in a.rows("SELECT * FROM assessments ORDER BY id")]
        return comps, lessons, tests

    @a.route("/")
    def home(req):
        comps, lessons, tests = data()
        problems = core.gaps(comps, lessons, tests)
        loops = core.check_order(comps)
        order = core.sequence_problems(comps, lessons)
        errors = sum(1 for p in problems if p[0] == "error") + len(loops)
        balance = core.assessment_balance(tests)
        body = stats([("Competencies", len(comps)), ("Lessons", len(lessons)), ("Teaching hours", f"{sum(l.hours for l in lessons):g}"), ("Problems", errors)])
        body += card("Problems to fix", table(problems, [("Severity", lambda p: Raw(f'<span class="{"bad" if p[0] == "error" else "warn"}">{p[0]}</span>')), ("Competency", lambda p: p[1]), ("Problem", lambda p: p[2])], "No gaps found."))
        if loops or order:
            body += card("Order", "".join(f"<p>{h(x)}</p>" for x in loops + order))
        body += card("Coverage", table(core.coverage(comps, lessons, tests), [("Code", "code"), ("Competency", "title"), ("Hours", lambda r: f"{r['taught']:g} / {r['planned']:g}"), ("Taught to", "top_taught"), ("Assessed at", "top_assessed"), ("Weight", lambda r: f"{r['assessed']:g}%")], "Add competencies to begin."))
        body += card("Assessment by thinking level", bar_chart([(k, round(v * 100)) for k, v in balance.items()], unit="%"))
        if comps and not loops:
            body += card("A workable teaching order", "<p>" + " → ".join(h(c) for c in core.teaching_order(comps)) + "</p>")
        return a.page("Curriculum map", body)

    @a.route("/competencies", ("GET", "POST"))
    def competencies(req):
        if req.method == "POST":
            lvl = req.text("level")
            if lvl not in core.BLOOM:
                raise Fail("Unknown level")
            needs = [c.strip() for c in req.text("requires", False).split(",") if c.strip()]
            a.run("INSERT INTO competencies (code, title, hours, level, requires) VALUES (?, ?, ?, ?, ?)", req.text("code"), req.text("title"), req.number("hours", 0, 0), lvl, json.dumps(needs))
            return redirect("/competencies")
        return a.page("Competencies", card("Add", form(a, "/competencies", [("code", "Code, such as C1"), ("title", "Competency"), ("hours", "Planned hours", "number", 0), ("level", "Target level", "select", LEVELS), ("requires", "Prerequisite codes, separated by commas")], "Add")) + card("All", table(a.rows("SELECT * FROM competencies ORDER BY rowid"), [("Code", "code"), ("Title", "title"), ("Hours", "hours"), ("Level", "level"), ("Needs", lambda r: ", ".join(json.loads(r["requires"])))])))

    @a.route("/lessons", ("GET", "POST"))
    def lessons(req):
        if req.method == "POST":
            a.run("INSERT INTO lessons (title, hours, week, teaches) VALUES (?, ?, ?, ?)", req.text("title"), req.number("hours", low=0.1), int(req.number("week", low=1)), json.dumps(parse_links(req.text("teaches"))))
            return redirect("/lessons")
        return a.page("Lessons", card("Add", form(a, "/lessons", [("title", "Lesson"), ("week", "Week", "number", 1), ("hours", "Hours", "number", 2), ("teaches", "Teaches, such as C1:Apply, C2:Remember")], "Add")) + card("All", table(a.rows("SELECT * FROM lessons ORDER BY week, id"), [("Week", "week"), ("Lesson", "title"), ("Hours", "hours"), ("Teaches", lambda r: ", ".join(f"{k} ({v})" for k, v in json.loads(r["teaches"]).items()))])))

    @a.route("/assessments", ("GET", "POST"))
    def assessments(req):
        if req.method == "POST":
            a.run("INSERT INTO assessments (title, weight, covers) VALUES (?, ?, ?)", req.text("title"), req.number("weight", low=0, high=100), json.dumps(parse_links(req.text("covers"))))
            return redirect("/assessments")
        total = a.one("SELECT COALESCE(SUM(weight), 0) FROM assessments")
        return a.page("Assessments", card(f"Weights add up to {total:g}%", form(a, "/assessments", [("title", "Assessment"), ("weight", "Weight %", "number", 20), ("covers", "Covers, such as C1:Apply")], "Add")) + card("All", table(a.rows("SELECT * FROM assessments ORDER BY id"), [("Assessment", "title"), ("Weight", "weight"), ("Covers", lambda r: ", ".join(f"{k} ({v})" for k, v in json.loads(r["covers"]).items()))])))

    return a
