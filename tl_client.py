#!/usr/bin/env python3
"""Twelve Labs client wrapper with dual API-key rotation + proxy support.

Env:
  TL_API_KEY_1 / TL_API_KEY_2   (both required; auto-failover on 401/429)
  TL_MODEL                      (default pegasus1.5)
  TL_INDEX_NAME                 (default video-editor-bench)
  HTTPS_PROXY / HTTP_PROXY      (honored by requests/twelvelabs SDK)
  TL_BASE_URL                   (default https://api.twelvelabs.io)

Design:
  - Round-robin across keys; on 401/429/rate-limit, cool down the failed key
    and rotate to the other. If both fail, sleep and retry once.
  - Resume-safe: asset_id can be cached via TL_ASSET_ID env (re-index is the
    expensive/slow step).
  - Thin wrapper around the official twelvelabs SDK so the rest of the bench
    doesn't need to know about keys.
"""
from __future__ import annotations

import json
import os
import time
from typing import Optional

try:
    import requests
except ImportError:  # pragma: no cover
    requests = None


def _proxy_env() -> dict:
    """Return proxies dict honoring HTTPS_PROXY/HTTP_PROXY (for codespace outbound)."""
    proxies = {}
    for var in ("HTTPS_PROXY", "HTTP_PROXY", "ALL_PROXY"):
        val = os.environ.get(var) or os.environ.get(var.lower())
        if val:
            proxies["https"] = val
            proxies["http"] = val
            break
    return proxies


PROXIES = _proxy_env()


def _env_keys() -> list[str]:
    keys = []
    for i in (1, 2):
        k = os.environ.get(f"TL_API_KEY_{i}")
        if k:
            keys.append(k)
    single = os.environ.get("TL_API_KEY")
    if single and single not in keys:
        keys.append(single)
    if not keys:
        raise SystemExit("set TL_API_KEY_1 and TL_API_KEY_2 (or TL_API_KEY)")
    return keys


class TLClient:
    """Dual-key rotating Twelve Labs client.

    Methods mirror the subset of the SDK we use: assets.create/retrieve,
    analyze_stream. On 401/429 the failing key is cooled down and the next
    key is used. Both keys exhausted => sleep 60s and retry the first key once.
    """

    def __init__(self):
        self.keys = _env_keys()
        self._key_idx = 0
        self._cooldown_until = {}  # key -> timestamp
        self.model = os.environ.get("TL_MODEL", "pegasus1.5")
        self.index_name = os.environ.get("TL_INDEX_NAME", "video-editor-bench")
        self.base_url = os.environ.get("TL_BASE_URL", "https://api.twelvelabs.io")
        self._sdk = None

    def _sdk_client(self, api_key: str):
        """Lazily import and construct a TwelveLabs SDK client for one key."""
        if self._sdk is None:
            import twelvelabs  # type: ignore
            self._sdk = twelvelabs
        # SDK reads proxies from env; set them per-call via session if needed.
        return self._sdk.TwelveLabs(api_key=api_key)

    def _current_key(self) -> str:
        return self.keys[self._key_idx % len(self.keys)]

    def _rotate(self):
        self._key_idx = (self._key_idx + 1) % len(self.keys)

    def _mark_cool(self, key: str, seconds: int = 60):
        self._cooldown_until[key] = time.time() + seconds

    def _available_key(self) -> Optional[str]:
        now = time.time()
        for _ in range(len(self.keys)):
            k = self._current_key()
            if k not in self._cooldown_until or now >= self._cooldown_until[k]:
                return k
            self._rotate()
        return None

    def _call_with_rotation(self, fn, *args, **kwargs):
        """Run `fn(client, *args, **kwargs)` rotating keys on 401/429."""
        last_err = None
        tries = len(self.keys) + 1  # one pass over keys + one retry of first
        for attempt in range(tries):
            key = self._available_key()
            if key is None:
                # all on cooldown; wait for the earliest to expire
                earliest = min(self._cooldown_until.values())
                sleep_for = max(1, earliest - time.time())
                print(f"  [tl] all keys cooling; sleeping {sleep_for:.0f}s", flush=True)
                time.sleep(sleep_for)
                continue
            try:
                client = self._sdk_client(key)
                return fn(client, *args, **kwargs)
            except Exception as e:
                last_err = e
                msg = str(e)[:200]
                is_rate = ("429" in msg) or ("Too Many" in msg) or ("rate" in msg.lower())
                is_auth = ("401" in msg) or ("Unauthorized" in msg) or ("invalid" in msg.lower())
                if is_auth or is_rate:
                    print(f"  [tl] key rotated ({'auth' if is_auth else 'rate-limit'}): {msg}", flush=True)
                    self._mark_cool(key)
                    self._rotate()
                    continue
                # non-rotatable error; re-raise
                raise
        raise last_err

    # ---- SDK-level operations ------------------------------------------------

    def upload_asset(self, video_path: str):
        """Upload and index a video. Returns (asset_id, upload_seconds)."""
        t0 = time.time()

        def _create(client):
            with open(video_path, "rb") as fh:
                asset = client.assets.create(method="direct", file=fh)
            return asset

        asset = self._call_with_rotation(_create)
        print(f"asset id={asset.id} status={asset.status}", flush=True)
        while asset.status not in ("ready", "failed"):
            time.sleep(5)
            asset = self._call_with_rotation(lambda c, aid=asset.id: c.assets.retrieve(aid))
            print(f"  asset {asset.status} ({time.time() - t0:.0f}s)", flush=True)
        if asset.status == "failed":
            raise SystemExit("asset processing failed")
        return asset.id, round(time.time() - t0, 1)

    def analyze(self, asset_id: str, prompt: str):
        """Run Pegasus analyze_stream on an indexed asset. Returns answer text."""
        from twelvelabs.types import VideoContext_AssetId, AnalyzePromptV2  # type: ignore

        def _analyze(client):
            video = VideoContext_AssetId(asset_id=asset_id)
            chunks = []
            stream = client.analyze_stream(
                model_name=self.model, video=video,
                prompt_v_2=AnalyzePromptV2(input_text=prompt),
            )
            for ev in stream:
                if getattr(ev, "event_type", None) == "text_generation":
                    chunks.append(getattr(ev, "text", "") or "")
            return "".join(chunks).strip()

        return self._call_with_rotation(_analyze)


def load_answers(path: str) -> dict:
    if not os.path.exists(path):
        return {}
    with open(path) as fh:
        doc = json.load(fh)
    if isinstance(doc, dict) and "answers" in doc:
        return doc["answers"]
    return doc


def save_answers(path: str, answers: dict):
    with open(path, "w") as fh:
        json.dump(answers, fh, indent=1, ensure_ascii=False)


if __name__ == "__main__":
    c = TLClient()
    print("keys:", len(c.keys), "| model:", c.model, "| index:", c.index_name)
    if PROXIES:
        print("proxy:", PROXIES)
