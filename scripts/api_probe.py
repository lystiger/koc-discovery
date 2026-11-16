"""Probe Kalodata Open API creator/detail for audience fields. Probe loop capped at 6 calls; header discovery adds 0 calls when KALODATA_AUTH_HEADER is set, else 1-6 candidate attempts (observed run: 1 + 6 = 7 calls, ~0.7 credit).

Env:
  KALODATA_API_KEY      secret key from the Kalodata Account page (never written to disk)
  KALODATA_AUTH_HEADER  header name the key goes in, as shown on the key page / docs example
Writes reports/api_probe_<UTC timestamp>.json with response bodies (no key, no headers).
If that name exists, appends _1, _2, ... Never overwrites an earlier probe.
"""
import json
import os
import sys
from datetime import datetime, timezone

import httpx

URL = "https://www.kalodata.com/openapi/v1/tiktok/creator/detail"
CREATORS = ["6798739018520839169", "7039923617978975234", "7072683155098272773"]
MAX_CALLS = 6


# Docs say only "secret-key authentication in headers"; header name unpublished, so try in order.
HEADER_CANDIDATES = [("secret-key", ""), ("Secret-Key", ""), ("X-Secret-Key", ""),
                     ("Authorization", "Bearer "), ("X-API-KEY", ""), ("api-key", "")]
AUTH_FAIL_CODES = {401, 403}


def find_header(key: str) -> tuple[str, str]:
    """Return the first header name the API does not reject as unauthenticated."""
    body = {"region": "VN", "language": "en-US", "currency": "VND", "date_range": "last30Day",
            "creator_id": CREATORS[0], "need_extra": False}
    for name, prefix in HEADER_CANDIDATES:
        r = httpx.post(URL, json=body, headers={name: prefix + key}, timeout=30)
        text = r.text[:200]
        print(f"try {name}: HTTP {r.status_code} {text}")
        auth_error = r.status_code in AUTH_FAIL_CODES or any(w in text.lower() for w in ("auth", "key", "unauthor", "token"))
        if not auth_error:
            return name, prefix
    sys.exit("no header candidate accepted; check Account page for the header name")


def save_report(results: list) -> str:
    """Write results to a new file (never overwrite): api_probe_<ts>.json, then _1, _2, ..."""
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    n = 0
    while True:
        path = f"reports/api_probe_{stamp}{'' if n == 0 else f'_{n}'}.json"
        try:
            with open(path, "x", encoding="utf-8") as f:
                json.dump(results, f, ensure_ascii=False, indent=2)
            return path
        except FileExistsError:
            n += 1


def main() -> None:
    key = os.environ["KALODATA_API_KEY"]
    if os.environ.get("KALODATA_AUTH_HEADER"):
        header, prefix = os.environ["KALODATA_AUTH_HEADER"], ""
    else:
        header, prefix = find_header(key)
    print(f"using header: {header}")
    results, calls = [], 0
    with httpx.Client(timeout=30, headers={header: prefix + key}) as client:
        for creator_id in CREATORS:
            for need_extra in (False, True):
                if calls >= MAX_CALLS:
                    sys.exit("call cap reached")
                body = {"region": "VN", "language": "en-US", "currency": "VND",
                        "date_range": "last30Day", "creator_id": creator_id, "need_extra": need_extra}
                r = client.post(URL, json=body)
                calls += 1
                payload = r.json() if r.headers.get("content-type", "").startswith("application/json") else r.text
                results.append({"creator_id": creator_id, "need_extra": need_extra, "status": r.status_code, "body": payload})
                data = payload.get("data") if isinstance(payload, dict) else None
                if isinstance(data, dict):  # contact details are PII we do not need
                    for k in data:
                        if k.startswith("creator_contact_") and data[k]:
                            data[k] = "[redacted]"
                keys = sorted(data) if isinstance(data, dict) else None
                print(creator_id, "need_extra" if need_extra else "plain", r.status_code, keys)
                if r.status_code != 200 or not (isinstance(payload, dict) and payload.get("success")):
                    print("stopping: non-success response:", str(payload)[:300])
                    save_report(results)
                    return
    out = save_report(results)
    print(f"{out}: {calls} calls; audience-like keys:",
          sorted({k for x in results if isinstance(x["body"], dict) and isinstance(x["body"].get("data"), dict)
                  for k in x["body"]["data"] if any(w in k.lower() for w in ("gender", "age", "audience", "fan", "region", "location"))}))


if __name__ == "__main__":
    main()
