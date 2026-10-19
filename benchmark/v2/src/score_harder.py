#!/usr/bin/env python3
"""Deterministic scorer for the HARDER question set (H001+). No AI judge.

Usage: python3 score_harder.py <model_key> <answers.json>
answers.json: {"H001": "raw answer text", ...}  (or {"answers": {...}})
Reads:  benchmark/v2/questions_harder.json  +  benchmark/v2/hidden/gt_rules_harder.json
Writes: benchmark/v2/results/<model_key>_harder_score.json

Scoring modes identical to src/score.py: tol / accepted / window / tiered /
keyword_set / timestamp_s / number_s / hard_editor / rubric / na.
"""
import json, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HID = os.path.join(ROOT, "hidden")

DASHES = str.maketrans({"—": "-", "–": "-", "−": "-", "‑": "-", "‒": "-"})


def norm(s):
    s = str(s).translate(DASHES).lower()
    s = re.sub(r"\s+", " ", s)
    return s.strip(" \n\t\"'`“”‘’.,;!?")


def compact(s):
    return re.sub(r"[^a-z0-9]", "", norm(s))


WORD_NUMS = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14,
    "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18,
    "nineteen": 19, "twenty": 20, "twice": 2, "thrice": 3,
    "once": 1, "single": 1, "a couple": 2, "pair": 2,
}

# Accepted-phrase aliases so semantically identical refusals match.
PHRASE_ALIASES = [
    (r"\bnot\s+legible\b", "illegible"),
    (r"\bnot\s+readable\b", "unreadable"),
    (r"\bnot\s+visible\b", "not visible"),
    (r"\bcannot\s+be\s+determined\b", "cannot determine"),
    (r"\bcan\s+not\s+be\s+determined\b", "cannot determine"),
    (r"\bcannot\s+be\s+read\b", "cannot read"),
    (r"\bcan\s+not\s+be\s+read\b", "cannot read"),
    (r"\bnot\s+determinable\b", "cannot determine"),
    (r"\bunable\s+to\s+be\s+determined\b", "unable to determine"),
]


def expand_phrases(text):
    t = str(text)
    for pat, repl in PHRASE_ALIASES:
        t = re.sub(pat, repl, t, flags=re.I)
    return t


def parse_word_number(text):
    """Return the first spelled-out number ('two', 'twice', 'a pair') as float."""
    t = str(text).lower()
    for m in re.finditer(r"\b([a-z]+(?:\s+[a-z]+)?)\b", t):
        phrase = m.group(1).strip()
        if phrase in WORD_NUMS:
            return float(WORD_NUMS[phrase]), "word"
        first = phrase.split()[0]
        if first in WORD_NUMS:
            return float(WORD_NUMS[first]), "word"
    return None, None


def parse_number(text):
    t = str(text).lower()
    if "minute" in t:
        m = re.search(r"-?\d+(?:[.,]\d+)?", t)
        if m:
            v = float(m.group(0).replace(",", "."))
            if v <= 10:
                return v * 60.0, "min"
    mmss = re.search(r"\b(\d{1,3}):(\d{2})\b", t)
    if mmss:
        return int(mmss.group(1)) * 60 + int(mmss.group(2)), "mmss"
    frac = re.search(r"(-?\d+)\s*/\s*(\d+)", t)
    if frac and int(frac.group(2)) != 0:
        return float(frac.group(1)) / float(frac.group(2)), "frac"
    plain = re.search(r"-?\d+(?:[.,]\d+)?", t)
    if plain:
        v = float(plain.group(0).replace(",", "."))
        if re.search(r"\bms\b|millisec", t) and v >= 5:
            return v / 1000.0, "ms"
        return v, None
    return parse_word_number(text)


def parse_all_numbers(text):
    t = str(text).lower()
    out = []
    if "minute" in t:
        for m in re.finditer(r"(\d+(?:\.\d+)?)\s*minutes?", t):
            out.append(float(m.group(1)) * 60)
    for m in re.finditer(r"\b(\d{1,3}):(\d{2})\b", t):
        out.append(int(m.group(1)) * 60 + int(m.group(2)))
    for m in re.finditer(r"-?\d+(?:[.,]\d+)?", t):
        out.append(float(m.group(0).replace(",", ".")))
    if re.search(r"\bms\b|millisec", t) and out:
        out = [v / 1000.0 if v >= 5 else v for v in out]
    return out


def score_answer(rules, raw):
    mode = rules["mode"]
    if raw is None or str(raw).strip() == "":
        return 0.0, "empty answer"
    n = norm(raw)
    c = compact(raw)

    if mode == "na":
        return None, "na"

    if mode == "accepted":
        # expand negations/paraphrases first: "not legible" -> "illegible",
        # "cannot be determined" -> "cannot determine", etc.
        ne = norm(expand_phrases(raw))
        for cand in rules["accepted"]:
            if ne == norm(cand) or compact(expand_phrases(raw)) == compact(cand):
                return 1.0, "exact match: %r" % cand
        for cand in rules["accepted"]:
            cn = norm(cand)
            if len(cn) >= 3 and cn in ne:
                return 1.0, "contains match: %r" % cand
        for cand in rules["accepted"]:
            cn = norm(cand)
            if len(cn) >= 6 and ne in cn:
                return 1.0, "reverse-contains: %r" % cand
        return 0.0, "no match (normalized %r)" % ne

    if mode == "tol":
        v, _ = parse_number(raw)
        if v is None:
            return 0.0, "no number in %r" % raw
        a, tol = rules["answer"], rules["tol"]
        if abs(v - a) <= tol:
            return 1.0, "|%s-%s|<=%s" % (v, a, tol)
        if abs(v - a) <= 2 * tol and tol > 0:
            return 0.5, "|%s-%s|<=2*tol" % (v, a)
        return 0.0, "|%s-%s|>%s" % (v, a, tol)

    if mode == "timestamp_s":
        v, _ = parse_number(raw)
        if v is None:
            return 0.0, "no timestamp"
        a, tol = rules["answer"], rules["tol"]
        if abs(v - a) <= tol:
            return 1.0, "|%s-%s|<=%s" % (v, a, tol)
        if abs(v - a) <= 2 * tol:
            return 0.5, "|%s-%s|<=2*tol" % (v, a)
        return 0.0, "|%s-%s|>%s" % (v, a, tol)

    if mode == "number_s":
        v, _ = parse_number(raw)
        if v is None:
            return 0.0, "no number"
        a, tol = rules["answer"], rules["tol"]
        if abs(v - a) <= tol:
            return 1.0, "|%s-%s|<=%s" % (v, a, tol)
        if abs(v - a) <= 2 * tol:
            return 0.5, "|%s-%s|<=2*tol" % (v, a)
        return 0.0, "|%s-%s|>%s" % (v, a, tol)

    if mode == "tiered":
        ne = norm(expand_phrases(raw))
        nc = compact(expand_phrases(raw))
        for sub in rules["full_substrings"]:
            if norm(sub) in ne or compact(sub) in nc:
                return 1.0, "full: %r" % sub
        for sub in rules.get("half_substrings", []):
            sn = norm(sub)
            if sn == ne or sn in ne.split() or re.search(r"\b%s\b" % re.escape(sn), ne):
                return 0.5, "half: %r" % sub
            if compact(sub) and compact(sub) in nc:
                return 0.5, "half (compact): %r" % sub
        return 0.0, "zero: %r" % ne

    if mode == "keyword_set":
        groups = rules["must_any"]
        if not any(any(k in n for k in grp) for grp in groups):
            return 0.0, "keywords missing: %r" % n
        return 1.0, "keywords matched"

    if mode == "rubric":
        return None, "HUMAN SCORING REQUIRED"

    return 0.0, "unhandled mode %s" % mode


def main():
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(2)
    model_key, answers_path = sys.argv[1], sys.argv[2]
    rules_doc = json.load(open(os.path.join(HID, "gt_rules_harder.json"), encoding="utf-8"))
    rules = {}
    for qid, r0 in rules_doc["rules"].items():
        r = dict(r0.get("gt", r0))
        r["category"] = r0.get("category", "")
        r["type"] = r0.get("type", "")
        rules[qid] = r
    ans = json.load(open(answers_path, encoding="utf-8"))
    if isinstance(ans, dict) and "answers" in ans:
        ans = ans["answers"]

    per, totals = {}, {"scored": 0.0, "max": 0.0, "na": [], "missing": []}
    by_cat = {}
    for qid in sorted(rules.keys()):
        r = rules[qid]
        cat = r["category"]
        raw = ans.get(qid)
        if raw is None:
            totals["missing"].append(qid)
        s, detail = score_answer(r, raw)
        per[qid] = {"score": s, "detail": detail, "raw": raw, "category": cat}
        by_cat.setdefault(cat, {"score": 0.0, "max": 0, "n": 0})
        if s is None:
            totals["na"].append(qid)
            per[qid]["status"] = "na"
            continue
        totals["scored"] += s
        totals["max"] += 1.0
        by_cat[cat]["score"] += s
        by_cat[cat]["max"] += 1
        by_cat[cat]["n"] += 1

    out = {
        "model": model_key + "_harder",
        "total_score": round(totals["scored"], 3),
        "total_max": totals["max"],
        "percent": round(100.0 * totals["scored"] / max(1.0, totals["max"]), 2),
        "na": totals["na"],
        "missing": totals["missing"],
        "by_category": {k: {"score": round(v["score"], 3), "max": v["max"]}
                        for k, v in sorted(by_cat.items())},
        "per_question": per,
    }
    dst = os.path.join(ROOT, "results", model_key + "_harder_score.json")
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    json.dump(out, open(dst, "w"), indent=1, ensure_ascii=False)
    print("%s HARDER: %.2f / %d = %.1f%%  (na=%s missing=%s)" % (
        model_key, out["total_score"], out["total_max"], out["percent"],
        totals["na"], totals["missing"]))
    for cat, v in sorted(by_cat.items()):
        print("  %-24s %.2f/%d" % (cat, v["score"], v["max"]))
    print("wrote", dst)


if __name__ == "__main__":
    main()
