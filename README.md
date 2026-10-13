# OpenLine Exchange

List verifiable **OpenLine receipts** with rights-in-file (OLH-1.0).  
All static: GitHub Actions + Pages.

## Quick start
1. Create this repo, paste files, commit.
2. For the beta, follow the protected, manual deployment plan in `docs/beta/README.md`; do not enable automatic branch publication.
3. Manual **Prepare legacy offer artifact** uses the reviewed local receipt, price and royalty, and creates an artifact for review without publication.
4. Visit after separately approved deployment: `https://<you>.github.io/<repo>/`

## Gates
- `policy.broker_ok` must be `true`
- `policy.use.sale` must be `true`
- Minimal schema: `claim`, `telem`, `policy` present

## Verification
If the receipt includes `sig.pub` (Ed25519 public key) and `sig.sig` (signature over the canonical JSON without `sig`/`offer`), a valid signature authenticates that key and payload. It does not prove the task succeeded or establish legal identity. Legacy `sig.verified` fields retain their existing format; new beta labels separate key authenticity from outcome verification.

## What buyers see
Status (green/amber/red), Why, Policy (train/share/sale), Price, Royalty bps, Hash, and Signature badge.  
**Preview** opens the receipt; **Request Purchase** opens a prefilled GitHub Issue.

## Notes
- Money happens off-platform (invoice, Stripe, wire).
- Offers are just JSON files in `docs/offers/`. Forks can rebuild the index anytime.

## Limited public beta preview

The new capability catalog and buyer-facing Bureau Select live at [`docs/beta/`](docs/beta/README.md), extending this Exchange while preserving legacy receipts and offers. Real reviewed listings start empty; clearly labeled synthetic examples are opt-in. See that guide for local startup, validation and the separate approval conditions for opening the beta. Legacy automatic publication has been removed: manual offer preparation produces a review artifact, and Pages requires a manual protected deployment.
