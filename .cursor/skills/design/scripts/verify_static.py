#!/usr/bin/env python3
"""Static integrity checks for a design pass, for when there is no browser.

Design edits break things in boring, checkable ways: a var() that points at a
token you renamed, a getElementById for an id you removed, a label pointing at
nothing, a stylesheet that no longer parses. None of that needs a rendered page
to catch, and catching it here is the difference between "I changed the CSS" and
"I changed the CSS and it still resolves".

This does NOT tell you the design is good, or that it looks right. It tells you
nothing is dangling. Read the limits section at the bottom of the output.

Usage
-----
  python verify_static.py .                 # whole project
  python verify_static.py dashboard.html    # one page plus what it links
  python verify_static.py . --quiet         # failures only

Exit code is 1 if any check fails, so it can gate a pass.
"""

import argparse
import os
import re
import sys
from html.parser import HTMLParser

SKIP_DIRS = {".git", "node_modules", ".design", "dist", "build", "__pycache__", ".next"}


# ---------------------------------------------------------------- html

class Page(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.ids = []
        self.labels_for = []
        self.aria_refs = []
        self.anchors = []
        self.assets = []
        self.images = []
        self.inputs = []
        self.void_stack = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        line = self.getpos()[0]

        if a.get("id"):
            self.ids.append((a["id"], line))
        if tag == "label" and a.get("for"):
            self.labels_for.append((a["for"], line))
        for key in ("aria-describedby", "aria-labelledby", "aria-controls", "aria-owns"):
            if a.get(key):
                for ref in a[key].split():
                    self.aria_refs.append((key, ref, line))

        href = a.get("href", "")
        if href.startswith("#") and len(href) > 1:
            self.anchors.append((href[1:], line))
        for attr in ("href", "src"):
            v = a.get(attr, "")
            if v and not v.startswith(("#", "http://", "https://", "//", "data:", "mailto:", "tel:", "?")):
                self.assets.append((v.split("?")[0].split("#")[0], line))

        if tag == "img":
            self.images.append((a.get("src", ""), a.get("alt"), line))
        if tag in ("input", "select", "textarea"):
            if a.get("type", "text").lower() not in ("hidden", "submit", "button", "reset", "image"):
                self.inputs.append((a.get("id"), a.get("aria-label"), a.get("aria-labelledby"),
                                    a.get("placeholder"), tag, line))


def scan_html(path):
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        text = fh.read()
    p = Page()
    try:
        p.feed(text)
    except Exception:
        pass
    return p, text


# ---------------------------------------------------------------- collect

def collect(root):
    html_files, css_files, js_files = [], [], []
    if os.path.isfile(root):
        base = os.path.dirname(os.path.abspath(root)) or "."
        html_files = [root] if root.lower().endswith((".html", ".htm")) else []
        for dirpath, dirs, files in os.walk(base):
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
            for f in files:
                p = os.path.join(dirpath, f)
                if f.lower().endswith(".css"):
                    css_files.append(p)
                elif f.lower().endswith(".js"):
                    js_files.append(p)
        return html_files, css_files, js_files, base

    for dirpath, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for f in sorted(files):
            p = os.path.join(dirpath, f)
            low = f.lower()
            if low.endswith((".html", ".htm")):
                html_files.append(p)
            elif low.endswith(".css"):
                css_files.append(p)
            elif low.endswith((".js", ".mjs")):
                js_files.append(p)
    return html_files, css_files, js_files, root


def read(path):
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        return fh.read()


def strip_css_comments(text):
    return re.sub(r"/\*.*?\*/", "", text, flags=re.S)


def line_of(text, index):
    return text.count("\n", 0, index) + 1


# ---------------------------------------------------------------- checks

class Report:
    def __init__(self):
        self.checks = []

    def add(self, name, ok, detail=""):
        self.checks.append((name, ok, detail))

    @property
    def failed(self):
        return [c for c in self.checks if not c[1]]


def rel(path, root):
    try:
        return os.path.relpath(path, root).replace("\\", "/")
    except ValueError:
        return path


def run_checks(root):
    html_files, css_files, js_files, base = collect(root)
    rpt = Report()

    # ---- CSS parses and braces balance
    for f in css_files:
        text = strip_css_comments(read(f))
        opens, closes = text.count("{"), text.count("}")
        rpt.add("css braces balance: %s" % rel(f, base), opens == closes,
                "" if opens == closes else "%d open vs %d close" % (opens, closes))

    # ---- every var(--x) resolves to a defined custom property
    defined = set()
    for f in css_files + html_files:
        for m in re.finditer(r"(--[\w-]+)\s*:", strip_css_comments(read(f))):
            defined.add(m.group(1))
    dangling = []
    for f in css_files + html_files + js_files:
        text = strip_css_comments(read(f))
        for m in re.finditer(r"var\(\s*(--[\w-]+)\s*(?:,([^)]*))?\)", text):
            name, fallback = m.group(1), m.group(2)
            if name not in defined and not fallback:
                dangling.append("%s:%d %s" % (rel(f, base), line_of(text, m.start()), name))
    rpt.add("every var(--x) resolves or has a fallback", not dangling,
            "; ".join(dangling[:6]) + (" (+%d more)" % (len(dangling) - 6) if len(dangling) > 6 else ""))

    # ---- per page
    all_ids = {}
    for f in html_files:
        page, text = scan_html(f)
        name = rel(f, base)
        ids = {i for i, _ in page.ids}
        all_ids[name] = ids

        dupes = {}
        for i, line in page.ids:
            dupes.setdefault(i, []).append(line)
        dup = ["%s (lines %s)" % (k, ", ".join(map(str, v))) for k, v in dupes.items() if len(v) > 1]
        rpt.add("no duplicate ids: %s" % name, not dup, "; ".join(dup[:5]))

        bad = ["%s:%d for=%s" % (name, line, ref) for ref, line in page.labels_for if ref not in ids]
        rpt.add("every label[for] resolves: %s" % name, not bad, "; ".join(bad[:5]))

        bad = ["%s:%d %s=%s" % (name, line, key, ref) for key, ref, line in page.aria_refs if ref not in ids]
        rpt.add("every aria reference resolves: %s" % name, not bad, "; ".join(bad[:5]))

        bad = ["%s:%d #%s" % (name, line, ref) for ref, line in page.anchors if ref not in ids]
        rpt.add("every in-page anchor resolves: %s" % name, not bad, "; ".join(bad[:5]))

        missing = []
        for asset, line in page.assets:
            target = os.path.normpath(os.path.join(os.path.dirname(f), asset))
            if not os.path.exists(target):
                missing.append("%s:%d %s" % (name, line, asset))
        rpt.add("every local asset exists: %s" % name, not missing, "; ".join(missing[:5]))

        bad = ["%s:%d %s" % (name, line, src or "(no src)") for src, alt, line in page.images if alt is None]
        rpt.add("every img has an alt attribute: %s" % name, not bad, "; ".join(bad[:5]))

        labelled = {ref for ref, _ in page.labels_for}
        bad = []
        for iid, aria_label, aria_by, placeholder, tag, line in page.inputs:
            has_label = (iid and iid in labelled) or aria_label or aria_by
            if not has_label:
                why = "placeholder is not a label" if placeholder else "no label"
                bad.append("%s:%d <%s> %s" % (name, line, tag, why))
        rpt.add("every form control has a visible label: %s" % name, not bad, "; ".join(bad[:5]))

    # ---- JS DOM lookups resolve against some page
    union = set().union(*all_ids.values()) if all_ids else set()
    if html_files:
        bad = []
        for f in js_files + html_files:
            text = read(f)
            for m in re.finditer(r"getElementById\(\s*['\"]([\w-]+)['\"]", text):
                if m.group(1) not in union:
                    bad.append("%s:%d #%s" % (rel(f, base), line_of(text, m.start()), m.group(1)))
            for m in re.finditer(r"querySelector(?:All)?\(\s*['\"]#([\w-]+)['\"]", text):
                if m.group(1) not in union:
                    bad.append("%s:%d #%s" % (rel(f, base), line_of(text, m.start()), m.group(1)))
        rpt.add("every JS id lookup resolves in some page", not bad, "; ".join(bad[:6]))

    # ---- focus is not removed without a replacement
    css_all = "\n".join(strip_css_comments(read(f)) for f in css_files)
    kills_outline = re.search(r"outline\s*:\s*(none|0)\b", css_all)
    has_focus_visible = ":focus-visible" in css_all
    rpt.add("focus ring is not removed without a replacement",
            not kills_outline or has_focus_visible,
            "outline:none present with no :focus-visible rule anywhere" if kills_outline and not has_focus_visible else "")

    # ---- reduced motion is handled if anything animates
    animates = re.search(r"@keyframes|transition\s*:|animation\s*:", css_all)
    rpt.add("prefers-reduced-motion is handled if anything animates",
            not animates or "prefers-reduced-motion" in css_all,
            "animation present with no prefers-reduced-motion guard" if animates and "prefers-reduced-motion" not in css_all else "")

    return rpt, base, len(html_files), len(css_files), len(js_files)


LIMITS = """
What this did NOT check, and what you therefore may not claim:
  layout, overflow, or anything about how the page actually renders
  computed contrast (use scripts/contrast.py)
  whether a font file loads over the network
  keyboard order, focus visibility in practice, or any real interaction
  whether a state can be reached by a user
Passing here means nothing is dangling. It does not mean the design works."""


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("target", nargs="?", default=".", help="project directory or a single .html file")
    ap.add_argument("--quiet", action="store_true", help="print failures only")
    args = ap.parse_args()

    if not os.path.exists(args.target):
        sys.stderr.write("verify_static: no such path: %s\n" % args.target)
        return 2

    rpt, base, nh, nc, nj = run_checks(args.target)
    width = max((len(c[0]) for c in rpt.checks), default=10)

    for name, ok, detail in rpt.checks:
        if ok and args.quiet:
            continue
        line = "%-*s  %s" % (width, name, "ok" if ok else "FAIL")
        if detail:
            line += "\n%s  %s" % (" " * width, detail)
        print(line)

    failed = rpt.failed
    print("\n%d checks over %d html, %d css, %d js. %d failing." % (
        len(rpt.checks), nh, nc, nj, len(failed)))
    print(LIMITS)
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
