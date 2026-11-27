"""The release check as one self-contained HTML page, on the Leader Report's template and the Landing Loop's one
visual family.

The page uses the report's whole stylesheet, taken from its template (assets/vendor/template.html, vendored
byte-identical at a pinned commit), and draws its picture with svgkit (scripts/vendor/svgkit.py, vendored
byte-identical from landing-loop and pinned in VENDORED.json). Only a few rules for this page's layout are added.

It reads top down for someone who has never shipped software: the shared header, the call as the heading, the
check word, a row of gates (one per check: an outline with a tick is ready to ship, solid ink holds, and a waived
check carries the name of the person who OK'd it and the date it runs out), then one thing to do next, owned by
the person the landing brief names. The checks follow in two columns. The evidence ledger and everything
technical (check ids, file names, the record key, exit codes) sit in one fold. Public copy uses plain words.

ready to ship and hold are this check's own words and print in ink, with no status colour: green, grey-white and
red mean a project's landed, watch and stalled, which only did-it-land sets. Brass is a person's call: who
waived a check, and who decides the next step. Every figure is a display string of a figure computed in
readiness.py; the page computes nothing. Nothing is fetched, nothing depends on the clock, and every piece of
text from an input is escaped.

Standard library only. Python 3.11 or later.
"""

from __future__ import annotations

import html
import re
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent / "vendor"))

import readiness  # noqa: E402
import svgkit as sk  # noqa: E402  (vendored, unchanged; see VENDORED.json)

TEMPLATE = Path(__file__).resolve().parent.parent / "assets" / "vendor" / "template.html"
STYLE = re.compile(r"<style>(.*?)</style>", re.S)

# Layout for this page only. Everything else comes from the template's stylesheet and svgkit.CSS.
PAGE_CSS = """
main.solo{margin-left:0}
.solo .slide{min-height:0}
.solo .slide.cover{min-height:0;padding-top:40px;padding-bottom:48px;justify-content:flex-start}
.solo h1{font-size:clamp(34px,4.6vw,60px);line-height:1;letter-spacing:-.04em;max-width:20ch;margin-bottom:20px}
.solo .lede{margin-bottom:24px}
.solo h2{margin-bottom:16px}
.rw{display:inline-block;font:400 10px/16px var(--mono);letter-spacing:.1em;text-transform:uppercase;color:var(--t1);border:1px solid var(--line3);border-radius:3px;padding:1px 6px;white-space:nowrap}
.rw.hold{background:var(--t1);color:var(--bg);border-color:var(--t1)}
.verdict{margin:0 0 20px}
@media (min-width:1100px){.panel .sk{display:grid;grid-template-columns:720px minmax(0,1fr);gap:16px 40px;align-items:center}.panel .sk figcaption{margin-top:0;flex-direction:column;align-items:flex-start}}
.panel{border:1px solid var(--line);border-radius:12px;background:var(--s1);padding:28px 28px 20px}
.next{margin-top:28px;display:grid;grid-template-columns:200px minmax(0,1fr);gap:8px 32px;align-items:baseline;border:1px solid var(--brass);border-radius:12px;padding:20px 24px;background:var(--brass-bg)}
.next>b{font:400 10px/22px var(--mono);letter-spacing:.1em;text-transform:uppercase;color:var(--brass)}
.next p{margin:0;font-size:16px;line-height:1.5;color:var(--t1)}
.next .who{display:flex;flex-wrap:wrap;gap:4px 24px;margin-top:10px;font:400 11.5px/16px var(--mono);color:var(--brass)}
.next .who span::before{font-size:10px;letter-spacing:.1em;color:var(--t3);margin-right:8px}
.next .who .o::before{content:"DECIDES"}.next .who .d::before{content:"DUE"}
.cols{display:grid;grid-template-columns:minmax(0,1.15fr) minmax(0,1fr);gap:24px 56px;align-items:start}
.cols h3{margin-bottom:8px}
.checks{margin:0;padding:0;list-style:none}
.checks li{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:4px 16px;border-top:1px solid var(--line);padding:12px 0}
.checks .nm{font-size:14px;line-height:1.45;color:var(--t1)}
.checks .ev{grid-column:1;font-size:13px;line-height:1.5;color:var(--t2)}
.checks .ev b{color:var(--t1);font-weight:500}
.checks .ow{grid-column:1;font:400 10px/16px var(--mono);letter-spacing:.06em;text-transform:uppercase;color:var(--t3)}
.checks ul{grid-column:1;margin:2px 0 0;padding-left:16px;font-size:13px;line-height:1.5;color:var(--t2)}
.checks .rw{grid-row:1;grid-column:2;justify-self:end;align-self:start}
.wv{border-top:1px solid var(--line);padding:12px 0 4px}
.wv p{margin:0 0 8px;font-size:13.5px;line-height:1.55;color:var(--t2)}
.wv p b{color:var(--t1);font-weight:500}
.wv .by{display:flex;flex-wrap:wrap;gap:4px 24px;font:400 11.5px/16px var(--mono);color:var(--brass)}
.wv .by span::before{font-size:10px;letter-spacing:.1em;color:var(--t3);margin-right:8px}
.wv .by .a::before{content:"OK'D BY"}.wv .by .x::before{content:"UNTIL"}
.plain{margin:0;padding:0;list-style:none}
.plain li{border-top:1px solid var(--line);padding:11px 0;font-size:13px;line-height:1.5;color:var(--t2)}
.plain li small{display:block;font:400 10px/16px var(--mono);letter-spacing:.06em;text-transform:uppercase;color:var(--t3);margin-top:2px}
.side h3:not(:first-child){margin-top:28px}
.sc-d{font-size:12.5px;line-height:1.5;color:var(--t3);margin:0 0 8px}
.solo details{margin-top:4px}
.solo details>*:not(summary){margin-top:12px}
.solo details p,.solo details li{margin:0 0 10px;font-size:13px;color:var(--t2);max-width:80ch}
.solo details ul{padding-left:18px}
.tablewrap td,.tablewrap th{overflow-wrap:anywhere}
.tablewrap .ex{font-size:12px;color:var(--t3)}
::selection{background:var(--t1);color:var(--bg)}
:focus-visible{outline-color:var(--t1)}
.foot{max-width:1120px;margin:0 auto;padding:28px 40px 64px;color:var(--t3);font-size:12px}
@media (max-width:980px){.foot{padding:24px 16px 48px}.solo .slide.cover{padding-top:24px}.cols,.next{grid-template-columns:1fr}.panel{padding:20px 16px 16px}
.stack table,.stack tbody,.stack tr,.stack td{display:block}.stack tr:first-child{display:none}.stack tr{padding:10px 16px;border-bottom:1px solid var(--line)}
.stack td{border:0;padding:3px 0;display:grid;grid-template-columns:96px 1fr;gap:12px}.stack td.num{text-align:left;white-space:normal}
.stack td::before{content:attr(data-l);font:400 10px/20px var(--mono);letter-spacing:.1em;text-transform:uppercase;color:var(--t3)}}
"""


def e(text: Any) -> str:
    return html.escape(str(text), quote=True)


def stylesheet() -> str:
    """The report template's whole stylesheet, fonts included."""
    try:
        found = STYLE.search(TEMPLATE.read_text(encoding="utf-8"))
    except OSError:
        found = None
    return found.group(1) if found else ""


def word(w: str, waived: bool = False) -> str:
    """ready to ship or hold, as a plain mono word. Hold is inverted ink so it reads first; neither uses a status colour."""
    text = f"{w}, waived" if waived else w
    return f'<span class="rw{" hold" if w == readiness.HOLD else ""}">{e(text)}</span>'


def figs(c: dict) -> dict[str, Any]:
    return {f["id"].split(".", 1)[1]: f["value"] for f in c["figures"]}


def of(n: int, one: str, many: str) -> str:
    return f"{n} {one if n == 1 else many}"


def open_bugs(v: dict[str, Any]) -> list[tuple[str, Any]]:
    return [(k.split(".", 1)[1], n) for k, n in v.items() if k.startswith("open.") and n]


def evidence(c: dict) -> str:
    """One line of the check's own figures, as computed, in plain words. Nothing here is a new number."""
    v = figs(c)
    if c["id"] == "ci" and "required" in v:
        return f"<b>{v['passed']}</b> of {of(v['required'], 'required code check passes', 'required code checks pass')}"
    if c["id"] == "bugs" and v:
        found = open_bugs(v)
        return "Open: " + (", ".join(f"<b>{n}</b> {e(s)}" for s, n in found) if found else "<b>0</b>")
    if c["id"] == "flags" and "total" in v:
        top = f"; the first release stage reaches <b>{v['top_rollout']}%</b> of customers" if "top_rollout" in v else ""
        return f"<b>{v['off_switch']}</b> of {of(v['total'], 'change has', 'changes have')} an off switch{top}"
    if c["id"] == "rollback" and "test_age_days" in v:
        return f"Rehearsed <b>{v['test_age_days']}</b> days before this check"
    if c["id"] == "brief" and "days_to_date" in v:
        return f"<b>{v['days_to_date']}</b> days to the brief's date"
    if c["id"] == "evals" and "total" in v:
        return f"<b>{v['passing']}</b> of {of(v['total'], 'quality test passes', 'quality tests pass')}"
    if c["id"] == "spec" and "holds" in v:
        return f"<b>{v['closed']}</b> of {of(v['holds'], 'build plan hold', 'build plan holds')} closed"
    return "No input"


def short_figure(c: dict) -> str:
    """The figure under a gate: the same numbers evidence() prints, in fewer words."""
    v = figs(c)
    if c["id"] == "ci" and "required" in v:
        return f"{v['passed']} of {v['required']} pass"
    if c["id"] == "bugs" and v:
        found = open_bugs(v)
        return f"{found[0][1]} {found[0][0]} open" if found else "0 open"
    if c["id"] == "flags" and "total" in v:
        return f"{v['off_switch']} of {v['total']}"
    if c["id"] == "rollback" and "test_age_days" in v:
        return f"{v['test_age_days']} days ago"
    if c["id"] == "brief" and "days_to_date" in v:
        return f"{v['days_to_date']} days left"
    if c["id"] == "evals" and "total" in v:
        return f"{v['passing']} of {v['total']} pass"
    if c["id"] == "spec" and "holds" in v:
        return f"{v['closed']} of {v['holds']} closed"
    return "no input"


def fold(title: str, body: str) -> str:
    return f"<details><summary>{e(title)}</summary>{body}</details>"


class Table:
    """A table whose cells carry their column name, so a phone shows each row as labelled lines."""

    def __init__(self, heads: tuple[str, ...]) -> None:
        self.heads = heads
        self.rows: list[str] = []

    def row(self, *cells: tuple[str, str]) -> None:
        tds = []
        for head, (cls, body) in zip(self.heads, cells, strict=True):
            attr = f' class="{cls}"' if cls else ""
            tds.append(f'<td{attr} data-l="{e(head)}">{body}</td>')
        self.rows.append("<tr>" + "".join(tds) + "</tr>")

    def html(self) -> str:
        head = "<tr>" + "".join(f"<th>{e(h)}</th>" for h in self.heads) + "</tr>"
        return f'<div class="tablewrap stack"><table>{head}{"".join(self.rows)}</table></div>'


# The signature picture


def answer(d: dict) -> str:
    """The aria-label: the call and why, in one sentence."""
    lead = f"{d['release']} is ready to ship" if d["readiness"] == readiness.READY else f"{d['release']} must hold"
    text = f"{lead}: {d['ready']} of {d['total']} checks are ready to ship"
    if d["holds"]:
        names = [readiness.SHORT.get(o["id"], o["label"]).lower() for o in d["holds"]]
        listed = names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1]
        text += f", and {listed} {'holds' if len(names) == 1 else 'hold'}"
    for w in d["waived"]:
        text += f"; {readiness.SHORT.get(w['id'], w['label']).lower()} holds under a waiver from {w['approved_by']} until {w['expires']}"
    return text + "."


def gates(d: dict, variant: str) -> str:
    """One gate per check, in the order they run. Ready: an outline with a tick. Hold: solid ink. A waived check
    carries the approver's name and the date the waiver runs out, in brass, because a waiver is a person's call."""
    waived = {w["id"]: w for w in d["waived"]}
    checks = d["checks"]
    parts: list[str] = []
    if variant == "wide":
        width = float(sk.WIDE)
        cw = width / len(checks)
        size, gy = 30.0, 4.0
        cy = gy + size / 2
        parts.append(sk.rule(cw / 2, cy, width - cw / 2, cy, tone=sk.LINE2))
        tag_at = None
        for i, c in enumerate(checks):
            cx = cw * i + cw / 2
            parts.append(sk.gate(cx - size / 2, gy, state="hold" if c["readiness"] == readiness.HOLD else "ready", size=size))
            parts.append(sk.label(cx, gy + size + 22, readiness.SHORT.get(c["id"], c["id"]), anchor="middle", tone=sk.INK))
            parts.append(sk.value(cx, gy + size + 42, short_figure(c), anchor="middle", tone=sk.INK2, size=13))
            if c["readiness"] == readiness.HOLD and c["id"] not in waived:
                parts.append(sk.label(cx, gy + size + 62, "hold", anchor="middle", tone=sk.INK))
            if c["id"] in waived and tag_at is None:
                tag_at = (cx, waived[c["id"]])
        height = gy + size + 70
        if tag_at:
            cx, w = tag_at
            top = height
            who = f"Waived by {w['approved_by']}"
            until = f"until {w['expires']}"
            span = 30 + max(len(who) * 7.6, sk.label_width(until))
            left = cx - 8 if cx - 8 + span <= width else width - span
            parts.append(sk.rule(cx, gy + size + 52, cx, top + 6, tone=sk.BRASS, width=sk.STROKE))
            parts.append(sk.person(left + 8, top + 26, size=14))
            parts.append(sk.value(left + 24, top + 18, who, tone=sk.BRASS, size=14))
            parts.append(sk.label(left + 24, top + 36, until, tone=sk.BRASS))
            height = top + 42
    else:
        width = float(sk.TALL)
        size, step, top = 22.0, 46.0, 2.0
        rows: list[tuple[dict, float]] = []
        y = top
        for c in checks:
            rows.append((c, y))
            y += step + (44 if c["id"] in waived else 0)
        last_c, last_y = rows[-1]
        height = last_y + (size + 30 if last_c["id"] in waived else size + 8)
        parts.append(sk.rule(size / 2, top + size / 2, size / 2, last_y + size / 2, tone=sk.LINE2))
        for c, ry in rows:
            hold = c["readiness"] == readiness.HOLD
            parts.append(sk.gate(0, ry, state="hold" if hold else "ready", size=size))
            parts.append(sk.label(36, ry + 15, readiness.SHORT.get(c["id"], c["id"]), tone=sk.INK))
            if hold and c["id"] not in waived:
                parts.append(sk.label(width, ry + 15, "hold", anchor="end", tone=sk.INK))
                parts.append(sk.value(width - 44, ry + 16, short_figure(c), anchor="end", tone=sk.INK2, size=13))
            else:
                parts.append(sk.value(width, ry + 16, short_figure(c), anchor="end", tone=sk.INK2, size=13))
            if c["id"] in waived:
                w = waived[c["id"]]
                parts.append(sk.person(43, ry + 56, size=13))
                parts.append(sk.value(56, ry + 49, f"Waived by {w['approved_by']}", tone=sk.BRASS, size=13))
                parts.append(sk.label(56, ry + 66, f"until {w['expires']}", tone=sk.BRASS))
    return sk.frame("".join(parts), label=answer(d), height=height, width=width, variant=variant)


# The words


def lede(d: dict) -> str:
    text = f"{d['ready']} of {d['total']} checks are ready to ship on the version checked {d['as_of']}."
    for w in d["waived"]:
        text += f" The {readiness.SHORT.get(w['id'], w['label']).lower()} check fails, and {w['approved_by']} has OK'd shipping anyway until {w['expires']}."
    if d["holds"]:
        text += " Every check must be ready before anything ships."
    return text


def checks_list(d: dict) -> str:
    waived = {w["id"] for w in d["waived"]}
    items = []
    for c in d["checks"]:
        reasons = "".join(f"<li>{e(readiness.plain(r))}</li>" for r in c["reasons"])
        items.append(
            f'<li><span class="nm">{e(readiness.PLAIN_LABELS.get(c["id"], c["label"]))}</span>{word(c["readiness"], c["id"] in waived)}'
            f'<span class="ev">{evidence(c)}</span>{f"<ul>{reasons}</ul>" if reasons else ""}'
            f'<span class="ow">Owner: {e(c["owner"])}</span></li>'
        )
    return f'<ul class="checks">{"".join(items)}</ul>'


def side(d: dict) -> str:
    out = []
    if d["waived"]:
        boxes = "".join(
            f'<div class="wv"><p><b>{e(readiness.PLAIN_LABELS.get(w["id"], w["label"]))}.</b> {e(w["reason"])}</p>'
            f'<span class="by"><span class="a">{e(w["approved_by"])}</span><span class="x">{e(w["expires"])}</span></span></div>'
            for w in d["waived"]
        )
        out.append(f"<h3>The waiver</h3><p class='sc-d'>{e(readiness.WAIVER_MEANS)} The check still reads hold until its owner fixes it.</p>{boxes}")
    if d["spec_holds"]:
        rows = []
        for h in d["spec_holds"]:
            by = readiness.SHORT.get(h["closed_by"], h["closed_by"]).lower() if h["closed_by"] else ""
            state = f"Closed: the {by} check is ready" if h["closed"] else (f"Open: the {by} check holds" if by else "Open: no check here closes it")
            rows.append(f"<li>{e(readiness.plain(h['message']))}<small>{e(state)}</small></li>")
        lede = "spec-auditor held the build plan on these points. Each closes only when the check here that tests the same thing is ready to ship."
        out.append(f"<h3>Build plan holds</h3><p class='sc-d'>{e(lede)}</p><ul class='plain'>{''.join(rows)}</ul>")
    if d["brief"]:
        b = d["brief"]
        out.append(
            f"<h3>The plan behind it</h3><p class='sc-d'>This release serves {e(readiness.BRIEF_MEANS)}.</p><ul class='plain'>"
            f"<li>{e(b['metric'])}: target {e(b['bar'])}, {e(b['better'])} is better, due {e(b['by'])}.<small>did-it-land reads it after launch</small></li></ul>"
        )
    notes = readiness.worth_knowing(d)
    if notes:
        out.append("<h3>Worth knowing</h3><ul class='plain'>" + "".join(f"<li>{e(n)}</li>" for n in notes) + "</ul>")
    return f'<div class="side">{"".join(out)}</div>'


def engineers(d: dict) -> str:
    eng = [f"<p>Commit <code>{e(d['commit'] or 'not named')}</code>. Tool: {e(d['tool'])}.</p>"]
    t = Table(("Check id", "Label as stored", "Check word", "Reasons as computed"))
    for c in d["checks"]:
        t.row(("", f"<code>{e(c['id'])}</code>"), ("", e(c["label"])), ("", e(c["readiness"])), ("ex", "<br>".join(e(r) for r in c["reasons"]) or "none"))
    eng.append(t.html())
    raw = [n for c in d["checks"] for n in c["notes"]] + d["waiver_problems"] + [f"Policy changed from the default: {p}" for p in d["policy_changes"]]
    if raw:
        eng.append("<p>Notes as computed:</p><ul>" + "".join(f"<li>{e(n)}</li>" for n in raw) + "</ul>")
    if d["spec_holds"]:
        held = "; ".join(f"<code>{e(h['finding'])}</code> closed by <code>{e(h['closed_by'] or 'no check')}</code>" for h in d["spec_holds"])
        eng.append(f"<p>Spec holds as stored: {held}.</p>")
    if d["bet"]:
        eng.append(f"<p>With --loop and --bet, the run adds its page to the project file: the <code>release</code> key of <code>landing/{e(d['bet'])}.json</code>, and no other key.</p>")
    eng.append("<p>readiness.py exits 0 on ready to ship, 1 on hold and 2 when an input cannot be read, so it can gate a CI job.</p>")
    eng.append(ledger(d))
    return fold("For your engineers", "".join(eng))


def ledger(d: dict) -> str:
    t = Table(("ID", "Figure", "Value", "Window", "Source"))
    for c in d["checks"]:
        for f in c["figures"]:
            t.row(("", f"<code>{e(f['id'])}</code>"), ("", e(f["label"])), ("num", e(readiness.shown(f))), ("", e(readiness.window(f))), ("ex", e(f["source"])))
    return "<p>Every figure, with its source:</p>" + t.html()


def page(d: dict) -> str:
    header = sk.page_header("release-readiness", date=d["as_of"], version=f"v{readiness.VERSION}", illustrative=d["illustrative"])
    pic = sk.figure(
        gates(d, "wide"),
        gates(d, "tall"),
        caption="One gate per check, in the order they run. An outline with a tick is ready to ship; a solid block holds."
        + (" The waived check carries the name of the person who OK'd it and the date the waiver runs out." if d["waived"] else ""),
        illustrative=d["illustrative"],
    )
    step = (
        f'<div class="next"><b>What to do next</b><div><p>{e(readiness.plain_next_step(d))}</p>'
        f'<span class="who"><span class="o">{e(d["decides"])}</span><span class="d">{e(readiness.due(d))}</span></span></div></div>'
    )
    cover = (
        f'<section class="slide cover">{header}<h1>{e(readiness.verdict(d))}</h1>'
        f'<p class="lede">{e(lede(d))}</p><p class="verdict">{word(d["readiness"])}</p>'
        f'<div class="panel">{pic}</div>{step}</section>'
    )
    detail = (
        '<section class="slide"><div class="meta"><span>The checks</span></div><div class="cols">'
        f"<div><h3>Every check</h3>{checks_list(d)}</div>{side(d)}</div></section>"
    )
    more = f'<section class="slide"><div class="meta"><span>Detail</span></div>{engineers(d)}</section>'
    title = f"Release readiness: {d['release']}"
    return (
        '<!doctype html><html lang="en-GB"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
        f'<title>{e(title)}</title><style>{stylesheet()}{sk.CSS}{PAGE_CSS}</style></head><body><main class="solo">{cover}{detail}{more}'
        '<p class="foot">A release check says whether this version is ready to ship, not whether the project will work. '
        "did-it-land reads the number against the target after launch. Every figure is computed in code from the sources named.</p>"
        "</main></body></html>\n"
    )
