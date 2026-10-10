#!/usr/bin/env python3
"""Render a /design audit report from markdown into a designed HTML page.

Usage:
    python render_report.py .design/smell-report.md
    python render_report.py .design/checkup-report.md -o custom/path.html

Reads the markdown written by an audit mode, infers the report type from the
filename, and writes a sibling .html file. Standard library only.

The markdown contract is in references/report-format.md. This renderer
understands a deliberate subset: headings, tables, lists, fenced code,
blockquotes, rules, paragraphs, and inline bold/italic/code/links. It gives
special treatment to the metadata block, to status words inside tables, and
to "### P0 - title" headings, which become severity cards.
"""

import argparse
import html
import os
import re
import sys

# --------------------------------------------------------------------------
# inline formatting
# --------------------------------------------------------------------------

FILE_REF = re.compile(r"\b([\w./\\-]+\.(?:tsx?|jsx?|css|scss|html|vue|svelte|py|json|md))(:\d+(?:-\d+)?)?\b")


def inline(text):
    """Escape, then apply inline markdown. Order matters: code spans last so
    their contents are not re-processed."""
    out = html.escape(text, quote=False)
    out = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', out)
    out = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", out)
    out = re.sub(r"(?<![\w*])\*([^*\n]+)\*(?![\w*])", r"<em>\1</em>", out)
    out = re.sub(r"`([^`]+)`", r"<code>\1</code>", out)
    return out


def with_file_refs(text):
    """Inline formatting plus highlighting for path:line references, which are
    the load-bearing part of every finding."""
    out = inline(text)
    # Do not touch anything already inside a tag or an existing code span.
    parts = re.split(r"(<[^>]+>|<code>.*?</code>)", out)
    for i, part in enumerate(parts):
        if part.startswith("<"):
            continue
        parts[i] = FILE_REF.sub(
            lambda m: '<span class="ref">%s%s</span>' % (m.group(1), m.group(2) or ""), part
        )
    return "".join(parts)


# --------------------------------------------------------------------------
# status vocabulary
# --------------------------------------------------------------------------

STATUS = {
    "healthy": "ok",
    "ok": "ok",
    "pass": "ok",
    "absent": "ok",
    "warning": "warn",
    "warn": "warn",
    "critical": "bad",
    "breaks": "bad",
    "fail": "bad",
    "present": "bad",
    "unverified": "unk",
    "unknown": "unk",
    "n/a": "na",
    "na": "na",
    "not applicable": "na",
}

SEVERITY_BAND = [
    (9, "ok"), (7, "ok"), (5, "warn"), (3, "bad"), (0, "bad"),
]


def band_for(score):
    try:
        s = int(score)
    except (TypeError, ValueError):
        return "unk"
    if s >= 9:
        return "ok"
    if s >= 7:
        return "good"
    if s >= 5:
        return "warn"
    return "bad"


def status_cell(value):
    key = value.strip().lower()
    if key in STATUS:
        return '<span class="pill pill--%s">%s</span>' % (STATUS[key], html.escape(value.strip()))
    # smell reports score 0 (present) / 1 (absent)
    if key == "0":
        return '<span class="pill pill--bad">0</span>'
    if key == "1":
        return '<span class="pill pill--ok">1</span>'
    # review reports score dimensions out of 10
    if re.fullmatch(r"\d{1,2}", key):
        return '<span class="pill pill--%s">%s</span>' % (band_for(key), key)
    return None


# --------------------------------------------------------------------------
# block parsing
# --------------------------------------------------------------------------

def parse_blocks(lines):
    blocks = []
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]
        stripped = line.strip()

        if not stripped:
            i += 1
            continue

        if stripped.startswith("```"):
            lang = stripped[3:].strip()
            body = []
            i += 1
            while i < n and not lines[i].strip().startswith("```"):
                body.append(lines[i])
                i += 1
            i += 1
            blocks.append(("code", {"lang": lang, "body": "\n".join(body)}))
            continue

        m = re.match(r"^(#{1,4})\s+(.*)$", stripped)
        if m:
            blocks.append(("h", {"level": len(m.group(1)), "text": m.group(2).strip()}))
            i += 1
            continue

        if re.fullmatch(r"(-{3,}|\*{3,}|_{3,})", stripped):
            blocks.append(("hr", {}))
            i += 1
            continue

        if stripped.startswith("|"):
            rows = []
            while i < n and lines[i].strip().startswith("|"):
                rows.append(lines[i].strip())
                i += 1
            blocks.append(("table", {"rows": rows}))
            continue

        if re.match(r"^\s*>", line):
            body = []
            while i < n and re.match(r"^\s*>", lines[i]):
                body.append(re.sub(r"^\s*>\s?", "", lines[i]))
                i += 1
            blocks.append(("quote", {"text": " ".join(x.strip() for x in body)}))
            continue

        if re.match(r"^\s*([-*+]|\d+\.)\s+", line):
            items = []
            ordered = bool(re.match(r"^\s*\d+\.\s+", line))
            while i < n and re.match(r"^\s*([-*+]|\d+\.)\s+", lines[i]):
                items.append(re.sub(r"^\s*([-*+]|\d+\.)\s+", "", lines[i]).strip())
                i += 1
                # fold continuation lines into the current item
                while i < n and lines[i].strip() and not re.match(
                    r"^\s*([-*+]|\d+\.)\s+|^\s*#|^\s*\||^\s*```", lines[i]
                ) and lines[i].startswith((" ", "\t")):
                    items[-1] += " " + lines[i].strip()
                    i += 1
            blocks.append(("list", {"ordered": ordered, "items": items}))
            continue

        body = []
        while i < n and lines[i].strip() and not re.match(
            r"^\s*(#{1,4}\s|\||```|>|[-*+]\s|\d+\.\s|-{3,}$)", lines[i]
        ):
            body.append(lines[i].strip())
            i += 1
        if body:
            blocks.append(("p", {"text": " ".join(body)}))
        else:
            i += 1
    return blocks


def split_table(rows):
    def cells(row):
        return [c.strip() for c in row.strip().strip("|").split("|")]

    if not rows:
        return [], []
    head = cells(rows[0])
    body = []
    for r in rows[1:]:
        if re.fullmatch(r"[\s|:-]+", r):
            continue
        body.append(cells(r))
    return head, body


# --------------------------------------------------------------------------
# rendering
# --------------------------------------------------------------------------

STATUS_COLS = {"score", "status", "reads as", "state", "result", "verdict", "severity"}


def render_table(rows):
    head, body = split_table(rows)
    # Only pill the column the header says is a status column, so a finding that
    # happens to contain the word "absent" stays prose.
    status_idx = {i for i, h in enumerate(head) if h.strip().lower() in STATUS_COLS}
    out = ['<div class="tw"><table>']
    if head:
        out.append("<thead><tr>" + "".join("<th>%s</th>" % inline(c) for c in head) + "</tr></thead>")
    out.append("<tbody>")
    for row in body:
        tds = []
        for idx, cell in enumerate(row):
            pill = status_cell(cell) if idx in status_idx else None
            if pill:
                tds.append('<td class="td--status">%s</td>' % pill)
            else:
                tds.append("<td>%s</td>" % with_file_refs(cell))
        out.append("<tr>" + "".join(tds) + "</tr>")
    out.append("</tbody></table></div>")
    return "\n".join(out)


ISSUE_HEAD = re.compile(r"^(P\d+)\s*[-—–:]\s*(.*)$", re.I)


def render_body(blocks):
    """Render everything after the metadata block. Groups P0/P1/P2 headings and
    the blocks beneath them into severity cards."""
    out = []
    open_card = False

    def close_card():
        nonlocal open_card
        if open_card:
            out.append("</section>")
            open_card = False

    for kind, data in blocks:
        if kind == "h":
            level, text = data["level"], data["text"]
            m = ISSUE_HEAD.match(text) if level == 3 else None
            if m:
                close_card()
                sev = m.group(1).upper()
                cls = {"P0": "bad", "P1": "warn"}.get(sev, "unk")
                out.append('<section class="issue issue--%s">' % cls)
                out.append(
                    '<h3 class="issue__h"><span class="sev sev--%s">%s</span>%s</h3>'
                    % (cls, sev, with_file_refs(m.group(2)))
                )
                open_card = True
                continue
            if level <= 2:
                close_card()
            out.append("<h%d>%s</h%d>" % (level, inline(text), level))
        elif kind == "p":
            out.append("<p>%s</p>" % with_file_refs(data["text"]))
        elif kind == "table":
            out.append(render_table(data["rows"]))
        elif kind == "list":
            tag = "ol" if data["ordered"] else "ul"
            out.append(
                "<%s>%s</%s>" % (tag, "".join("<li>%s</li>" % with_file_refs(x) for x in data["items"]), tag)
            )
        elif kind == "code":
            out.append("<pre><code>%s</code></pre>" % html.escape(data["body"], quote=False))
        elif kind == "quote":
            out.append("<blockquote>%s</blockquote>" % with_file_refs(data["text"]))
        elif kind == "hr":
            close_card()
            out.append('<hr class="rule">')
    close_card()
    return "\n".join(out)


META_LINE = re.compile(r"^\*\*([^:*]+):\*\*\s*(.*)$")
SCORE_LINE = re.compile(r"^(\d{1,2})\s*/\s*10\s*(?:[·•|.-]\s*(.*))?$")


def extract_meta(blocks):
    """Pull the leading **Key:** value block out of the document. Returns
    (title, meta_pairs, remaining_blocks)."""
    title = None
    meta = []
    rest = []
    consuming = True
    for kind, data in blocks:
        if title is None and kind == "h" and data["level"] == 1:
            title = data["text"]
            continue
        if consuming and kind == "p":
            # metadata paragraphs are one or more "**Key:** value" on their own lines,
            # which the paragraph folder has joined with spaces
            pieces = re.findall(r"\*\*([^:*]+):\*\*\s*([^*]*)", data["text"])
            if pieces and data["text"].strip().startswith("**"):
                for k, v in pieces:
                    meta.append((k.strip(), v.strip()))
                continue
        if kind == "h" and data["level"] >= 2:
            consuming = False
        rest.append((kind, data))
    return title, meta, rest


def build_head(title, meta, report_type):
    score, label = None, None
    others = []
    for k, v in meta:
        if k.lower() == "score":
            m = SCORE_LINE.match(v.strip())
            if m:
                score, label = m.group(1), (m.group(2) or "").strip()
            else:
                label = v.strip()
        else:
            others.append((k, v))

    cls = band_for(score) if score is not None else "unk"
    parts = ['<header class="head head--%s">' % cls]
    parts.append('<div class="head__top"><span class="stamp">%s report</span></div>' % html.escape(report_type))
    parts.append("<h1>%s</h1>" % inline(title or "Design report"))

    if score is not None:
        parts.append('<div class="scorebox">')
        parts.append(
            '<div class="score"><span class="score__n">%s</span><span class="score__d">/10</span></div>' % score
        )
        if label:
            parts.append('<div class="score__label">%s</div>' % html.escape(label))
        parts.append('<div class="meter"><div class="meter__fill" style="width:%d%%"></div></div>' % (int(score) * 10))
        parts.append("</div>")
    elif label:
        parts.append('<div class="scorebox"><div class="score__label">%s</div></div>' % html.escape(label))

    if others:
        parts.append('<dl class="meta">')
        for k, v in others:
            parts.append("<div><dt>%s</dt><dd>%s</dd></div>" % (inline(k), with_file_refs(v)))
        parts.append("</dl>")
    parts.append("</header>")
    return "\n".join(parts)


CSS = """
*,*::before,*::after{box-sizing:border-box}
:root{
  color-scheme: light dark;
  --h: 42;
  --bg:      oklch(0.985 0.004 var(--h));
  --surface: oklch(1 0 0);
  --raised:  oklch(0.975 0.006 var(--h));
  --line:    oklch(0.90 0.008 var(--h));
  --line-2:  oklch(0.82 0.010 var(--h));
  --ink:     oklch(0.24 0.012 var(--h));
  --ink-2:   oklch(0.50 0.012 var(--h));
  --ink-3:   oklch(0.62 0.010 var(--h));
  --brand:   oklch(0.55 0.145 var(--h));
  --ok:      oklch(0.52 0.115 155);
  --ok-bg:   oklch(0.95 0.035 155);
  --warn:    oklch(0.55 0.130 68);
  --warn-bg: oklch(0.95 0.055 78);
  --bad:     oklch(0.52 0.180 26);
  --bad-bg:  oklch(0.95 0.040 26);
  --unk:     oklch(0.55 0.010 var(--h));
  --unk-bg:  oklch(0.94 0.006 var(--h));
  --mono: ui-monospace,"Cascadia Mono","SF Mono",Menlo,Consolas,monospace;
  --sans: ui-sans-serif,-apple-system,"Segoe UI",Inter,Roboto,Helvetica,Arial,sans-serif;
}
@media (prefers-color-scheme: dark){
  :root{
    --bg:      oklch(0.17 0.008 var(--h));
    --surface: oklch(0.20 0.010 var(--h));
    --raised:  oklch(0.235 0.012 var(--h));
    --line:    oklch(0.30 0.012 var(--h));
    --line-2:  oklch(0.38 0.014 var(--h));
    --ink:     oklch(0.93 0.006 var(--h));
    --ink-2:   oklch(0.74 0.010 var(--h));
    --ink-3:   oklch(0.62 0.010 var(--h));
    --brand:   oklch(0.72 0.115 var(--h));
    --ok:      oklch(0.74 0.095 155); --ok-bg:  oklch(0.28 0.045 155);
    --warn:    oklch(0.79 0.105 78);  --warn-bg:oklch(0.30 0.050 68);
    --bad:     oklch(0.70 0.135 26);  --bad-bg: oklch(0.30 0.060 26);
    --unk:     oklch(0.70 0.008 var(--h)); --unk-bg: oklch(0.26 0.008 var(--h));
  }
}
html{-webkit-text-size-adjust:100%}
body{
  margin:0; background:var(--bg); color:var(--ink);
  font-family:var(--sans); font-size:clamp(0.95rem,0.92rem+0.15vw,1.0625rem);
  line-height:1.6; font-variant-numeric:tabular-nums;
}
.wrap{max-width:60rem;margin:0 auto;padding:clamp(1.25rem,4vw,3.5rem) clamp(1.1rem,4vw,2.5rem) 6rem}

/* ---- header ---- */
.head{border-top:3px solid var(--brand);padding-top:1.5rem;margin-bottom:2.75rem}
.head--bad{border-top-color:var(--bad)}
.head--warn{border-top-color:var(--warn)}
.head--ok,.head--good{border-top-color:var(--ok)}
.stamp{
  font-family:var(--mono);font-size:0.72rem;letter-spacing:0.14em;text-transform:uppercase;
  color:var(--ink-3);
}
.head h1{
  font-size:clamp(1.75rem,1.3rem+2.2vw,2.9rem);line-height:1.05;letter-spacing:-0.025em;
  font-weight:660;margin:0.5rem 0 0;max-width:22ch;
}
.scorebox{display:flex;align-items:baseline;gap:0.9rem;flex-wrap:wrap;margin-top:1.6rem}
.score{font-family:var(--mono);display:flex;align-items:baseline;gap:0.1rem}
.score__n{font-size:clamp(3rem,2rem+5vw,4.75rem);line-height:0.85;font-weight:600;letter-spacing:-0.04em}
.score__d{font-size:1.15rem;color:var(--ink-3)}
.head--bad .score__n{color:var(--bad)}
.head--warn .score__n{color:var(--warn)}
.head--ok .score__n,.head--good .score__n{color:var(--ok)}
.score__label{
  font-family:var(--mono);font-size:0.8rem;letter-spacing:0.13em;text-transform:uppercase;
  padding:0.3rem 0.6rem;border:1px solid var(--line-2);border-radius:2px;color:var(--ink-2);
  align-self:center;
}
.meter{flex:1 1 12rem;min-width:8rem;height:3px;background:var(--line);position:relative;align-self:center}
.meter__fill{position:absolute;inset:0 auto 0 0;background:var(--brand)}
.head--bad .meter__fill{background:var(--bad)}
.head--warn .meter__fill{background:var(--warn)}
.head--ok .meter__fill,.head--good .meter__fill{background:var(--ok)}
.meta{
  display:grid;grid-template-columns:repeat(auto-fit,minmax(11rem,1fr));
  gap:0 1.75rem;margin:1.9rem 0 0;padding-top:1.1rem;border-top:1px solid var(--line);
}
.meta div{padding:0.45rem 0}
.meta dt{
  font-family:var(--mono);font-size:0.68rem;letter-spacing:0.11em;text-transform:uppercase;
  color:var(--ink-3);margin:0 0 0.15rem;
}
.meta dd{margin:0;font-size:0.9rem;color:var(--ink-2)}

/* ---- prose ---- */
h2{
  font-size:1.32rem;letter-spacing:-0.012em;font-weight:640;line-height:1.25;
  margin:3.25rem 0 0.9rem;padding-bottom:0.5rem;border-bottom:1px solid var(--line);
}
h3{font-size:1.05rem;font-weight:640;margin:2rem 0 0.6rem;letter-spacing:-0.008em}
h4{font-size:0.95rem;font-weight:640;margin:1.5rem 0 0.4rem}
p{margin:0 0 1rem;max-width:68ch}
ul,ol{margin:0 0 1.15rem;padding-left:1.15rem;max-width:68ch}
li{margin:0.3rem 0}
li::marker{color:var(--ink-3)}
a{color:var(--brand);text-underline-offset:2px}
strong{font-weight:640;color:var(--ink)}
code{
  font-family:var(--mono);font-size:0.86em;background:var(--raised);
  border:1px solid var(--line);border-radius:2px;padding:0.08em 0.34em;
}
.ref{font-family:var(--mono);font-size:0.86em;color:var(--ink-2);white-space:nowrap;
  border-bottom:1px dotted var(--line-2)}
pre{
  background:var(--raised);border:1px solid var(--line);border-left:2px solid var(--line-2);
  padding:0.9rem 1.1rem;overflow-x:auto;margin:0 0 1.3rem;
}
pre code{background:none;border:0;padding:0;font-size:0.83rem;line-height:1.55}
blockquote{
  margin:0 0 1.2rem;padding:0.15rem 0 0.15rem 1.1rem;border-left:2px solid var(--brand);
  color:var(--ink-2);max-width:66ch;
}
.rule{border:0;border-top:1px solid var(--line);margin:2.75rem 0}

/* ---- tables ---- */
.tw{overflow-x:auto;margin:0 0 1.6rem;border:1px solid var(--line);background:var(--surface)}
table{border-collapse:collapse;width:100%;font-size:0.885rem}
thead th{
  text-align:left;font-family:var(--mono);font-weight:500;font-size:0.68rem;
  letter-spacing:0.11em;text-transform:uppercase;color:var(--ink-3);
  padding:0.7rem 0.85rem;border-bottom:1px solid var(--line-2);white-space:nowrap;
}
td{padding:0.62rem 0.85rem;border-bottom:1px solid var(--line);vertical-align:top}
tbody tr:last-child td{border-bottom:0}
tbody tr:nth-child(even){background:var(--raised)}
td:first-child{color:var(--ink);font-weight:520}
.td--status{white-space:nowrap;width:1%}

/* ---- pills ---- */
.pill{
  display:inline-block;font-family:var(--mono);font-size:0.7rem;letter-spacing:0.06em;
  text-transform:uppercase;padding:0.16rem 0.46rem;border-radius:2px;border:1px solid transparent;
  min-width:2.1rem;text-align:center;
}
.pill--ok{background:var(--ok-bg);color:var(--ok);border-color:var(--ok)}
.pill--good{background:var(--ok-bg);color:var(--ok);border-color:var(--ok)}
.pill--warn{background:var(--warn-bg);color:var(--warn);border-color:var(--warn)}
.pill--bad{background:var(--bad-bg);color:var(--bad);border-color:var(--bad)}
.pill--unk{background:var(--unk-bg);color:var(--unk);border-color:var(--line-2);border-style:dashed}
.pill--na{background:none;color:var(--ink-3);border-color:var(--line)}

/* ---- issue cards ---- */
.issue{
  background:var(--surface);border:1px solid var(--line);border-left:3px solid var(--unk);
  padding:1.15rem 1.35rem 0.5rem;margin:0 0 1.15rem;
}
.issue--bad{border-left-color:var(--bad)}
.issue--warn{border-left-color:var(--warn)}
.issue__h{display:flex;align-items:center;gap:0.7rem;margin:0 0 0.7rem;font-size:1.02rem;line-height:1.35}
.sev{
  font-family:var(--mono);font-size:0.7rem;letter-spacing:0.09em;padding:0.2rem 0.45rem;
  border-radius:2px;flex:none;
}
.sev--bad{background:var(--bad-bg);color:var(--bad)}
.sev--warn{background:var(--warn-bg);color:var(--warn)}
.sev--unk{background:var(--unk-bg);color:var(--unk)}
.issue p:last-child{margin-bottom:0.9rem}
.issue .tw{margin-bottom:1rem}

@media print{
  body{background:#fff}
  .issue,.tw{break-inside:avoid}
}
"""


def render(md_text, report_type):
    blocks = parse_blocks(md_text.replace("\r\n", "\n").split("\n"))
    title, meta, rest = extract_meta(blocks)
    doc_title = title or ("%s report" % report_type)
    return """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>%s</title>
<style>%s</style>
</head>
<body>
<main class="wrap">
%s
%s
</main>
</body>
</html>
""" % (html.escape(doc_title), CSS, build_head(title, meta, report_type), render_body(rest))


def main():
    ap = argparse.ArgumentParser(description="Render a /design audit report to HTML.")
    ap.add_argument("markdown", help="path to the report markdown, e.g. .design/smell-report.md")
    ap.add_argument("-o", "--out", help="output html path (default: sibling .html)")
    ap.add_argument("--type", help="report type label (default: inferred from filename)")
    args = ap.parse_args()

    if not os.path.isfile(args.markdown):
        sys.stderr.write("render_report: no such file: %s\n" % args.markdown)
        return 2

    with open(args.markdown, "r", encoding="utf-8") as fh:
        md_text = fh.read()

    stem = os.path.splitext(os.path.basename(args.markdown))[0]
    report_type = args.type or stem.replace("-report", "").replace("_report", "").replace("-", " ")
    out_path = args.out or os.path.splitext(args.markdown)[0] + ".html"

    out_dir = os.path.dirname(os.path.abspath(out_path))
    if out_dir and not os.path.isdir(out_dir):
        os.makedirs(out_dir, exist_ok=True)

    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(render(md_text, report_type))

    sys.stdout.write("wrote %s\n" % out_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
