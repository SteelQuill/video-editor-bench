"""v2 benchmark timeline — single source of truth for renderer, GT writer, validator.

All frame numbers are FINAL rendered-timeline frames @30fps.
"""
FPS = 30
W, H = 1920, 1080
TOTAL = 1950  # 65.000 s

# ---- assets (opaque names only) -------------------------------------------
A = {
    "dog": "asset_001.jpg",
    "vista": "asset_002.jpg",
    "book": "asset_003.jpg",
    "cafe": "asset_004.jpg",
    "flatlay": "asset_005.jpg",
    "beach": "asset_006.jpg",
    "flowers": "asset_007.jpg",
    "bwdesk": "asset_008.jpg",
    "chateau": "asset_009.jpg",
    "canal": "asset_010.jpg",
    "creator": "asset_011.jpg",
    "laptop": "asset_012.jpg",
    "teapot": "asset_013.jpg",
    "onion": "asset_014.jpg",
    "lily": "asset_015.jpg",
}

# ---- transitions (documented facts, consumed by GT + scorer) ---------------
# frames are inclusive ranges on the final timeline
TRANSITIONS = [
    {"id": "T01", "kind": "fade",         "frames": (50, 59),   "direction": "to-black",  "note": "title fades out through black"},
    {"id": "T02", "kind": "fade",         "frames": (60, 69),   "direction": "from-black", "note": "dog fades in from black"},
    {"id": "T03", "kind": "cut",          "frames": (180, 180), "note": "hard cut title->wait: dog->flowers"},
    {"id": "T04", "kind": "dissolve",     "frames": (330, 344), "dur": 15, "note": "flowers->beach, overlong (bad B3)"},
    {"id": "T05", "kind": "cut",          "frames": (480, 480), "note": "beach->vista with matched pan-right velocity (good G1)"},
    {"id": "T06", "kind": "zoom",         "frames": (630, 635), "dur": 6,  "note": "vista->chateau scale-blend"},
    {"id": "T07", "kind": "wipe",         "frames": (780, 789), "dur": 10, "direction": "L->R", "note": "chateau->canal"},
    {"id": "T08", "kind": "dip-to-black", "frames": (930, 935), "dur": 6,  "note": "canal->cafe"},
    {"id": "T09", "kind": "flash",        "frames": (1080, 1081), "dur": 2, "asset": "onion", "note": "stray flash frame before card (bad B1)"},
    {"id": "T10", "kind": "cut",          "frames": (1082, 1082), "note": "flash->MEANWHILE card"},
    {"id": "T11", "kind": "slide",        "frames": (1142, 1145), "dur": 4, "direction": "up", "note": "card->creator, incoming slides up over outgoing"},
    {"id": "T12", "kind": "dissolve",     "frames": (1320, 1329), "dur": 10, "note": "creator->flatlay"},
    {"id": "T13", "kind": "dissolve",     "frames": (1480, 1489), "dur": 10, "note": "flatlay->mirrored cafe; contains 2f book flash 1484-1485"},
    {"id": "T14", "kind": "wipe",         "frames": (1590, 1597), "dur": 8, "direction": "R->L", "note": "mirrored cafe->bw desk"},
    {"id": "T15", "kind": "cut",          "frames": (1740, 1740), "note": "bw desk->dog re-appearance (good G5 bookend)"},
    {"id": "T16", "kind": "fade",         "frames": (1850, 1859), "direction": "to-black", "note": "dog fades out"},
    {"id": "T17", "kind": "fade",         "frames": (1860, 1869), "direction": "from-black", "note": "FIN fades in"},
]

FLASH_FRAMES = {
    "onion": (1080, 1081),   # definitely-observable, bad edit B1
    "book":  (1484, 1485),   # ambiguous (67 ms inside dissolve)
}

OVERLAYS = [
    {"id": "OV1", "kind": "lower_third", "frames": (1170, 1319), "text": "the cut — 23:10",
     "slide_frames": (1170, 1175), "note": "OCR target; slides in from left over 6f"},
    {"id": "OV2", "kind": "rec_blink",   "frames": (1160, 1319), "period": 15, "on": 9,
     "text": "REC", "note": "red REC dot top-left, motion overlay"},
]

# ---- segment display ranges (inclusive; includes overlap rendering) --------
# body = the segment's "own" frames; display = frames it is actually rendered
SEGMENTS = [
    {"id": "S1",  "name": "title_card",  "kind": "card",  "body": (0, 59),     "display": (0, 59)},
    {"id": "S2",  "name": "dog",         "kind": "photo", "asset": A["dog"],      "body": (60, 179),   "display": (60, 179)},
    {"id": "S3",  "name": "flowers",     "kind": "photo", "asset": A["flowers"],  "body": (180, 329),  "display": (180, 344)},
    {"id": "S4",  "name": "beach",       "kind": "photo", "asset": A["beach"],    "body": (330, 479),  "display": (330, 479)},
    {"id": "S5",  "name": "vista",       "kind": "photo", "asset": A["vista"],    "body": (480, 629),  "display": (480, 635)},
    {"id": "S6",  "name": "chateau",     "kind": "photo", "asset": A["chateau"],  "body": (630, 779),  "display": (630, 789)},
    {"id": "S7",  "name": "canal",       "kind": "photo", "asset": A["canal"],    "body": (780, 929),  "display": (780, 935)},
    {"id": "S8",  "name": "cafe",        "kind": "photo", "asset": A["cafe"],     "body": (933, 1079), "display": (933, 1079)},
    {"id": "S9",  "name": "meanwhile_card","kind": "card",                          "body": (1082, 1139),"display": (1082, 1145)},
    {"id": "S10", "name": "creator",     "kind": "photo", "asset": A["creator"],  "body": (1142, 1319),"display": (1142, 1329)},
    {"id": "S11", "name": "flatlay",     "kind": "photo", "asset": A["flatlay"],  "body": (1320, 1479),"display": (1320, 1489)},
    {"id": "S12", "name": "cafe_mirror", "kind": "photo", "asset": A["cafe"],     "body": (1480, 1589),"display": (1480, 1597), "flip_h": True},
    {"id": "S13", "name": "bwdesk",      "kind": "photo", "asset": A["bwdesk"],   "body": (1590, 1739),"display": (1590, 1739)},
    {"id": "S14", "name": "dog2",        "kind": "photo", "asset": A["dog"],      "body": (1740, 1859),"display": (1740, 1859)},
    {"id": "S15", "name": "fin_card",    "kind": "card",                          "body": (1860, 1949),"display": (1860, 1949)},
]

# per-segment fade multipliers (applied over black)
FADES = {
    "S1":  {"out": (50, 59)},
    "S2":  {"in": (60, 69)},
    "S14": {"out": (1850, 1859)},
    "S15": {"in": (1860, 1869)},
}

# ---- motion plans (output-pixel offsets; zoom multiplies cover fit) --------
# ox/oy = crop-center offset in OUTPUT pixels relative to centered window.
def _motion(seg, t):
    """t = local frame index since body start (may exceed body during overlap)."""
    n = seg["name"]
    if n == "title_card" or n == "meanwhile_card" or n == "fin_card":
        return {"z": 1.0, "ox": 0, "oy": 0, "text_scale": 1.0 + 0.03 * t / max(1, seg["body"][1] - seg["body"][0])}
    if n == "dog":
        return {"z": 1.05 + 0.10 * min(1.0, t / 120.0), "ox": 0, "oy": 0}
    if n == "flowers":  # pan up
        return {"z": 1.15, "ox": 0, "oy": 30 - 60 * min(1.0, t / 165.0)}
    if n == "beach":    # static then pan-right ramp matching vista entry velocity
        if t <= 134:
            return {"z": 1.25, "ox": 0, "oy": 0}
        dt = t - 134
        return {"z": 1.25, "ox": 10.0 * dt * dt / 30.0, "oy": 0}
    if n == "vista":    # enters already panning right at 10 px/f, decays over 60f
        if t <= 60:
            ox = -150.0 + 10.0 * t - t * t / 12.0   # v = 10 - t/6 -> 0 @ t=60
        else:
            ox = 150.0
        return {"z": 1.25, "ox": ox, "oy": 0}
    if n == "chateau":  # push-in
        return {"z": 1.02 + 0.12 * min(1.0, t / 160.0), "ox": 0, "oy": 0}
    if n == "canal":    # pan left
        return {"z": 1.15, "ox": 60 - 120 * min(1.0, t / 160.0), "oy": 0}
    if n == "cafe":
        return {"z": 1.02, "ox": 0, "oy": 0}
    if n == "creator":  # pan right
        return {"z": 1.10, "ox": -30 + 60 * min(1.0, t / 178.0), "oy": 0}
    if n == "flatlay":  # tilt down
        return {"z": 1.12, "ox": 0, "oy": -40 + 80 * min(1.0, t / 170.0)}
    if n == "cafe_mirror":
        return {"z": 1.02, "ox": 0, "oy": 0}
    if n == "bwdesk":   # push-in
        return {"z": 1.03 + 0.09 * min(1.0, t / 150.0), "ox": 0, "oy": 0}
    if n == "dog2":     # tighter crop
        return {"z": 1.35 + 0.15 * min(1.0, t / 120.0), "ox": 40, "oy": 10}
    raise KeyError(n)

# ---- boundary transition table for the renderer ---------------------------
# frame -> (type, dur, meta) ; regions where two segments render simultaneously
RENDER_BLENDS = [
    {"type": "dissolve", "frames": (330, 344), "out": "flowers", "in": "beach"},
    {"type": "zoom",     "frames": (630, 635), "out": "vista",   "in": "chateau"},
    {"type": "wipe",     "frames": (780, 789), "out": "chateau", "in": "canal", "dir": "L->R"},
    {"type": "dip",      "frames": (930, 935), "out": "canal",   "in": "cafe"},
    {"type": "slide",    "frames": (1142, 1145), "out": "meanwhile_card", "in": "creator", "dir": "up"},
    {"type": "dissolve", "frames": (1320, 1329), "out": "creator", "in": "flatlay"},
    {"type": "dissolve", "frames": (1480, 1489), "out": "flatlay", "in": "cafe_mirror", "flash_mid": ("book", 1484, 1485)},
    {"type": "wipe",     "frames": (1590, 1597), "out": "cafe_mirror", "in": "bwdesk", "dir": "R->L"},
]

def seg_by_name(name):
    for s in SEGMENTS:
        if s["name"] == name:
            return s
    raise KeyError(name)

def check_invariants():
    """Sanity: total, non-overlap of bodies, display containment."""
    assert SEGMENTS[-1]["display"][1] == TOTAL - 1
    for i, s in enumerate(SEGMENTS):
        assert s["display"][0] <= s["body"][0] <= s["body"][1] <= s["display"][1], s
        if i:
            prev = SEGMENTS[i - 1]
            # bodies must not overlap (except none should)
            assert s["body"][0] > prev["body"][1] or s["id"] == "S8", (prev, s)
    # flash frames must fall in gaps
    assert FLASH_FRAMES["onion"] == (1080, 1081)
    assert SEGMENTS[7]["body"][1] == 1079 and SEGMENTS[8]["body"][0] == 1082

if __name__ == "__main__":
    check_invariants()
    print("timeline OK: %d frames, %d segments, %d transitions" % (TOTAL, len(SEGMENTS), len(TRANSITIONS)))
    for t in TRANSITIONS:
        print(" ", t["id"], t["kind"], t["frames"])
