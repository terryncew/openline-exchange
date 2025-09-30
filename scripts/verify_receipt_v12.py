# scripts/verify_receipt_v12.py
from pathlib import Path
import json, sys

RECEIPT = Path("docs/receipt.latest.json")
STATUS  = Path("docs/status.json")

def main():
    status = {"verified": False, "reason": "missing"}
    if RECEIPT.is_file():
        try:
            r = json.loads(RECEIPT.read_text("utf-8"))
            ok = r.get("receipt_version","").startswith("olr/1.2") and "training_evolution" in r
            status["verified"] = bool(ok)
            status["reason"] = "ok" if ok else "receipt_version<1.2 or no training_evolution"
        except Exception as e:
            status["verified"] = False
            status["reason"] = f"parse_error {e}"
    STATUS.write_text(json.dumps(status, indent=2), encoding="utf-8")
    print(f"[exchange] verified={status['verified']} reason={status['reason']}")
    sys.exit(0)

if __name__ == "__main__":
    main()
