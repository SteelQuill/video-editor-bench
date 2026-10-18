#!/usr/bin/env python3
"""Twelve Labs harder-benchmark runner with dual-key rotation + 3 retries.

Run from anywhere with internet (codespace OK). env:
  TL_API_KEY_1 / TL_API_KEY_2   (required; auto-failover)
  VIDEO / QFILE / OUT           (defaults to benchmark.mp4 / questions_harder.json)
  TL_MODEL                      (default pegasus1.5)
  N_RETRIES                     (default 3: initial + 3 hinted re-answers)
  RETRY_SUFFIX                  (hint text appended on retries)

Retry flow (per your benchmark finding that 1 retry lifted TwelveLabs 52.9%->63.0%):
  pass-1:  original question
  pass-2:  question + "Your previous answer was incorrect. Watch the video again carefully and answer again."
  pass-3:  question + "Your previous answer was incorrect. Focus on the exact timestamp/text requested. Answer again."
  pass-4:  question + "Your previous answer was incorrect. Be concise and answer only what is asked. Answer again."

The LAST non-empty answer per question is kept (your v2 pass-2 kept pass-2 overwrites).
Output: {"answers": {qid: text}, "per_pass": {qid: [pass1, pass2, ...]}, ...}
Resume-safe: skips already-answered qids.
"""
from __future__ import annotations

import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tl_client import TLClient, load_answers, save_answers  # noqa: E402

REPO = os.path.dirname(os.path.abspath(__file__))
V2 = os.path.join(REPO, "benchmark", "v2")
VIDEO = os.environ.get("VIDEO", os.path.join(V2, "benchmark.mp4"))
QFILE = os.environ.get("QFILE", os.path.join(V2, "questions_harder.json"))
OUT = os.environ.get("OUT") or os.path.join(
    V2, "results", "results_harder_twelvelabs.json")
TL_MODEL = os.environ.get("TL_MODEL", "pegasus1.5")
N_RETRIES = int(os.environ.get("N_RETRIES", "3"))  # extra hinted passes after pass-1
WRAP = "Watch this video and answer the question.\n\n"

RETRY_SUFFIXES = [
    "",
    " Your previous answer was incorrect. Watch the video again carefully and answer again.",
    " Your previous answer was incorrect. Focus on the exact timestamp or text requested. Answer again.",
    " Your previous answer was incorrect. Be concise and answer only what is asked. Answer again.",
]


def doc_asset_id(doc):
    """Fetch asset_id from a resumed results doc (top-level or config)."""
    if isinstance(doc, dict):
        return doc.get("asset_id") or doc.get("config", {}).get("asset_id")
    return None


def main():
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    client = TLClient()
    with open(QFILE) as fh:
        qs = json.load(fh)["questions"]
    print("LOADED %d harder questions" % len(qs), flush=True)

    answers = load_answers(OUT)
    per_pass = {}
    # load existing per_pass if present
    prev = {}
    if os.path.exists(OUT):
        with open(OUT) as fh:
            prev = json.load(fh)
        per_pass = prev.get("per_pass", {})
        answers = prev.get("answers", answers)

    # asset setup (reuse via TL_ASSET_ID if set)
    asset_id = os.environ.get("TL_ASSET_ID") or prev.get("asset_id") or doc_asset_id(prev)
    if not asset_id:
        print("UPLOADING %s" % VIDEO, flush=True)
        t0 = time.time()
        asset_id, up_s = client.upload_asset(VIDEO)
        print("ASSET READY %s in %.1fs" % (asset_id, up_s), flush=True)

    started = time.time()
    errors = []

    for i, q in enumerate(qs, 1):
        qid = q["id"]
        if answers.get(qid):
            continue

        base_prompt = WRAP + q["question"]
        pass_answers = []
        final_ans = ""

        for p in range(N_RETRIES + 1):
            suffix = RETRY_SUFFIXES[p] if p < len(RETRY_SUFFIXES) else RETRY_SUFFIXES[-1]
            prompt = base_prompt + suffix
            print("ENTER %s pass-%d" % (qid, p + 1), flush=True)
            try:
                t = time.time()
                ans = client.analyze(asset_id, prompt)
                wall = time.time() - t
                pass_answers.append(ans)
                final_ans = ans  # last non-empty wins
                print("Q%02d %s p%d %.1fs -> %s" % (
                    i, qid, p + 1, wall,
                    ans.replace("\n", " ")[:160]), flush=True)
                time.sleep(2)  # be gentle with the API between passes
            except Exception as e:
                msg = str(e)[:300]
                errors.append("%s p%d: %s" % (qid, p + 1, msg))
                print("ERROR %s p%d: %s" % (qid, p + 1, msg), flush=True)
                if not pass_answers:
                    final_ans = ""

        answers[qid] = final_ans
        per_pass[qid] = pass_answers

        doc = {
            "model_key": "twelvelabs",
            "model": TL_MODEL,
            "video": VIDEO,
            "asset_id": asset_id,
            "n_retries": N_RETRIES,
            "answers": answers,
            "per_pass": per_pass,
            "errors": errors,
            "total_wall_s": round(time.time() - started, 1),
        }
        with open(OUT, "w") as fh:
            json.dump(doc, fh, indent=1, ensure_ascii=False)

    walls = [len(v) for v in per_pass.values()]
    print("WROTE %s" % OUT, flush=True)
    print("SUMMARY answered=%d errors=%d total_wall=%.0fs" % (
        len(answers), len(errors), time.time() - started), flush=True)


if __name__ == "__main__":
    main()
