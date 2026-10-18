#!/usr/bin/env python3
"""HARDER question set for the v2 benchmark — grounded in timeline.py + render.py.

Single source of truth: every question and its ground truth comes from the
documented facts in benchmark/v2/src/timeline.py (frames @30fps) and the
rendered card/overlay text in render.py.

Emits:
  benchmark/v2/questions_harder.json        (public — questions only)
  benchmark/v2/hidden/gt_rules_harder.json  (private — GT + scoring rules)

Usage: python3 make_harder_questions.py
"""
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Each entry: (id, category, type, question, gt)
# gt dict keys: mode + mode-specific fields (same schema as score.py)
QUESTIONS = [
    # ---------------- transition-timing (precise start second) ----------------
    ("H001", "transition-timing", "timestamp_s",
     "At what second does the dissolve from the flowers shot to the beach shot BEGIN?",
     {"mode": "timestamp_s", "answer": 11.0, "tol": 0.35}),
    ("H002", "transition-timing", "timestamp_s",
     "At what second does the wipe from the chateau to the canal BEGIN?",
     {"mode": "timestamp_s", "answer": 26.0, "tol": 0.35}),
    ("H003", "transition-timing", "timestamp_s",
     "At what second does the dip-to-black transition from the canal to the cafe BEGIN?",
     {"mode": "timestamp_s", "answer": 31.0, "tol": 0.35}),
    ("H004", "transition-timing", "timestamp_s",
     "At what second does the transition from the MEANWHILE card to the desk shot BEGIN?",
     {"mode": "timestamp_s", "answer": 38.07, "tol": 0.35}),
    ("H005", "transition-timing", "timestamp_s",
     "At what second does the wipe from the mirrored cafe to the black-and-white desk BEGIN?",
     {"mode": "timestamp_s", "answer": 53.0, "tol": 0.35}),

    # ---------------- transition-identification (harder kinds) ----------------
    ("H006", "transition-identification", "closed",
     "Around 21 seconds, what type of transition connects the sea-view vista to the chateau?",
     {"mode": "accepted", "accepted": ["zoom", "scale", "scale-blend", "zoom-blend", "zoom in", "zoom transition"]}),
    ("H007", "transition-identification", "closed",
     "Around 31 seconds, what type of transition connects the canal shot to the cafe shot?",
     {"mode": "accepted", "accepted": ["dip to black", "dip-to-black", "dip", "fade through black", "fade to black"]}),
    ("H008", "transition-identification", "closed",
     "What type of transition carries the MEANWHILE card into the desk shot (the incoming image moves over the card)?",
     {"mode": "accepted", "accepted": ["slide", "slide up", "push", "push up"]}),
    ("H009", "transition-identification", "closed",
     "Around 16 seconds, what type of transition connects the beach shot to the sea-view vista?",
     {"mode": "accepted", "accepted": ["cut", "hard cut", "straight cut", "jump cut"]}),
    ("H010", "transition-identification", "closed",
     "Around 44 seconds, what type of transition connects the overhead desk shot to the flat-lay desk shot?",
     {"mode": "accepted", "accepted": ["dissolve", "crossfade", "cross dissolve", "cross-fade"]}),

    # ---------------- transition-duration (precise length) ----------------
    ("H011", "transition-duration", "number_s",
     "How many seconds long is the dissolve between the flowers and beach shots?",
     {"mode": "number_s", "answer": 0.5, "tol": 0.1}),
    ("H012", "transition-duration", "number_s",
     "How many seconds long is the wipe from the chateau to the canal?",
     {"mode": "number_s", "answer": 0.33, "tol": 0.1}),
    ("H013", "transition-duration", "number_s",
     "How many seconds long is the zoom transition from the vista to the chateau?",
     {"mode": "number_s", "answer": 0.2, "tol": 0.1}),
    ("H014", "transition-duration", "number_s",
     "How many seconds long is the dip-to-black from the canal to the cafe?",
     {"mode": "number_s", "answer": 0.2, "tol": 0.1}),
    ("H015", "transition-duration", "number_s",
     "How many seconds long is the wipe from the mirrored cafe to the black-and-white desk?",
     {"mode": "number_s", "answer": 0.27, "tol": 0.1}),

    # ---------------- transition-direction ----------------
    ("H016", "transition-direction", "closed",
     "What is the DIRECTION of the wipe at ~26 seconds (chateau to canal)?",
     {"mode": "accepted", "accepted": ["left to right", "left-to-right", "l->r", "left right", "from left", "leftwards", "left to right direction"]}),
    ("H017", "transition-direction", "closed",
     "What is the DIRECTION of the wipe at ~53 seconds (mirrored cafe to black-and-white desk)?",
     {"mode": "accepted", "accepted": ["right to left", "right-to-left", "r->l", "from right", "rightwards"]}),
    ("H018", "transition-direction", "closed",
     "What is the DIRECTION of the slide transition at ~38 seconds (MEANWHILE card to desk shot)?",
     {"mode": "accepted", "accepted": ["up", "upward", "upwards", "slides up", "bottom to top"]}),

    # ---------------- bad-edit-detection ----------------
    ("H019", "bad-edit-detection", "text",
     "A stray image flashes full-screen for 2 frames right before the MEANWHILE card at ~36 seconds. What does it show?",
     {"mode": "tiered",
      "full_substrings": ["onion", "red onion", "vegetable", "chopped onion"],
      "half_substrings": ["food", "cooking", "cutting board", "kitchen"]}),
    ("H020", "bad-edit-detection", "text",
     "During the dissolve around 49.5 seconds (overhead desk to mirrored cafe), a single image flashes for 2 frames. What is it?",
     {"mode": "tiered",
      "full_substrings": ["open book", "book"],
      "half_substrings": ["book", "reading", "page"]}),
    ("H021", "bad-edit-detection", "text",
     "The dissolve between the flowers shot and the beach shot is unusual from an editor's point of view. What is wrong with it?",
     {"mode": "tiered",
      "full_substrings": ["too long", "overlong", "too slow", "long dissolve", "slow dissolve", "excessively long"],
      "half_substrings": ["long", "slow", "duration", "length"]}),

    # ---------------- object-count (grounded in assets) ----------------
    ("H022", "object-count", "integer",
     "How many cups are on the cafe table in the first cafe shot?",
     {"mode": "tol", "answer": 2, "tol": 0}),
    ("H023", "object-count", "integer",
     "How many times does the black dog appear in the video (counting both appearances)?",
     {"mode": "tol", "answer": 2, "tol": 0}),
    ("H024", "object-count", "integer",
     "How many books are standing on the desk in the black-and-white shot?",
     {"mode": "tol", "answer": 2, "tol": 0}),
    ("H025", "object-count", "integer",
     "How many full-screen TEXT cards (title, interlude, end) appear in the video?",
     {"mode": "tol", "answer": 3, "tol": 0}),

    # ---------------- not-observable (should refuse) ----------------
    ("H026", "not-observable", "text",
     "What is written in the handwritten notes of the open notebook in the overhead desk shot?",
     {"mode": "accepted",
      "accepted": ["cannot determine", "not visible", "cannot tell", "unable to determine",
                   "illegible", "unreadable", "not observable", "cannot read", "too small", "too blurry", "blurry"]}),
    ("H027", "not-observable", "text",
     "What text is visible on the smartphone screen lying on the cafe table?",
     {"mode": "accepted",
      "accepted": ["none", "no text", "screen is off", "blank", "off", "cannot determine", "not visible",
                   "no text visible", "screen off", "black screen"]}),
    ("H028", "not-observable", "text",
     "What is the brand of the white car visible through the cafe window in the background?",
     {"mode": "accepted",
      "accepted": ["cannot determine", "not visible", "cannot tell", "unable to determine",
                   "not observable", "cannot read", "unknown"]}),
    ("H029", "not-observable", "text",
     "What are the first three words of the blurred text on the open-book flash frame at ~49.5 seconds?",
     {"mode": "accepted",
      "accepted": ["cannot determine", "not visible", "cannot tell", "unable to determine",
                   "illegible", "unreadable", "not observable", "cannot read", "too blurry", "blurry"]}),

    # ---------------- shot-count ----------------
    ("H030", "shot-count", "integer",
     "Counting each scene and each full-screen text card as one segment (ignore the brief flash inserts), how many segments does this edit contain?",
     {"mode": "tol", "answer": 15, "tol": 0}),
    ("H031", "shot-count", "integer",
     "How many times does the cafe table shot appear in the video (counting both the original and the mirrored return)?",
     {"mode": "tol", "answer": 2, "tol": 0}),

    # ---------------- ocr-title / ocr-overlay ----------------
    ("H032", "ocr-title", "text",
     "What does the main text of the opening title card say?",
     {"mode": "accepted", "accepted": ["WEEKEND CUT"]}),
    ("H033", "ocr-title", "text",
     "What is the smaller subtitle line under the opening title?",
     {"mode": "accepted", "accepted": ["sat — sun", "sat - sun", "sat–sun"]}),
    ("H034", "ocr-overlay", "text",
     "What does the lower-third overlay show during the desk shot with the REC indicator?",
     {"mode": "accepted", "accepted": ["the cut — 23:10", "the cut - 23:10", "the cut–23:10", "the cut 23:10"]}),
    ("H035", "ocr-overlay", "text",
     "What is the subtitle line under the word MEANWHILE on the mid-video card?",
     {"mode": "accepted", "accepted": ["back at the desk"]}),
    ("H036", "ocr-prop", "text",
     "What word is printed on the book standing on the desk in the black-and-white shot?",
     {"mode": "accepted", "accepted": ["Symbol", "symbol"]}),
    ("H037", "ocr-prop", "text",
     "What number is shown on the black desk calendar in the black-and-white shot?",
     {"mode": "accepted", "accepted": ["18"]}),
    ("H038", "ocr-overlay", "text",
     "Which three letters appear next to the blinking red dot in the top-left corner of the desk shot?",
     {"mode": "accepted", "accepted": ["REC", "rec"]}),

    # ---------------- spatial-order / long-range ----------------
    ("H039", "spatial-order", "closed",
     "Which comes FIRST in the video: the chateau shot or the canal shot?",
     {"mode": "accepted", "accepted": ["chateau", "castle", "chateau shot"]}),
    ("H040", "spatial-order", "closed",
     "Which comes FIRST: the flat-lay overhead desk shot or the mirrored cafe shot?",
     {"mode": "accepted", "accepted": ["flat-lay", "flat lay", "flatlay", "overhead desk", "overhead", "flat-lay desk"]}),
    ("H041", "long-range-reappearance", "text",
     "Which subject appears near both the BEGINNING and the END of the video?",
     {"mode": "accepted", "accepted": ["dog", "puppy", "black dog", "black lab", "labrador", "dog/puppy"]}),

    # ---------------- motion-direction ----------------
    ("H042", "motion-direction", "closed",
     "In the canal shot (~26-31 s), which direction does the camera PAN?",
     {"mode": "accepted", "accepted": ["left", "leftwards", "leftward", "to the left", "pan left", "pans left"]}),
    ("H043", "motion-direction", "closed",
     "In the overhead desk shot with the REC indicator (~38-44 s), which direction does the camera PAN?",
     {"mode": "accepted", "accepted": ["right", "rightwards", "rightward", "to the right", "pan right", "pans right"]}),

    # ---------------- continuity-mismatch ----------------
    ("H044", "continuity-mismatch", "text",
     "The cafe table shot appears twice. What is DIFFERENT about the second appearance compared to the first?",
     {"mode": "tiered",
      "full_substrings": ["mirror", "flipped", "flip", "reversed", "horizontally"],
      "half_substrings": ["mirrored", "flipped", "opposite"]}),
]


def main():
    qdoc = {
        "schema": "v2-harder-questions/1",
        "note": "Harder set grounded in src/timeline.py. Additive to the 49 v2 questions.",
        "video": "benchmark.mp4",
        "questions": [
            {"id": qid, "category": cat, "type": typ, "question": q}
            for (qid, cat, typ, q, _gt) in QUESTIONS
        ],
    }
    rules = {
        "rules": {
            qid: {"category": cat, "type": typ, "flags": {}, "gt": gt}
            for (qid, cat, typ, _q, gt) in QUESTIONS
        }
    }
    qpath = os.path.join(ROOT, "questions_harder.json")
    gpath = os.path.join(ROOT, "hidden", "gt_rules_harder.json")
    os.makedirs(os.path.dirname(gpath), exist_ok=True)
    with open(qpath, "w") as fh:
        json.dump(qdoc, fh, indent=1, ensure_ascii=False)
    with open(gpath, "w") as fh:
        json.dump(rules, fh, indent=1, ensure_ascii=False)
    print("wrote %d questions -> %s" % (len(QUESTIONS), qpath))
    print("wrote GT rules      -> %s" % gpath)


if __name__ == "__main__":
    main()
