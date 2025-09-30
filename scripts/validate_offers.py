from pathlib import Path, PurePosixPath as P
import json, sys
ROOT = Path("docs/offers")
req = ["id","merchant_id","sku","price"]
ok=True
for f in sorted(ROOT.glob("*.json")):
    j=json.loads(f.read_text("utf-8"))
    miss=[k for k in req if k not in j] or ([] if isinstance(j.get("price"),dict) and "amount" in j["price"] and "currency" in j["price"] else ["price.amount","price.currency"])
    if miss: print(f"[err] {P(f).name} missing {miss}"); ok=False
    else:    print(f"[ok]  {P(f).name}")
sys.exit(0 if ok else 2)
