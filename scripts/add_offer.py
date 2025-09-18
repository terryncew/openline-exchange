from pathlib import Path
import argparse, json, hashlib, time, requests, sys, copy, base64

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_DIR = ROOT / "schema"
OFFERS_DIR = ROOT / "docs" / "offers"
OFFERS_DIR.mkdir(parents=True, exist_ok=True)
INDEX = OFFERS_DIR / "index.json"

def load_schema(name):
    p = SCHEMA_DIR / name
    return json.loads(p.read_text("utf-8"))

def validate(instance, schema):
    import jsonschema
    jsonschema.validate(instance=instance, schema=schema)

def sha256_hex(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()

def to_bytes(s: str) -> bytes:
    """Accept base64 (std/urlsafe, with/without padding) or hex."""
    s = s.strip()
    # hex?
    try:
        return bytes.fromhex(s)
    except Exception:
        pass
    # normalize base64 padding
    pad = '=' * ((4 - (len(s) % 4)) % 4)
    for decoder in (base64.b64decode, base64.urlsafe_b64decode):
        try:
            return decoder(s + pad)
        except Exception:
            continue
    raise ValueError("bad key/sig encoding")

def canon_bytes(j: dict) -> bytes:
    """Canonical payload: JSON without 'sig' or 'offer', sorted & tight separators."""
    payload = copy.deepcopy(j)
    payload.pop("sig", None)
    payload.pop("offer", None)
    return json.dumps(payload, sort_keys=True, separators=(",",":")).encode("utf-8")

def verify_sig(j: dict):
    """Return (verified:bool, pubkey_str:str, reason:str). Ed25519 over canonical payload."""
    sig = j.get("sig") or {}
    alg = (sig.get("alg") or "ed25519").lower()
    pub = sig.get("pub") or ""
    s   = sig.get("sig") or sig.get("signature") or ""
    if not pub or not s:
        return (False, "", "missing sig/pub")
    if alg != "ed25519":
        return (False, pub, f"unsupported alg {alg}")

    try:
        from nacl.signing import VerifyKey
        pk = to_bytes(pub)
        sig_bytes = to_bytes(s)
        vk = VerifyKey(pk)
        vk.verify(canon_bytes(j), sig_bytes)  # raises if bad
        return (True, pub, "")
    except Exception as e:
        return (False, pub, f"verify fail: {e}")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", required=True)
    ap.add_argument("--price", required=True)
    ap.add_argument("--royalty", required=True)
    a = ap.parse_args()

    # fetch receipt
    r = requests.get(a.url, timeout=20)
    if r.status_code != 200:
        print("[err] could not fetch receipt:", r.status_code)
        sys.exit(2)
    j = r.json()

    # minimal schema gate (claim + telem + policy presence)
    try:
        receipt_schema = load_schema("receipt.min.schema.json")
        validate(j, receipt_schema)
    except Exception as e:
        print("[err] schema validation failed:", e)
        sys.exit(2)

    # policy gates
    pol = j.get("policy", {})
    use = pol.get("use", {})
    if not pol.get("broker_ok", False):
        print("[err] policy.broker_ok=false → cannot list"); sys.exit(2)
    if not use.get("sale", False):
        print("[err] policy.use.sale=false → cannot list"); sys.exit(2)

    # canonical hash (over payload w/o sig/offer)
    canon = canon_bytes(j)
    h = sha256_hex(canon)
    sid = h[:12]

    # signature verification (optional)
    verified, pub, reason = verify_sig(j)

    # inputs
    try:
        price = float(a.price)
        royalty_bps = int(a.royalty)
        assert 0 <= royalty_bps <= 10000
    except Exception:
        print("[err] bad price/royalty inputs"); sys.exit(2)

    now = int(time.time())
    offer = {
      "id": sid,
      "ts": now,
      "price_usd": price,
      "royalty_bps": royalty_bps,
      "receipt_url": a.url,
      "hash": h,
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
        "sig": {
          "verified": bool(verified),
          "pub": pub,
          "note": ("" if verified else reason)
        }
      }
    }

    # write file
    f = OFFERS_DIR / f"{sid}.json"
    f.write_text(json.dumps(offer, indent=2), encoding="utf-8")

    # update index
    items = []
    if INDEX.exists():
        try: items = json.loads(INDEX.read_text("utf-8"))
        except Exception: items = []
    items = [x for x in items if x.get("id") != sid]
    items.append({k: offer[k] for k in ("id","ts","price_usd","royalty_bps","receipt_url","hash","summary")})
    items.sort(key=lambda x: x["ts"], reverse=True)
    INDEX.write_text(json.dumps(items, indent=2), encoding="utf-8")

    badge = "Verified" if verified else ("Unverified" if pub else "No signature")
    print(f"[ok] listed {sid}  hash={h[:10]}…  sig={badge}")

if __name__ == "__main__":
    main()
