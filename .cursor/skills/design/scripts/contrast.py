#!/usr/bin/env python3
"""Color math for design passes: contrast, sRGB gamut, and color vision checks.

Every design pass ends up needing these three answers, and computing them by
hand is slow and easy to get subtly wrong. Run this instead.

Usage
-----
  # One pair. Add --large for 18.66px bold / 24px text.
  python contrast.py --pair "oklch(0.55 0.14 42)" "#ffffff"

  # Many pairs from a file. One per line:  name | foreground | background [| large]
  python contrast.py --pairs pairs.txt

  # Pull every color token out of a stylesheet, report lightness and gamut.
  python contrast.py --css css/tokens.css

  # Do two colors stay separable for the ~1 in 12 people with a CVD?
  python contrast.py --cvd "#16A34A" "#DC2626"

Accepts #rgb, #rrggbb, #rrggbbaa, rgb(), rgba(), hsl(), hsla(), oklch(), oklab()
and the common CSS keywords.

Run this BEFORE committing to a palette, not after. Catching an out-of-gamut
color or a 3.3:1 pair while the ramp is still a draft costs nothing; catching it
after the palette is applied to 40 components costs a migration.

Exit code is 1 if any check fails, so it can gate a pass.
"""

import argparse
import math
import os
import re
import sys

# ---------------------------------------------------------------- parsing

KEYWORDS = {
    "white": (1.0, 1.0, 1.0), "black": (0.0, 0.0, 0.0),
    "red": (1.0, 0.0, 0.0), "green": (0.0, 0.5019, 0.0),
    "blue": (0.0, 0.0, 1.0), "gray": (0.5019,) * 3, "grey": (0.5019,) * 3,
    "silver": (0.7529,) * 3, "transparent": (1.0, 1.0, 1.0),
}

NUM = r"[-+]?(?:\d*\.\d+|\d+)"


def _nums(text, count):
    vals = re.findall(NUM + r"%?", text)
    if len(vals) < count:
        raise ValueError("expected %d numbers in %r" % (count, text))
    return vals[:count]


def _pct(token, scale=1.0):
    if token.endswith("%"):
        return float(token[:-1]) / 100.0 * scale
    return float(token)


def parse_color(text):
    """Return gamma-encoded sRGB in 0..1. Out-of-gamut input is reported by
    parse_color_gamut, not silently clipped here."""
    rgb, _ = parse_color_gamut(text)
    return tuple(min(1.0, max(0.0, c)) for c in rgb)


def parse_color_gamut(text):
    """Return (rgb, in_gamut). rgb may fall outside 0..1 for oklch/oklab input
    that sRGB cannot represent."""
    s = str(text).strip().lower()

    if s in KEYWORDS:
        return KEYWORDS[s], True

    m = re.fullmatch(r"#([0-9a-f]{3,8})", s)
    if m:
        h = m.group(1)
        if len(h) in (3, 4):
            h = "".join(c * 2 for c in h)
        if len(h) not in (6, 8):
            raise ValueError("bad hex color: %s" % text)
        return tuple(int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4)), True

    if s.startswith("rgb"):
        r, g, b = _nums(s, 3)
        conv = lambda t: _pct(t, 1.0) if t.endswith("%") else float(t) / 255.0
        return (conv(r), conv(g), conv(b)), True

    if s.startswith("hsl"):
        h, sat, lig = _nums(s, 3)
        return hsl_to_rgb(float(h.rstrip("%")), _pct(sat), _pct(lig)), True

    if s.startswith("oklch"):
        l, c, h = _nums(s, 3)
        rgb = oklab_to_srgb(oklch_to_oklab(_pct(l), float(c.rstrip("%")), float(h.rstrip("%"))))
        return rgb, all(-1e-4 <= v <= 1 + 1e-4 for v in rgb)

    if s.startswith("oklab"):
        l, a, b = _nums(s, 3)
        rgb = oklab_to_srgb((_pct(l), float(a), float(b)))
        return rgb, all(-1e-4 <= v <= 1 + 1e-4 for v in rgb)

    raise ValueError("unrecognized color: %s" % text)


def hsl_to_rgb(h, s, l):
    h = (h % 360) / 360.0
    if s == 0:
        return (l, l, l)
    q = l * (1 + s) if l < 0.5 else l + s - l * s
    p = 2 * l - q

    def hue(t):
        t = t % 1.0
        if t < 1 / 6:
            return p + (q - p) * 6 * t
        if t < 1 / 2:
            return q
        if t < 2 / 3:
            return p + (q - p) * (2 / 3 - t) * 6
        return p

    return (hue(h + 1 / 3), hue(h), hue(h - 1 / 3))


# ---------------------------------------------------------------- oklab

def oklch_to_oklab(l, c, h):
    rad = math.radians(h)
    return (l, c * math.cos(rad), c * math.sin(rad))


def oklab_to_srgb(lab):
    L, a, b = lab
    l_ = L + 0.3963377774 * a + 0.2158037573 * b
    m_ = L - 0.1055613458 * a - 0.0638541728 * b
    s_ = L - 0.0894841775 * a - 1.2914855480 * b
    l, m, s = l_ ** 3, m_ ** 3, s_ ** 3
    r = 4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s
    g = -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s
    bb = -0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s
    return tuple(linear_to_srgb(v) for v in (r, g, bb))


def srgb_to_oklab(rgb):
    r, g, b = (srgb_to_linear(v) for v in rgb)
    l = 0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b
    m = 0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b
    s = 0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b
    l_, m_, s_ = (math.copysign(abs(v) ** (1 / 3), v) for v in (l, m, s))
    return (
        0.2104542553 * l_ + 0.7936177850 * m_ - 0.0040720468 * s_,
        1.9779984951 * l_ - 2.4285922050 * m_ + 0.4505937099 * s_,
        0.0259040371 * l_ + 0.7827717662 * m_ - 0.8086757660 * s_,
    )


def srgb_to_linear(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def linear_to_srgb(c):
    if c <= 0.0031308:
        return 12.92 * c
    return 1.055 * (abs(c) ** (1 / 2.4)) * (1 if c >= 0 else -1) - 0.055


# ---------------------------------------------------------------- wcag

def luminance(rgb):
    r, g, b = (srgb_to_linear(min(1.0, max(0.0, c))) for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(fg, bg):
    a, b = luminance(fg), luminance(bg)
    hi, lo = max(a, b), min(a, b)
    return (hi + 0.05) / (lo + 0.05)


def required(kind):
    return {"large": 3.0, "ui": 3.0, "body": 4.5, "text": 4.5}.get(kind, 4.5)


# ---------------------------------------------------------------- cvd

# Viénot, Brettel & Mollon dichromat simulation, applied in gamma-encoded sRGB.
# An approximation, but the right one for the question this answers: will these
# two colors still read as different.
def _to_lms(rgb):
    r, g, b = (c * 255.0 for c in rgb)
    return (
        17.8824 * r + 43.5161 * g + 4.11935 * b,
        3.45565 * r + 27.1554 * g + 3.86714 * b,
        0.0299566 * r + 0.184309 * g + 1.46709 * b,
    )


def _from_lms(lms):
    L, M, S = lms
    r = 0.0809444479 * L - 0.130504409 * M + 0.116721066 * S
    g = -0.0102485335 * L + 0.0540193266 * M - 0.113614708 * S
    b = -0.000365296938 * L - 0.00412161469 * M + 0.693511405 * S
    return tuple(min(1.0, max(0.0, v / 255.0)) for v in (r, g, b))


def simulate(rgb, kind):
    L, M, S = _to_lms(rgb)
    if kind == "protanopia":
        L = 2.02344 * M - 2.52581 * S
    elif kind == "deuteranopia":
        M = 0.494207 * L + 1.24827 * S
    elif kind == "tritanopia":
        S = -0.395913 * L + 0.801109 * M
    return _from_lms((L, M, S))


CVD_TYPES = ("deuteranopia", "protanopia", "tritanopia")
# OKLab distance. Below the floor two colors read as the same. Between the floor
# and the comfort line they are technically distinct but only by lightness, which
# is not enough to carry meaning on its own.
SEPARATION_FLOOR = 0.10
SEPARATION_COMFORT = 0.18


def oklab_distance(a, b):
    la, aa, ba = srgb_to_oklab(a)
    lb, ab, bb = srgb_to_oklab(b)
    return math.sqrt((la - lb) ** 2 + (aa - ab) ** 2 + (ba - bb) ** 2)


# ---------------------------------------------------------------- css tokens

TOKEN_RE = re.compile(r"(--[\w-]+)\s*:\s*([^;{}]+);")
COLORISH = re.compile(r"#[0-9a-fA-F]{3,8}|rgba?\(|hsla?\(|oklch\(|oklab\(")


def css_tokens(path):
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        text = fh.read()
    out = []
    for name, value in TOKEN_RE.findall(text):
        v = value.strip()
        if COLORISH.search(v) or v.lower() in KEYWORDS:
            try:
                rgb, in_gamut = parse_color_gamut(v)
            except ValueError:
                continue
            out.append((name, v, rgb, in_gamut))
    return out


def to_hex(rgb):
    return "#%02X%02X%02X" % tuple(int(round(min(1.0, max(0.0, c)) * 255)) for c in rgb)


# ---------------------------------------------------------------- commands

def cmd_pair(args):
    fg_raw, bg_raw = args.pair
    fg, fg_ok = parse_color_gamut(fg_raw)
    bg, bg_ok = parse_color_gamut(bg_raw)
    kind = "large" if args.large else ("ui" if args.ui else "body")
    ratio = contrast(fg, bg)
    need = required(kind)
    ok = ratio >= need

    def label(raw, rgb):
        h = to_hex(rgb)
        return raw if raw.strip().upper() == h else "%s -> %s" % (raw, h)

    print("%-30s on %-24s  %5.2f:1  need %.1f  %s" % (
        label(fg_raw, fg), label(bg_raw, bg), ratio, need, "PASS" if ok else "FAIL"))
    for label, in_gamut, raw in (("foreground", fg_ok, fg_raw), ("background", bg_ok, bg_raw)):
        if not in_gamut:
            print("  ! %s %s is outside the sRGB gamut and will be clipped" % (label, raw))
    return 0 if ok else 1


def cmd_pairs(args):
    failures = 0
    rows = []
    with open(args.pairs, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.split("#")[0].strip()
            if not line:
                continue
            parts = [p.strip() for p in line.split("|")]
            if len(parts) < 3:
                print("skipping malformed line: %s" % line, file=sys.stderr)
                continue
            name, fg_raw, bg_raw = parts[0], parts[1], parts[2]
            kind = parts[3].lower() if len(parts) > 3 else "body"
            try:
                fg, _ = parse_color_gamut(fg_raw)
                bg, _ = parse_color_gamut(bg_raw)
            except ValueError as exc:
                print("skipping %s: %s" % (name, exc), file=sys.stderr)
                continue
            ratio = contrast(fg, bg)
            need = required(kind)
            ok = ratio >= need
            failures += 0 if ok else 1
            rows.append((name, ratio, need, ok))

    width = max((len(r[0]) for r in rows), default=4)
    for name, ratio, need, ok in rows:
        print("%-*s  %5.2f:1  need %.1f  %s" % (width, name, ratio, need, "PASS" if ok else "FAIL"))
    print("\n%d pairs, %d failing" % (len(rows), failures))
    return 0 if failures == 0 else 1


def cmd_css(args):
    tokens = css_tokens(args.css)
    if not tokens:
        print("no color tokens found in %s" % args.css)
        return 0
    width = max(len(t[0]) for t in tokens)
    bad = 0
    print("%-*s  %-24s  %-9s  %-7s  %s" % (width, "token", "value", "hex", "L*", "gamut"))
    for name, value, rgb, in_gamut in tokens:
        L = srgb_to_oklab(rgb)[0]
        if not in_gamut:
            bad += 1
        print("%-*s  %-24s  %-9s  %-7.3f  %s" % (
            width, name, value[:24], to_hex(rgb), L, "ok" if in_gamut else "OUT OF GAMUT"))
    print("\n%d color tokens, %d out of gamut" % (len(tokens), bad))
    if bad:
        print("Out-of-gamut colors get clipped by the browser, which changes the hue you designed.")
    return 0 if bad == 0 else 1


def cmd_cvd(args):
    a_raw, b_raw = args.cvd
    a = parse_color(a_raw)
    b = parse_color(b_raw)
    base = oklab_distance(a, b)
    print("%s vs %s" % (a_raw, b_raw))
    print("  %-14s distance %.3f" % ("normal vision", base))
    collapsed, marginal = 0, 0
    for kind in CVD_TYPES:
        sa, sb = simulate(a, kind), simulate(b, kind)
        d = oklab_distance(sa, sb)
        if d < SEPARATION_FLOOR:
            verdict = "COLLAPSES"
            collapsed += 1
        elif d < SEPARATION_COMFORT:
            verdict = "MARGINAL"
            marginal += 1
        else:
            verdict = "separable"
        print("  %-14s distance %.3f  %-10s (%s vs %s)" % (kind, d, verdict, to_hex(sa), to_hex(sb)))

    if collapsed or marginal:
        print("")
        if collapsed:
            print("These two collapse for at least one form of color vision deficiency.")
        if marginal:
            print("These two survive only on a thin lightness difference, which is not enough to")
            print("carry meaning by itself. A default green/red status pair usually lands here.")
        print("Fix by widening the LIGHTNESS gap, and pair them with an icon, label, or position.")
        print("A hue change alone usually does not fix it.")
    return 0 if collapsed == 0 else 1


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--pair", nargs=2, metavar=("FG", "BG"), help="check one foreground/background pair")
    g.add_argument("--pairs", metavar="FILE", help="check many pairs: name | fg | bg [| large]")
    g.add_argument("--css", metavar="FILE", help="list color tokens in a stylesheet with gamut status")
    g.add_argument("--cvd", nargs=2, metavar=("A", "B"), help="check two colors stay separable under CVD")
    ap.add_argument("--large", action="store_true", help="treat as large text (3:1 instead of 4.5:1)")
    ap.add_argument("--ui", action="store_true", help="treat as a UI boundary or icon (3:1)")
    args = ap.parse_args()

    try:
        if args.pair:
            return cmd_pair(args)
        if args.pairs:
            if not os.path.isfile(args.pairs):
                sys.stderr.write("no such file: %s\n" % args.pairs)
                return 2
            return cmd_pairs(args)
        if args.css:
            if not os.path.isfile(args.css):
                sys.stderr.write("no such file: %s\n" % args.css)
                return 2
            return cmd_css(args)
        return cmd_cvd(args)
    except ValueError as exc:
        sys.stderr.write("contrast: %s\n" % exc)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
