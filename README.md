# OpenLine Exchange

List verifiable **OpenLine receipts** with rights-in-file (OLH-1.0).  
All static: GitHub Actions + Pages.

## Quick start
1. Create this repo, paste files, commit.
2. Settings → Pages → Source: **Deploy from a branch**, Branch: **main**, Folder: **/docs** → Save.
3. Actions → **Add offer (OpenLine Exchange)** → paste a `receipt.latest.json` URL → set price + royalty → Run.
4. Visit: `https://<you>.github.io/<repo>/`

## Gates
- `policy.broker_ok` must be `true`
- `policy.use.sale` must be `true`
- Minimal schema: `claim`, `telem`, `policy` present

## Verification
If the receipt includes `sig.pub` (Ed25519 public key) and `sig.sig` (signature over the canonical JSON without `sig`/`offer`), the card shows **Verified**. Otherwise: Unverified/No signature.

## What buyers see
Status (green/amber/red), Why, Policy (train/share/sale), Price, Royalty bps, Hash, and Signature badge.  
**Preview** opens the receipt; **Request Purchase** opens a prefilled GitHub Issue.

## Notes
- Money happens off-platform (invoice, Stripe, wire).
- Offers are just JSON files in `docs/offers/`. Forks can rebuild the index anytime.
