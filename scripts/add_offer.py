from pathlib import Path
import argparse, json, hashlib, time, requests, sys, copy, base64

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
    ap.add_argument("--url", required=True)
    ap.add_argument("--price", required=True)
    ap.add_argument("--royalty", required=True)
    a = ap.parse_args()

    r = requests.get(a.url, timeout=20)
    if r.status_code != 200: print("[err] fetch failed", r.status_code); sys.exit(2)
    j = r.json()

    payload = canon_bytes(j)
    h = sha256_hex(payload); sid = h[:12]
    ok, pub, note = False, "", ""
    try:
        from nacl.signing import VerifyKey  # noqa
        ok, pub, note = verify_any(j)
    except Exception as e:
        note = f"verify err: {e}"

    price = float(a.price); royalty_bps = int(a.royalty)
    now = int(time.time())
    pol = j.get("policy", {}); use = pol.get("use", {})
    if not pol.get("broker_ok", False): print("[err] broker_ok=false"); sys.exit(2)
    if not use.get("sale", False): print("[err] use.sale=false"); sys.exit(2)

    offer = {
      "id": sid, "ts": now, "price_usd": price, "royalty_bps": royalty_bps,
      "receipt_url": a.url, "hash": h,
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
    print(f"[ok] listed {sid} sig={'Verified' if ok else 'Unverified'}")

if __name__ == "__main__":
    main()
