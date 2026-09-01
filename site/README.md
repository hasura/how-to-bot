# Static site

`site/dist/` is a deterministic, dependency-light build of the canonical tutorial
manifests. Do not hand-edit generated files.

```bash
uv run python tools/build_site.py
uv run python tools/build_site.py --check
python -m http.server 8000 --directory site/dist
```

The site uses no external JavaScript, CSS, fonts, analytics, credentials, or live data.
The role, playbook, pattern, ownership, and progressive tutorial views come directly
from each validated `tutorial.yaml`.