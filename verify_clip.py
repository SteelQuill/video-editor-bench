#!/usr/bin/env python3
"""Single-call content verification via Twelve Labs.

Design note: ONE analyze call with ALL checks in one prompt (saves credit
vs N separate calls). Content/order/OCR only -- per the harder benchmark,
Pegasus is reliable there (object-count 4/4, OCR 7/7, ordering 2/2) but
unreliable on sub-second timing (0/5) and stray-frame detection (1/3),
so those are deliberately excluded from verification.

env: TL_API_KEY_1, TL_API_KEY_2, TL_MODEL (default pegasus1.5),
     TL_ASSET_ID (required), INTENT (what we meant to record)
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tl_client import TLClient  # noqa: E402

INTENT = os.environ.get(
    "INTENT",
    "A screen recording of a YouTube channel page being scrolled downwards. "
    "The page shows many video thumbnails that look repetitive/similar. "
    "The channel name and profile picture are BLURRED and must not be readable.",
)

PROMPT = """You are a video QA inspector. Answer each item as a numbered list,
one line each, starting with the exact labels below. Be literal and concise.

1. SCENE: What kind of page or interface is shown? (e.g. video platform channel page, other)
2. SCROLLING: Is the content scrolling/moving vertically? Answer yes or no.
3. THUMBNAIL_COUNT: Roughly how many distinct video thumbnails are visible in total?
4. REPETITION: Do the thumbnails look highly similar to each other, or all different? Answer "highly similar", "somewhat similar", or "all different".
5. TEXT_LEGIBLE: Is any channel name or profile picture clearly readable or recognizable? Answer "readable" or "not readable".
6. ANY_TEXT: List any legible on-screen text you can see (titles, counts, buttons). If none, say none.
7. OVERLAY_TEXT: Is there any caption, subtitle, or added graphic on top of the recording that is not part of the webpage itself? Answer yes or no, and describe it.
8. ARTIFACTS: Describe any blur, censor boxes, black bars, or editing artifacts visible.
9. VERDICT: Does this video look like a genuine real screen recording of that page? Answer "genuine", "partly synthetic", or "synthetic".
"""


def main():
    asset_id = os.environ.get("TL_ASSET_ID")
    if not asset_id:
        sys.exit("set TL_ASSET_ID")
    client = TLClient()
    print("ASSET  %s" % asset_id, flush=True)
    print("MODEL  %s" % client.model, flush=True)
    print("INTENT %s\n" % INTENT, flush=True)
    try:
        out = client.analyze(asset_id, PROMPT)
    except Exception as exc:
        sys.exit("ANALYZE FAILED: %s" % exc)
    print("=" * 60)
    print(out)
    print("=" * 60)
    dst = os.environ.get("OUT", "verify_out.json")
    with open(dst, "w") as fh:
        json.dump({"asset_id": asset_id, "intent": INTENT, "prompt": PROMPT,
                   "response": out}, fh, indent=1)
    print("wrote %s" % dst)


if __name__ == "__main__":
    main()
