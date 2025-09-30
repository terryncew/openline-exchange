# scripts/validate_offers.py
from pathlib import Path
import json, sys
REQ = ["id","merchant_id","sku","price","currency"]
OFFERS = Path("docs/offers")

def main():
    ok=True
    for p in sorted(OFFERS.glob("*.json")):
        j=json.loads(p.read_text("utf-8"))
        missing=[k for k in REQ if k not in j]
        if isinstance(j.get("price"), dict):
            if "amount" not in j["price"]: missing.append("price.amount")
        else:
            missing.append("price.amount")
        if missing:
            ok=False; print(f"[fail] {p.name}: missing {missing}")
        else:
            print(f"[ok] {p.name}")
    sys.exit(0 if ok else 2)

if __name__=="__main__":
    main()
