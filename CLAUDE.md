# Agent Instructions

`template/` is the payload `install.py` copies into new projects. Keep it free
of any particular language, project, or person: `{{YEAR}}` and
`{{COPYRIGHT_HOLDER}}` in `template/LICENSE` are filled in at install time.

Verify a change with `python3 -m unittest discover -s tests`. The kit and the
tools it ships use the Python standard library alone, because `python3` is the
only thing a project of any language can be asked to have.
