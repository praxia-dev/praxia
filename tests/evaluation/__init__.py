"""Evaluation suite — regression-prevention scenario tests.

Run with:
    pytest tests/evaluation/ -m evaluation -q

Each module in this package focuses on one feature area and exhaustively
covers boundary conditions, invariants, and known-bad inputs. The goal
is **detect regressions before merge** — if any test here fails, do not
ship.

Modules:
    test_eval_auth.py        — authentication + RBAC + ACL
    test_eval_memory.py      — memory backends + mode + admin policy
    test_eval_composite.py   — multi-LTM fusion + routing
    test_eval_skills.py      — skill registry + output format detection
    test_eval_exporters.py   — output exporters (md / html / pptx / docx / json)
    test_eval_oauth.py       — per-user OAuth token store + flow
    test_eval_parsers.py     — file parsers (PDF / Office / CSV / HTML / TXT)
    test_eval_cli.py         — CLI smoke tests for all major commands
    test_eval_extensions.py  — Registry primitive + entry-point discovery
"""
