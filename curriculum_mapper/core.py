"""Curriculum logic: is every competency taught, practised and assessed, in a workable order?

Teaching, learning activities and assessment should line up (Biggs' constructive alignment).
A competency that is taught but never assessed, or assessed at a higher level than it was
taught, is a problem a map can show long before a class meets it.
"""
from collections import defaultdict
from dataclasses import dataclass, field

BLOOM = ("Remember", "Understand", "Apply", "Analyse", "Evaluate", "Create")


@dataclass
class Competency:
    code: str
    title: str
    hours: float = 0.0
    level: str = "Apply"
    requires: tuple = ()


@dataclass
class Lesson:
    id: int
    title: str
    hours: float
    teaches: dict = field(default_factory=dict)     # {competency code: Bloom level}
    week: int = 0


@dataclass
class Assessment:
    id: int
    title: str
    weight: float
    covers: dict = field(default_factory=dict)      # {competency code: Bloom level}


def level_of(name):
    if name not in BLOOM:
        raise ValueError(f"unknown Bloom level: {name}")
    return BLOOM.index(name)


def coverage(competencies, lessons, assessments):
    """One row per competency: taught hours, levels reached, and assessment share."""
    rows = {}
    for c in competencies:
        rows[c.code] = {"code": c.code, "title": c.title, "planned": c.hours, "target": c.level, "taught": 0.0, "lessons": 0, "top_taught": None, "top_assessed": None, "assessed": 0.0}
    for l in lessons:
        share = l.hours / len(l.teaches) if l.teaches else 0
        for code, lvl in l.teaches.items():
            if code in rows:
                r = rows[code]
                r["taught"] += share
                r["lessons"] += 1
                if r["top_taught"] is None or level_of(lvl) > level_of(r["top_taught"]):
                    r["top_taught"] = lvl
    for a in assessments:
        share = a.weight / len(a.covers) if a.covers else 0
        for code, lvl in a.covers.items():
            if code in rows:
                r = rows[code]
                r["assessed"] += share
                if r["top_assessed"] is None or level_of(lvl) > level_of(r["top_assessed"]):
                    r["top_assessed"] = lvl
    return list(rows.values())


def gaps(competencies, lessons, assessments, hours_tolerance=0.2):
    """Plain-language problems in the map, as (severity, competency, message)."""
    known = {c.code for c in competencies}
    out = []
    for r in coverage(competencies, lessons, assessments):
        code = r["code"]
        if r["lessons"] == 0:
            out.append(("error", code, "is never taught"))
        if r["top_assessed"] is None:
            out.append(("error", code, "is never assessed"))
        if r["top_taught"] and r["top_assessed"] and level_of(r["top_assessed"]) > level_of(r["top_taught"]):
            out.append(("error", code, f"is assessed at {r['top_assessed']} but taught only to {r['top_taught']}"))
        if r["top_taught"] and level_of(r["top_taught"]) < level_of(r["target"]):
            out.append(("warning", code, f"targets {r['target']} but reaches only {r['top_taught']}"))
        if r["planned"] and r["lessons"]:
            diff = (r["taught"] - r["planned"]) / r["planned"]
            if abs(diff) > hours_tolerance:
                out.append(("warning", code, f"has {r['taught']:g} teaching hours against {r['planned']:g} planned"))
    for l in lessons:
        for code in l.teaches:
            if code not in known:
                out.append(("error", code, f"is used by lesson {l.title} but is not defined"))
    for a in assessments:
        for code in a.covers:
            if code not in known:
                out.append(("error", code, f"is used by {a.title} but is not defined"))
    return out


def check_order(competencies):
    """Find prerequisites that do not exist and prerequisite loops. Returns problems."""
    by = {c.code: c for c in competencies}
    problems = [f"{c.code} requires {r}, which is not defined" for c in competencies for r in c.requires if r not in by]
    state = {}

    def visit(code, path):
        state[code] = 1
        for r in by[code].requires:
            if r not in by:
                continue
            if state.get(r) == 1:
                problems.append("loop: " + " -> ".join(path[path.index(r):] + [r]) if r in path else f"loop at {r}")
            elif r not in state:
                visit(r, path + [r])
        state[code] = 2
    for c in competencies:
        if c.code not in state:
            visit(c.code, [c.code])
    return problems


def teaching_order(competencies):
    """A valid order: prerequisites first, keeping the given order where free (Kahn's algorithm)."""
    by = {c.code: c for c in competencies}
    waiting = {c.code: sum(1 for r in c.requires if r in by) for c in competencies}
    users = defaultdict(list)
    for c in competencies:
        for r in c.requires:
            if r in by:
                users[r].append(c.code)
    position = {c.code: i for i, c in enumerate(competencies)}
    ready = sorted((k for k, n in waiting.items() if n == 0), key=position.get)
    out = []
    while ready:
        code = ready.pop(0)
        out.append(code)
        for u in users[code]:
            waiting[u] -= 1
            if waiting[u] == 0:
                ready.append(u)
                ready.sort(key=position.get)
    if len(out) != len(competencies):
        raise ValueError("prerequisites form a loop")
    return out


def sequence_problems(competencies, lessons):
    """Lessons that teach something before its prerequisite has been taught."""
    first = {}
    for l in sorted(lessons, key=lambda x: x.week):
        for code in l.teaches:
            first.setdefault(code, l.week)
    out = []
    for c in competencies:
        for r in c.requires:
            if c.code in first and (r not in first or first[r] > first[c.code]):
                out.append(f"{c.code} is taught in week {first[c.code]}, before its prerequisite {r}")
    return out


def assessment_balance(assessments):
    """Share of assessment weight at each Bloom level, to spot a course that only tests recall."""
    totals = defaultdict(float)
    for a in assessments:
        if a.covers:
            share = a.weight / len(a.covers)
            for lvl in a.covers.values():
                totals[lvl] += share
    whole = sum(totals.values())
    return {lvl: totals[lvl] / whole for lvl in BLOOM if totals[lvl]} if whole else {}


def plan_hours(lessons, week_hours):
    """Check each week's teaching hours against the time available."""
    used = defaultdict(float)
    for l in lessons:
        used[l.week] += l.hours
    return {w: h for w, h in sorted(used.items()) if h > week_hours}
