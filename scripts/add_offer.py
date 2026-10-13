from pathlib import Path
import argparse, json, hashlib, time, sys, copy, base64, math
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, ProxyHandler, HTTPRedirectHandler
from urllib.error import URLError

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None

ROOT = Path(__file__).resolve().parents[1]
OFFERS_DIR = ROOT / "docs" / "offers"
OFFERS_DIR.mkdir(parents=True, exist_ok=True)
INDEX = OFFERS_DIR / "index.json"

def to_bytes(s: str) -> bytes:
    s = (s or "").strip()
    try: return bytes.fromhex(s)
    except Exception: pass
    pad = '=' * ((4 - (len(s) % 4)) % 4)
    for dec in (base64.b64decode, base64.urlsafe_b64decode):
        try: return dec(s + pad)
        except Exception: continue
    raise ValueError("bad encoding")

def canon_bytes(j: dict) -> bytes:
    x = copy.deepcopy(j); x.pop("sig", None); x.pop("offer", None)
    return json.dumps(x, sort_keys=True, separators=(",",":")).encode("utf-8")

def verify_any(j: dict):
    from nacl.signing import VerifyKey
    payload = canon_bytes(j)
    sigs = j.get("signatures") or []
    for row in sigs:
        if (row.get("alg") or "").lower() == "ed25519":
            try:
                VerifyKey(to_bytes(row.get("key_id"))).verify(payload, to_bytes(row.get("sig")))
                return True, row.get("key_id",""), ""
            except Exception:
                pass
    legacy = j.get("sig") or {}
    if legacy.get("pub") and (legacy.get("sig") or legacy.get("signature")):
        try:
            VerifyKey(to_bytes(legacy["pub"])).verify(payload, to_bytes(legacy.get("sig") or legacy.get("signature")))
            return True, legacy["pub"], ""
        except Exception as e:
            return False, legacy.get("pub",""), f"verify fail: {e}"
    return False, "", "no usable signature"

def sha256_hex(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()

def main():
    ap = argparse.ArgumentParser()
    source = ap.add_mutually_exclusive_group(required=True)
    source.add_argument("--url", help="Operator-only approved public HTTPS receipt URL")
    source.add_argument("--file", type=Path, help="Reviewed local JSON receipt; preferred")
    ap.add_argument("--allowed-host", action="append", default=[], help="Explicit approved host; only raw.githubusercontent.com or terryncew.github.io")
    ap.add_argument("--price", required=True)
    ap.add_argument("--royalty", required=True)
    a = ap.parse_args()

    max_bytes = 1024 * 1024
    receipt_url = a.url or ""
    try:
        if a.file:
            local = a.file.resolve()
            if a.file.is_symlink() or not local.is_file() or local.stat().st_size > max_bytes or local.suffix != ".json":
                raise ValueError("expected bounded reviewed local JSON")
            payload_bytes = local.read_bytes()
        else:
            allowed = {"raw.githubusercontent.com", "terryncew.github.io"}
            u = urlsplit(a.url)
            if (u.scheme != "https" or u.hostname not in allowed or u.hostname not in a.allowed_host
                    or u.username or u.password or u.port not in (None, 443) or u.fragment
                    or "\\" in a.url or any(ch.isspace() for ch in a.url)):
                raise ValueError("URL needs explicit approved HTTPS host without credentials")
            # No redirects, ambient authentication, cookies, or proxy credentials.
            opener = build_opener(ProxyHandler({}), NoRedirect())
            request = Request(a.url, headers={"Accept": "application/json"}, method="GET")
            with opener.open(request, timeout=20) as response:
                if response.status != 200:
                    raise ValueError("receipt fetch did not return 200; redirects prohibited")
                size = response.headers.get("Content-Length")
                if size and (not size.isdigit() or int(size) > max_bytes):
                    raise ValueError("receipt response too large")
                payload_bytes = response.read(max_bytes + 1)
                if len(payload_bytes) > max_bytes:
                    raise ValueError("receipt response too large")
        def pairs(rows):
            result = {}
            for key, value in rows:
                if key in result:
                    raise ValueError("duplicate JSON keys")
                result[key] = value
            return result
        j = json.loads(payload_bytes, object_pairs_hook=pairs, parse_constant=lambda _: (_ for _ in ()).throw(ValueError("non-finite JSON")))
        if not isinstance(j, dict):
            raise ValueError("receipt needs a JSON object")
    except (ValueError, OSError, URLError):
        print("[err] receipt rejected; use reviewed local bounded JSON or an explicitly approved HTTPS source")
        return 2

    payload = canon_bytes(j)
    h = sha256_hex(payload); sid = h[:12]
    ok, pub, note = False, "", ""
    try:
        from nacl.signing import VerifyKey  # noqa
        ok, pub, note = verify_any(j)
    except Exception as e:
        note = f"verify err: {e}"

    try:
        price = float(a.price); royalty_bps = int(a.royalty)
        if not math.isfinite(price) or price < 0 or not 0 <= royalty_bps <= 10000:
            raise ValueError("price or royalty outside supported bounds")
    except ValueError:
        print("[err] price must be finite and nonnegative; royalty 0-10000")
        return 2
    now = int(time.time())
    pol = j.get("policy", {}); use = pol.get("use", {})
    if not pol.get("broker_ok", False): print("[err] broker_ok=false"); sys.exit(2)
    if not use.get("sale", False): print("[err] use.sale=false"); sys.exit(2)

    offer = {
      "id": sid, "ts": now, "price_usd": price, "royalty_bps": royalty_bps,
      "receipt_url": receipt_url, "hash": h,
      "summary": {
        "claim": j.get("claim",""),
        "status": (j.get("attrs",{}) or {}).get("status","") or j.get("status",""),
        "why": (j.get("but") or [""])[0] if isinstance(j.get("but"), list) else "",
        "policy": {
          "license": pol.get("license",""),
          "train": bool(use.get("train", False)),
          "share": use.get("share","none"),
          "sale": bool(use.get("sale", False))
        },
        "sig": { "verified": bool(ok), "pub": pub, "note": note }
      }
    }

    f = OFFERS_DIR / f"{sid}.json"
    f.write_text(json.dumps(offer, indent=2), encoding="utf-8")
    items = []
    if INDEX.exists():
        try: items = json.loads(INDEX.read_text("utf-8"))
        except: items = []
    items = [x for x in items if x.get("id") != sid]
    items.append({k: offer[k] for k in ("id","ts","price_usd","royalty_bps","receipt_url","hash","summary")})
    items.sort(key=lambda x: x["ts"], reverse=True)
    INDEX.write_text(json.dumps(items, indent=2), encoding="utf-8")
    print(f"[ok] prepared {sid}; key signature={'authenticated' if ok else 'not authenticated'}; outcomes not verified")
    return 0

if __name__ == "__main__":
    sys.exit(main())
