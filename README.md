# Curriculum Mapper

Check a course before it reaches a classroom. Map each competency to its lessons and assessments, and the tool shows what is missing, misaligned or out of order. It suits competency-based courses and learning materials (CBLM), and it runs offline.

```
python -m curriculum_mapper
```

Then open http://127.0.0.1:8029. It needs Python 3.10 or newer.

## How to use it

1. Add **competencies** with planned hours, a target Bloom level and any prerequisites.
2. Add **lessons** with their week, hours and links, such as `C1:Apply, C2:Remember`.
3. Add **assessments** in the same way, with a weight.
4. Read the map.

## What it finds

| Problem | Example |
|---|---|
| Never taught | A competency with no lesson |
| Never assessed | Taught, but nobody checks it |
| Misaligned | Assessed at Analyse, taught only to Remember |
| Target not reached | Aims for Create, stops at Apply |
| Hours mismatch | 10 hours taught against 4 planned |
| Bad order | Taught in week 1, before a prerequisite in week 3 |
| Prerequisite loops | A needs B, B needs C, C needs A |

It also shows how assessment weight is spread across thinking levels, to reveal a course that only tests recall, and it gives a workable teaching order.

This follows constructive alignment (Biggs): what you teach, what learners do, and what you assess should match.

## How it is tested

Each kind of gap has its own case, and a clean map must show none. The teaching order is checked on 100 random prerequisite graphs, and loops must be reported without breaking the page.

## Limits

The map only knows what you enter. A lesson marked "Apply" may not really reach that level, so it supports a teacher's judgement and does not replace it. There are no multi-course or multi-user features. Hours are split evenly across a lesson's competencies, which is an approximation.

## Tests

```
python -m unittest discover -s tests
```

MIT licence.
