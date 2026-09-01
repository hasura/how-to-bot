from __future__ import annotations

import argparse
from collections import defaultdict
from html import escape
import json
from pathlib import Path
import shutil
import tempfile

import yaml

ROOT = Path(__file__).resolve().parents[1]
TUTORIALS = ROOT / "tutorials"
DEFAULT_OUTPUT = ROOT / "site" / "dist"
STYLES = ROOT / "site" / "styles.css"


def load_tutorials() -> list[dict]:
    tutorials = []
    for manifest in sorted(TUTORIALS.glob("*/tutorial.yaml")):
        data = yaml.safe_load(manifest.read_text())
        data["_path"] = str(manifest.parent.relative_to(ROOT))
        tutorials.append(data)
    return tutorials


def slug(value: str) -> str:
    return "".join(character if character.isalnum() else "-" for character in value.casefold()).strip("-")


def chips(values: list[str], kind: str = "") -> str:
    class_name = f"chip {kind}".strip()
    return "".join(f'<span class="{class_name}">{escape(value)}</span>' for value in values)


def status_label(status: str) -> str:
    return status.replace("_", " ").title()


def shell() -> tuple[str, str]:
    head = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="description" content="How to Bot: verified operational playbooks for persistent workplace bots.">
<title>{title}</title>
<link rel="stylesheet" href="{prefix}styles.css">
</head>
<body>
<a class="skip" href="#main">Skip to content</a>
<header class="topbar">
  <a class="brand" href="{prefix}index.html" aria-label="How to Bot home">
    <span class="brand-mark" aria-hidden="true">H</span>
    <span>How to Bot</span>
  </a>
  <nav aria-label="Primary">
    <a href="{prefix}index.html#library">Library</a>
    <a href="{prefix}index.html#standard">Standard</a>
    <a href="https://github.com/hasura/how-to-bot">GitHub</a>
  </nav>
</header>
<main id="main">
"""
    foot = """
</main>
<footer>
  <p><strong>How to Bot</strong> · Open operational playbooks, not prompt snippets.</p>
  <p>Apache-2.0 · <a href="https://github.com/hasura/how-to-bot">Source and contribution guide</a></p>
</footer>
<script>
for (const button of document.querySelectorAll('[data-view]')) {
  button.addEventListener('click', () => {
    const view = button.dataset.view;
    document.querySelectorAll('[data-view]').forEach(item => {
      item.classList.toggle('active', item === button);
      item.setAttribute('aria-pressed', String(item === button));
    });
    document.querySelectorAll('[data-kind]').forEach(section => {
      section.hidden = section.dataset.kind !== view;
    });
  });
}
</script>
</body>
</html>
"""
    return head, foot


def tutorial_card(tutorial: dict) -> str:
    ownership = tutorial["ownership"]
    return f"""
<article class="tutorial-card">
  <div class="card-meta">
    <span class="mode {ownership['mode'].casefold()}">{escape(ownership['mode'])}</span>
    <span class="risk">{escape(tutorial['risk']['tier'])}</span>
    <span class="status">{escape(status_label(tutorial['status']))}</span>
  </div>
  <h3><a href="tutorials/{escape(tutorial['id'])}.html">{escape(tutorial['title'])}</a></h3>
  <p>{escape(ownership['responsibility'])}</p>
  <dl class="compact">
    <div><dt>Owns</dt><dd>{escape(ownership['owned_object'])}</dd></div>
    <div><dt>Done when</dt><dd>{escape(ownership['healthy_or_done_condition'])}</dd></div>
  </dl>
  <div class="card-chips">{chips(tutorial['discovery']['patterns'][:2], 'pattern')}</div>
  <a class="card-action" href="tutorials/{escape(tutorial['id'])}.html">Open playbook <span aria-hidden="true">→</span></a>
</article>
"""


def grouped_view(tutorials: list[dict], key: str, label: str) -> str:
    groups: dict[str, list[dict]] = defaultdict(list)
    for tutorial in tutorials:
        for value in tutorial["discovery"][key]:
            groups[value].append(tutorial)
    sections = []
    for value, members in sorted(groups.items()):
        sections.append(
            f"""
<section class="catalog-group" id="{slug(label)}-{slug(value)}">
  <div class="group-heading">
    <p class="eyebrow">{escape(label)}</p>
    <h3>{escape(value)}</h3>
    <span>{len(members)} playbook{'s' if len(members) != 1 else ''}</span>
  </div>
  <div class="card-grid">{''.join(tutorial_card(item) for item in members)}</div>
</section>
"""
        )
    return "".join(sections)


def build_index(tutorials: list[dict]) -> str:
    head, foot = shell()
    index = head.format(title="How to Bot — Operational playbooks for workplace bots", prefix="")
    index += """
<section class="hero">
  <div class="hero-copy">
    <p class="eyebrow">The open operating manual for persistent workplace bots</p>
    <h1>Teach a bot to own an outcome—not just run a prompt.</h1>
    <p class="lede">Verified playbooks for delegating bounded, observable work. Every tutorial
    specifies permissions, evidence, approvals, state, tests, recovery, and a stop path.</p>
    <div class="hero-actions">
      <a class="button primary" href="#library">Explore the library</a>
      <a class="button secondary" href="https://github.com/hasura/how-to-bot">View the standard</a>
    </div>
  </div>
  <aside class="operating-model" aria-label="Operating model">
    <p class="eyebrow">The recurring contract</p>
    <ol>
      <li><span>01</span> Authorized trigger</li>
      <li><span>02</span> Approved sources + provenance</li>
      <li><span>03</span> Bounded output or transaction</li>
      <li><span>04</span> Human or deterministic gate</li>
      <li><span>05</span> Exception routing</li>
      <li><span>06</span> Measurement + feedback</li>
    </ol>
  </aside>
</section>
<section class="notice" aria-label="Repository status">
  <strong>Foundation first cut</strong>
  <span>Runnable with synthetic data. Author-side checks pass; independent v0.4 review is still required before publication claims.</span>
</section>
<section class="framework" id="standard">
  <div>
    <p class="eyebrow">One library, three ways in</p>
    <h2>Find the right delegation from where you stand.</h2>
  </div>
  <div class="framework-grid">
    <article><span class="number">Who</span><h3>Role</h3><p>The person or team handing off responsibility.</p></article>
    <article><span class="number">What</span><h3>Playbook</h3><p>The concrete job and bounded outcome the bot owns.</p></article>
    <article><span class="number">How</span><h3>Pattern</h3><p>The reusable operational mechanism underneath the job.</p></article>
  </div>
  <div class="ownership-grid">
    <article><span class="mode maintain">MAINTAIN</span><h3>Ongoing control loop</h3><p>Keep an owned object within a defined healthy condition.</p></article>
    <article><span class="mode complete">COMPLETE</span><h3>Bounded mission</h3><p>Reach a verifiable done condition, then stop.</p></article>
  </div>
</section>
"""
    index += f"""
<section class="library" id="library">
  <div class="library-heading">
    <div><p class="eyebrow">Canonical tutorial library</p><h2>Browse verified operating contracts.</h2></div>
    <div class="view-switcher" role="group" aria-label="Browse library by">
      <button class="active" type="button" data-view="playbooks" aria-pressed="true">Playbook</button>
      <button type="button" data-view="roles" aria-pressed="false">Role</button>
      <button type="button" data-view="patterns" aria-pressed="false">Pattern</button>
    </div>
  </div>
  <div data-kind="playbooks">{grouped_view(tutorials, 'playbooks', 'Playbook')}</div>
  <div data-kind="roles" hidden>{grouped_view(tutorials, 'roles', 'Role')}</div>
  <div data-kind="patterns" hidden>{grouped_view(tutorials, 'patterns', 'Pattern')}</div>
</section>
<section class="progressive">
  <p class="eyebrow">Progressive disclosure</p>
  <h2>Start small. Earn the right to operate.</h2>
  <div class="steps">
    <article><span>1</span><h3>Try it</h3><p>Run a bounded example with synthetic fixtures and inspect the result.</p></article>
    <article><span>2</span><h3>Run it repeatedly</h3><p>Prove behavior across replay, failure, recovery, and evaluation.</p></article>
    <article><span>3</span><h3>Operate it safely</h3><p>Understand permission, approval, monitoring, escalation, and stop boundaries.</p></article>
  </div>
</section>
"""
    return index + foot


def list_items(values: list[str]) -> str:
    return "<ul>" + "".join(f"<li>{escape(item)}</li>" for item in values) + "</ul>"


def build_tutorial(tutorial: dict) -> str:
    head, foot = shell()
    page = head.format(title=f"{tutorial['title']} — How to Bot", prefix="../")
    ownership = tutorial["ownership"]
    progression = tutorial["progression"]
    page += f"""
<article class="tutorial-page">
  <header class="tutorial-hero">
    <a class="back" href="../index.html#library">← Tutorial library</a>
    <div class="card-meta">
      <span class="mode {ownership['mode'].casefold()}">{escape(ownership['mode'])}</span>
      <span class="risk">{escape(tutorial['risk']['tier'])}</span>
      <span class="status">{escape(status_label(tutorial['status']))}</span>
      <span>v{escape(tutorial['version'])}</span>
    </div>
    <h1>{escape(tutorial['title'])}</h1>
    <p class="lede">{escape(ownership['responsibility'])}</p>
    <div class="taxonomy">
      <div><strong>Roles</strong>{chips(tutorial['discovery']['roles'])}</div>
      <div><strong>Playbooks</strong>{chips(tutorial['discovery']['playbooks'])}</div>
      <div><strong>Patterns</strong>{chips(tutorial['discovery']['patterns'], 'pattern')}</div>
    </div>
  </header>
  <section class="outcome-contract">
    <div><p class="eyebrow">Owned object</p><p>{escape(ownership['owned_object'])}</p></div>
    <div><p class="eyebrow">Healthy / done condition</p><p>{escape(ownership['healthy_or_done_condition'])}</p></div>
  </section>
  <section class="tutorial-section">
    <p class="eyebrow">Progressive tutorial</p>
    <h2>From first run to safe operation.</h2>
    <div class="tutorial-steps">
"""
    stage_labels = [
        ("try_it", "01", "Try it"),
        ("run_repeatedly", "02", "Run it repeatedly"),
        ("operate_safely", "03", "Operate it safely"),
    ]
    for key, number, label in stage_labels:
        stage = progression[key]
        page += f"""
<article>
  <span class="stage-number">{number}</span>
  <div><h3>{label}</h3><p>{escape(stage['goal'])}</p>{list_items(stage['actions'])}
  <p class="exit"><strong>Exit:</strong> {escape(stage['exit_condition'])}</p></div>
</article>
"""
    page += f"""
    </div>
  </section>
  <div class="detail-grid">
    <section class="tutorial-section">
      <p class="eyebrow">Verification evidence</p>
      <h2>How you know.</h2>
      {list_items(ownership['verification_evidence'])}
    </section>
    <section class="tutorial-section boundary">
      <p class="eyebrow">Stop · approve · escalate</p>
      <h2>Where autonomy ends.</h2>
      {list_items(ownership['stop_approval_escalation_boundary'])}
    </section>
  </div>
  <section class="tutorial-section contract">
    <p class="eyebrow">Operational contract</p>
    <h2>What this playbook guarantees—and does not.</h2>
    <div class="contract-grid">
      <div><h3>Success criteria</h3>{list_items(tutorial['outcome']['success_criteria'])}</div>
      <div><h3>Unacceptable outcomes</h3>{list_items(tutorial['outcome']['unacceptable_outcomes'])}</div>
      <div><h3>Non-goals</h3>{list_items(tutorial['outcome']['non_goals'])}</div>
      <div><h3>Limitations</h3>{list_items(tutorial['outcome']['limitations'])}</div>
    </div>
  </section>
  <section class="source-callout">
    <div><p class="eyebrow">Inspect and reproduce</p><h2>The readable page is not the source of truth.</h2>
    <p>This page is generated from the validated manifest. Review the full permissions,
    approvals, threat model, evaluation, failure matrix, and implementation in the repository.</p></div>
    <a class="button primary" href="https://github.com/hasura/how-to-bot/tree/main/{escape(tutorial['_path'])}">Open source files</a>
  </section>
</article>
"""
    return page + foot


def catalog_data(tutorials: list[dict]) -> list[dict]:
    fields = ("id", "title", "version", "status", "discovery", "ownership", "progression", "risk")
    return [{field: tutorial[field] for field in fields} for tutorial in tutorials]


def build(output: Path) -> None:
    tutorials = load_tutorials()
    if output.exists():
        shutil.rmtree(output)
    (output / "tutorials").mkdir(parents=True)
    (output / "index.html").write_text(build_index(tutorials))
    (output / "styles.css").write_text(STYLES.read_text())
    (output / "catalog.json").write_text(
        json.dumps(catalog_data(tutorials), indent=2, sort_keys=True) + "\n"
    )
    for tutorial in tutorials:
        (output / "tutorials" / f"{tutorial['id']}.html").write_text(
            build_tutorial(tutorial)
        )


def compare_directories(expected: Path, actual: Path) -> list[str]:
    expected_files = {
        path.relative_to(expected): path.read_bytes()
        for path in expected.rglob("*")
        if path.is_file()
    }
    actual_files = {
        path.relative_to(actual): path.read_bytes()
        for path in actual.rglob("*")
        if path.is_file()
    }
    errors = []
    for path in sorted(set(expected_files) | set(actual_files)):
        if path not in expected_files:
            errors.append(f"unexpected generated file: {path}")
        elif path not in actual_files:
            errors.append(f"missing generated file: {path}")
        elif expected_files[path] != actual_files[path]:
            errors.append(f"stale generated file: {path}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if args.check:
        with tempfile.TemporaryDirectory() as temporary:
            candidate = Path(temporary) / "dist"
            build(candidate)
            errors = compare_directories(candidate, args.output)
        if errors:
            print("\n".join(errors))
            return 1
        print("Generated site is current.")
        return 0
    build(args.output)
    try:
        display_output = args.output.relative_to(ROOT)
    except ValueError:
        display_output = args.output
    print(f"Built {len(load_tutorials())} tutorial(s) in {display_output}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())