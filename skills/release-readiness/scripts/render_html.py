"""The release check as one self-contained HTML page, in the Leader Report style guide.

The page uses the report's own stylesheet, taken whole from its template (assets/vendor/template.html, vendored
byte-identical at a pinned commit), so it is the same brand family as the deck: the same fonts, tokens, hairline
rows and scorecard grid. It follows the report's references/design.md:

  - labels in mono capitals, sentences in sans; hairlines, not boxes
  - ready to ship and hold are this check's own words and print plainly, in ink, with no status colour.
    Green, grey-white and red mean a bet's landed, watch or stalled, which only did-it-land sets, so this
    page uses none of them (the template's green focus ring and selection are set to ink here)
  - brass marks a person's call: a waiver and who approved it, the owner of a check that holds, and who
    decides the next step
  - an Illustrative tag when the data is a sample

Every figure on the page is a display string of a figure computed in readiness.py; the page computes nothing.
Nothing is loaded from the network, nothing depends on the clock or the machine, and every piece of text from
an input is escaped.

Standard library only. Python 3.11 or later.
"""

from __future__ import annotations

import html
import re
from pathlib import Path
from typing import Any

import readiness

TEMPLATE = Path(__file__).resolve().parent.parent / "assets" / "vendor" / "template.html"
STYLE = re.compile(r"<style>(.*?)</style>", re.S)

# Layout for this page only. Everything else comes from the template's stylesheet.
PAGE_CSS = """
::selection{background:var(--t1);color:var(--bg)}
:focus-visible{outline-color:var(--t1)}
main.solo{margin-left:0}
.solo .slide{min-height:0}
.solo .slide.cover{padding-top:72px;padding-bottom:40px}
.solo .lede{margin-bottom:8px}
.call{display:inline-flex;align-items:center;gap:10px;font:500 13px/20px var(--mono);letter-spacing:.12em;text-transform:uppercase;
color:var(--t1);border:1px solid var(--line3);border-radius:4px;padding:5px 12px;margin:0 0 20px}
.call.hold{background:var(--t1);color:var(--bg);border-color:var(--t1)}
.rw{font:400 10px/16px var(--mono);letter-spacing:.1em;text-transform:uppercase;color:var(--t1);white-space:nowrap;
border:1px solid var(--line3);border-radius:3px;padding:1px 7px}
.rw.hold{background:var(--t1);color:var(--bg);border-color:var(--t1)}
.wv{display:block;font:400 10.5px/16px var(--mono);color:var(--brass)}
.sc-n .own{display:block;font:400 10.5px/16px var(--mono);color:var(--t3);margin-top:5px}
.sc-n .own.owes{color:var(--brass)}
.sc-v ul{margin:0;padding-left:16px;font-size:12.5px;color:var(--t2)}
.sc-v li+li{margin-top:4px}
.rows{margin-top:8px}
.rows>div{display:grid;grid-template-columns:168px minmax(0,1fr) auto;gap:6px 36px;border-top:1px solid var(--line);padding:14px 0;align-items:baseline}
.rows>div>span:first-child{font:400 10px/22px var(--mono);letter-spacing:.1em;text-transform:uppercase;color:var(--t3)}
.rows>div>span:nth-child(2){color:var(--t2);font-size:13.5px}
.need+.need{margin-top:14px}
.need .who{color:var(--brass);font:400 11.5px/16px var(--mono);white-space:nowrap}
.need .when{color:var(--t2);font:400 11.5px/16px var(--mono);white-space:nowrap}
.notes{list-style:none;margin:0;padding:0}
.notes li{border-top:1px solid var(--line);padding:12px 0;color:var(--t2);font-size:13px;overflow-wrap:anywhere}
.ledger td{font-size:12px;overflow-wrap:anywhere}
.ledger td.mo{white-space:nowrap}
.page-foot{max-width:1120px;margin:0 auto;padding:28px 40px 64px;color:var(--t3);font-size:12px}
@media (max-width:980px){.rows>div{grid-template-columns:1fr;gap:2px}.page-foot{padding:24px 16px 48px}.solo .slide.cover{padding-top:48px}
.ledger th:nth-child(1),.ledger td:nth-child(1){display:none}}
"""

MARK = (
    '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" aria-hidden="true" focusable="false">'
    '<rect x="2" y="13" width="3" height="7" fill="var(--agent)"/><rect x="7" y="10" width="3" height="10" fill="var(--agent)"/>'
    '<rect x="12" y="2" width="1.5" height="20" fill="var(--brass)"/><rect x="16" y="4" width="4" height="16" fill="var(--t1)"/></svg>'
)


def e(text: Any) -> str:
    return html.escape(str(text), quote=True)


def stylesheet() -> str:
    """The report template's whole stylesheet, fonts included."""
    try:
        found = STYLE.search(TEMPLATE.read_text(encoding="utf-8"))
    except OSError:
        found = None
    return found.group(1) if found else ""


def word(w: str) -> str:
    """ready to ship or hold, as a plain mono word. Hold is inverted ink so it reads first; neither uses a status colour."""
    return f'<span class="rw{" hold" if w == readiness.HOLD else ""}">{e(w)}</span>'


def figs(c: dict) -> dict[str, dict]:
    return {f["id"].split(".", 1)[1]: f for f in c["figures"]}


def of(n: int, one: str, many: str) -> str:
    return f"{n} {one if n == 1 else many}"


def evidence(c: dict) -> str:
    """One mono line of the check's own figures, as computed. Nothing here is a new number."""
    f = figs(c)
    v = {k: x["value"] for k, x in f.items()}
    if c["id"] == "ci" and "required" in v:
        return f"<b>{v['passed']}</b> of {of(v['required'], 'required check passes', 'required checks pass')}"
    if c["id"] == "bugs" and f:
        open_ = [(k.split(".", 1)[1], n) for k, n in v.items() if k.startswith("open.") and n]
        return "Open: " + (", ".join(f"<b>{n}</b> {e(s)}" for s, n in open_) if open_ else "<b>0</b>")
    if c["id"] == "flags" and "total" in v:
        top = f" &middot; starts at <b>{v['top_rollout']}%</b>" if "top_rollout" in v else ""
        return f"<b>{v['off_switch']}</b> of {of(v['total'], 'flag has', 'flags have')} an off switch{top}"
    if c["id"] == "rollback" and "test_age_days" in v:
        return f"Rehearsed <b>{v['test_age_days']}</b> days before this check"
    if c["id"] == "brief" and "days_to_date" in v:
        return f"<b>{v['days_to_date']}</b> days to the brief's date, {e(f['days_to_date']['window_to'])}"
    if c["id"] == "evals" and "total" in v:
        return f"<b>{v['passing']}</b> of {of(v['total'], 'eval passes', 'evals pass')} the gate"
    if c["id"] == "spec" and "holds" in v:
        return f"<b>{v['closed']}</b> of {of(v['holds'], 'spec hold', 'spec holds')} closed"
    return "No input"


def checks_table(d: dict) -> str:
    waived = {w["id"]: w for w in d["waived"]}
    rows = []
    for c in d["checks"]:
        owes = c["readiness"] == readiness.HOLD
        own = f'<span class="own{" owes" if owes else ""}">Owner &middot; {e(c["owner"])}</span>'
        reasons = "".join(f"<li>{e(r)}</li>" for r in c["reasons"])
        detail = f"<ul>{reasons}</ul>" if reasons else ""
        mark = word(c["readiness"])
        if c["id"] in waived:
            w = waived[c["id"]]
            detail += f'<span class="wv">Waived by {e(w["approved_by"])} until {e(w["expires"])}</span>'
        rows.append(
            f'<div class="sc-r"><div class="sc-n"><span>{e(c["label"])}</span>{own}</div>'
            f'<div class="sc-v"><span class="sc-l">{evidence(c)}</span>{detail}</div><div class="sc-s">{mark}</div></div>'
        )
    head = '<div class="sc-h"><span>Check and owner</span><span>Evidence</span><span>Check word</span></div>'
    return f'<div class="tablewrap sc">{head}{"".join(rows)}</div>'


def waivers(d: dict) -> str:
    if not d["waived"]:
        return ""
    boxes = "".join(
        f'<div class="need"><b>Waiver &middot; a person&#39;s call &middot; {e(w["label"])}</b><div class="need-r"><p>{e(w["reason"])}</p>'
        f'<span class="who">Approved by {e(w["approved_by"])}</span><span class="when">until {e(w["expires"])}</span></div></div>'
        for w in d["waived"]
    )
    lede = "A waiver lets the release ship with a known gap. The check still holds, and its owner closes it before the waiver runs out."
    return f'<section class="slide"><div class="meta"><span>Waivers</span></div><h2>Held, and waived by a named person</h2><p class="lede">{e(lede)}</p>{boxes}</section>'


def spec_section(d: dict) -> str:
    if not d["spec_holds"]:
        return ""
    rows = "".join(
        f"<div><span>{e(h['finding'])}</span><span>{e(h['message'])}</span><span class='rw{'' if h['closed'] else ' hold'}'>{'closed' if h['closed'] else 'open'}</span></div>"
        for h in d["spec_holds"]
    )
    by = ", ".join(f"{h['finding']} by the {h['closed_by']} check" for h in d["spec_holds"] if h["closed_by"])
    lede = f"spec-auditor held the spec on these findings. Each closes only when the release check that tests the same thing is ready to ship: {by}."
    return f'<section class="slide"><div class="meta"><span>02 Spec</span></div><h2>Spec holds, closed by this check</h2><p class="lede">{e(lede)}</p><div class="rows">{rows}</div></section>'


def ledger(d: dict) -> str:
    rows = "".join(
        f'<tr><td class="mo">{e(f["id"])}</td><td>{e(f["label"])}</td><td class="num">{e(readiness.shown(f))}</td>'
        f'<td class="mo">{e(readiness.window(f))}</td><td>{e(f["source"])}</td></tr>'
        for c in d["checks"]
        for f in c["figures"]
    )
    head = "<tr><th>ID</th><th>Figure</th><th class='num'>Value</th><th>Window</th><th>Source</th></tr>"
    return (
        '<section class="slide"><div class="meta"><span>Evidence</span></div><h2>Every figure, with its source</h2>'
        f'<div class="tablewrap"><table class="ledger"><thead>{head}</thead><tbody>{rows}</tbody></table></div></section>'
    )


def notes(d: dict) -> str:
    items = [n for c in d["checks"] for n in c["notes"]] + d["waiver_problems"]
    items += [f"Policy changed from the default: {p}" for p in d["policy_changes"]]
    if not d["ai_feature"]:
        items.append("The eval gate does not apply: the brief's line is fixed code.")
    if not items:
        return ""
    lis = "".join(f"<li>{e(n)}</li>" for n in items)
    return f'<section class="slide"><div class="meta"><span>Notes</span></div><h2>Worth knowing</h2><ul class="notes">{lis}</ul></section>'


def page(d: dict) -> str:
    title = f"Release readiness: {d['release']}"
    meta = [f"Checked {d['as_of']}", d["tool"]] + ([f"Bet {d['bet']}"] if d["bet"] else [])
    meta_html = "".join(f"<span>{e(m)}</span>" for m in meta)
    if d["illustrative"]:
        meta_html += '<span class="ill">Illustrative</span>'
    call_cls = "call hold" if d["readiness"] == readiness.HOLD else "call"
    facts = [(f"{d['ready']} of {d['total']}", "checks ready to ship")]
    if d["waived"]:
        facts.append((str(len(d["waived"])), "waived, a person's call"))
    if d["holds"]:
        facts.append((str(len(d["holds"])), "hold"))
    if d["brief"]:
        facts.append((d["brief"]["bar"], f"the brief's bar, by {d['brief']['by']}"))
    if d["commit"]:
        facts.append((str(d["commit"])[:7], "release commit"))
    facts_html = "".join(f"<span><b>{e(v)}</b>{e(k)}</span>" for v, k in facts)
    nxt = (
        f'<section class="slide"><div class="meta"><span>Next step</span></div><h2>What happens now</h2>'
        f'<div class="need"><div class="need-r"><p>{e(d["next_step"])}</p>'
        f'<span class="who">Decides &middot; {e(d["decides"])}</span><span class="when">checked {e(d["as_of"])}</span></div></div></section>'
    )
    return (
        '<!doctype html><html lang="en-GB"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
        f'<title>{e(title)}</title><style>{stylesheet()}{PAGE_CSS}</style></head><body><main class="solo">'
        f'<section class="slide cover"><div class="brand">{MARK}<span translate="no">DACARD</span></div><div class="meta">{meta_html}</div>'
        f'<h1>{e(d["release"])}</h1><div><span class="{call_cls}">{e(d["readiness"])}</span></div>'
        f'<p class="lede">{e(readiness.headline(d))}</p><div class="facts">{facts_html}</div></section>'
        f'<section class="slide"><div class="meta"><span>03 Build</span></div><h2>Every check, on the release commit</h2>{checks_table(d)}</section>'
        f"{waivers(d)}{spec_section(d)}{nxt}{notes(d)}{ledger(d)}"
        '<p class="page-foot">A release check says whether this commit is ready to ship, not whether the bet will work. '
        "did-it-land reads the metric against the brief's bar after launch. Every figure is computed in code from the sources named.</p>"
        "</main></body></html>\n"
    )
