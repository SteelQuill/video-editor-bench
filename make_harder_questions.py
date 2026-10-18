#!/usr/bin/env python3
"""Generate HARDER questions targeting v2 failure modes.

Output: benchmark/v2/questions_harder.json  (same schema as questions.json)

These are ADDITIONAL questions, not a replacement for the 49 in questions.json.
They target the categories where every local model (and even TwelveLabs pass-1)
scored 0 or near-0:

  - transition-timing   (precise second of transition start)
  - transition-duration (precise seconds of dissolve/wipe length)
  - bad-edit-detection  (continuity errors an editor would catch)
  - object-count        (precise counts)
  - not-observable      (things frame-sampling cannot determine - should REFUSE)
  - shot-count          (precise segment count incl. flash inserts)
  - ocr-title           (exact on-screen text)

Usage:
  python3 make_harder_questions.py > benchmark/v2/questions_harder.json

NOTE: These are written against the known structure of benchmark.mp4
(65s, 17 transitions, 15 segments) from your v2 report. If your actual
video differs, edit the questions/GT before running the bench.
"""
import json
import sys

HARDER = {
    "schema": "v2-harder-questions/1",
    "note": "Harder set targeting v2 failure modes. GT must be filled in hidden/ before scoring.",
    "video": "benchmark.mp4",
    "questions": [
        # ---------------- transition-timing (harder: precise start second) ----------------
        {
            "id": "H001",
            "category": "transition-timing",
            "type": "timestamp_s",
            "question": "At what exact second does the dissolve from the beach shot to the chateau shot BEGIN?",
        },
        {
            "id": "H002",
            "category": "transition-timing",
            "type": "timestamp_s",
            "question": "At what exact second does the wipe from the canal shot to the cafe shot BEGIN?",
        },
        {
            "id": "H003",
            "category": "transition-timing",
            "type": "timestamp_s",
            "question": "At what exact second does the cut from the MEANWHILE card to the desk shot occur?",
        },
        {
            "id": "H004",
            "category": "transition-timing",
            "type": "timestamp_s",
            "question": "At what exact second does the black-and-white desk shot FIRST appear?",
        },
        {
            "id": "H005",
            "category": "transition-timing",
            "type": "timestamp_s",
            "question": "At what exact second does the cafe shot re-enter (the mirrored return) BEGIN?",
        },

        # ---------------- transition-duration (harder: precise length) ----------------
        {
            "id": "H006",
            "category": "transition-duration",
            "type": "number_s",
            "question": "How many seconds long is the dissolve between the flowers shot and the beach shot?",
        },
        {
            "id": "H007",
            "category": "transition-duration",
            "type": "number_s",
            "question": "How many seconds long is the wipe between the chateau shot and the canal shot?",
        },
        {
            "id": "H008",
            "category": "transition-duration",
            "type": "number_s",
            "question": "How many seconds long is the dissolve around 44 seconds (desk shot to mirrored cafe)?",
        },
        {
            "id": "H009",
            "category": "transition-duration",
            "type": "number_s",
            "question": "How many seconds long is the transition at ~53 seconds (cafe to black-and-white desk)?",
        },
        {
            "id": "H010",
            "category": "transition-duration",
            "type": "number_s",
            "question": "How many seconds long is the fade/cut transition into the opening title card?",
        },

        # ---------------- bad-edit-detection (harder: editor-level continuity errors) ----------------
        {
            "id": "H011",
            "category": "bad-edit-detection",
            "type": "text",
            "question": "Around 36 seconds, right before the MEANWHILE card, there is an editing mistake. Describe it precisely.",
        },
        {
            "id": "H012",
            "category": "bad-edit-detection",
            "type": "text",
            "question": "The cafe shot returns at ~49.3 seconds. From an editor's point of view, what is wrong with that re-entry?",
        },
        {
            "id": "H013",
            "category": "bad-edit-detection",
            "type": "text",
            "question": "In the black-and-white desk shot, is there a continuity error with the objects on the desk between the first and second time we see it? Describe.",
        },
        {
            "id": "H014",
            "category": "bad-edit-detection",
            "type": "text",
            "question": "Does any shot in the video have a jump-cut within the same continuous action (subject jumps position mid-shot)? If so, at what second?",
        },
        {
            "id": "H015",
            "category": "bad-edit-detection",
            "type": "text",
            "question": "Is there a frame where audio and video are visibly out of sync (lip sync or action mismatch)? If yes, when?",
        },

        # ---------------- object-count (harder: precise counts, occluded objects) ----------------
        {
            "id": "H016",
            "category": "object-count",
            "type": "integer",
            "question": "How many espresso cups are on the cafe table in the FIRST cafe shot?",
        },
        {
            "id": "H017",
            "category": "object-count",
            "type": "integer",
            "question": "How many white boats are moored in the canal shot?",
        },
        {
            "id": "H018",
            "category": "object-count",
            "type": "integer",
            "question": "How many people are visible in the chateau shot?",
        },
        {
            "id": "H019",
            "category": "object-count",
            "type": "integer",
            "question": "How many distinct books are on the desk in the black-and-white shot?",
        },
        {
            "id": "H020",
            "category": "object-count",
            "type": "integer",
            "question": "How many times does the black dog/puppy appear across the entire video?",
        },

        # ---------------- not-observable (traps - model should refuse, not guess) ----------------
        {
            "id": "H021",
            "category": "not-observable",
            "type": "text",
            "question": "In the shot with the vintage camera and open grid notebook, what is written in the handwritten notes?",
        },
        {
            "id": "H022",
            "category": "not-observable",
            "type": "text",
            "question": "What is the brand of the white car visible through the cafe window in the background?",
        },
        {
            "id": "H023",
            "category": "not-observable",
            "type": "text",
            "question": "What is the exact time shown on the wall clock in the cafe shot?",
        },
        {
            "id": "H024",
            "category": "not-observable",
            "type": "text",
            "question": "What is written on the napkin under the espresso cups in the first cafe shot?",
        },
        {
            "id": "H025",
            "category": "not-observable",
            "type": "text",
            "question": "What color are the dog's eyes in the shot where it appears?",
        },

        # ---------------- shot-count (harder: precise segment count) ----------------
        {
            "id": "H026",
            "category": "shot-count",
            "type": "integer",
            "question": "Counting each scene, each full-screen text card, and each flash insert as one segment, how many total segments does this edit contain?",
        },
        {
            "id": "H027",
            "category": "shot-count",
            "type": "integer",
            "question": "How many full-screen text cards (title, interlude, MEANWHILE, end cards) appear?",
        },
        {
            "id": "H028",
            "category": "shot-count",
            "type": "integer",
            "question": "How many distinct shooting locations are shown (e.g. beach, chateau, canal, cafe, desk)?",
        },
        {
            "id": "H029",
            "category": "shot-count",
            "type": "integer",
            "question": "How many times does the cafe shot appear (counting both first and re-entry)?",
        },
        {
            "id": "H030",
            "category": "shot-count",
            "type": "integer",
            "question": "How many black-and-white shots are in the video?",
        },

        # ---------------- ocr-title (harder: exact text) ----------------
        {
            "id": "H031",
            "category": "ocr-title",
            "type": "text",
            "question": "What does the main text of the opening title card say, exactly?",
        },
        {
            "id": "H032",
            "category": "ocr-title",
            "type": "text",
            "question": "What is the smaller subtitle line under the opening title, exactly?",
        },
        {
            "id": "H033",
            "category": "ocr-title",
            "type": "text",
            "question": "What text does the lower-third overlay show during the desk shot with the REC indicator, exactly?",
        },
        {
            "id": "H034",
            "category": "ocr-title",
            "type": "text",
            "question": "What word is printed on the white book standing on the desk in the black-and-white shot?",
        },
        {
            "id": "H035",
            "category": "ocr-title",
            "type": "text",
            "question": "Which number is shown on the black desk calendar in the black-and-white shot?",
        },
    ],
}


def main():
    out_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", "questions_harder.json"
    )
    out_path = os.path.abspath(out_path)
    with open(out_path, "w") as fh:
        json.dump(HARDER, fh, indent=1, ensure_ascii=False)
    print("wrote %d harder questions to %s" % (len(HARDER["questions"]), out_path))


if __name__ == "__main__":
    import os
    main()
