# OpenLine Exchange limited public beta preview

This extends the existing static Exchange. The legacy receipt and offer formats remain at the original paths; `./beta/` is the new discovery, contribution and manual inquiry experience. Bureau compiles reviewed JSON records and validates evidence; Wallet remains the authority/signature foundation. No arbitrary capability code is executed, no payment is processed, and no public deployment has been performed.

## Run the complete local experience

Use a **trusted, reviewed Bureau checkout** on the matching `feat/openline-public-beta` branch. The operator build executes Bureau's compiler and frozen-trial verifier; do not point it at an unreviewed contribution checkout.

```sh
/workspace/openline-venv/bin/python scripts/build_beta.py --bureau /workspace/openline-bureau
python -m http.server 8765 --bind 127.0.0.1 --directory docs
```

Open `http://127.0.0.1:8765/beta/`. The reviewed catalog intentionally starts empty. Opt in to **Show synthetic examples** to inspect versions, independent-evaluation reports, failures, missing evidence, worker records, comparisons, a local sample inquiry, and Bureau Select's documented-evidence shortlist. Synthetic examples cannot create a real inquiry. The frozen allocation exhibit preserves improvements, reversed results and inconclusive sparse evidence, including cost denominators in simulated currency.

## Validation

```sh
python scripts/validate_beta.py
python -m unittest discover -s tests -p 'test_*.py'
node --test tests/beta_model.test.mjs
node --check docs/beta/app.js
```

The build manifest binds output files to hashes and records the Bureau compiler/trial verifier hashes. These hashes do not authenticate a maintainer or establish actual task outcomes. Review the corresponding Bureau source and publication registry before releasing data. Public data contributions use Bureau's reviewed data-only PR path; Exchange UI/infrastructure changes receive ordinary maintainer code review and do not grant permission to run contributed capability code.

Browser coverage runs in CI with the pinned `tests/requirements-browser.txt`. For a local installed Chromium:

```sh
/workspace/openline-venv/bin/python tests/browser_beta.py --chromium /usr/bin/chromium
```

If preparing another machine, install the pinned requirements and use Playwright's supported browser installation with TLS/checksum verification: `python -m playwright install --with-deps chromium`. Supply the installed browser executable via `--chromium`. The suite serves an ephemeral loopback site and blocks every external request. Optional `--screenshots-dir /tmp/beta-screenshots` captures synthetic-only review assets.

## Discovery and contribution

- Reviewed catalog: `catalog/v1/index.json`, format `openline.catalog.v1`.
- Synthetic walkthrough: `synthetic/v1/index.json`, separate file with `synthetic: true`.
- Frozen research: `economic-validation.json`, format `openline.bureau.economic-validation.v1`; simulated only.
- [Contribution and evaluation instructions](https://github.com/terryncew/openline-bureau/blob/feat/openline-public-beta/docs/beta/CONTRIBUTING.md).
- [Security boundaries and review procedure](https://github.com/terryncew/openline-bureau/blob/feat/openline-public-beta/docs/beta/SECURITY.md).
- [Exact deployment and opening conditions](https://github.com/terryncew/openline-bureau/blob/feat/openline-public-beta/docs/beta/DEPLOYMENT.md).

The inquiry path requires both an operator-enabled catalog policy and a reviewed capability explicitly accepting inquiries at the approved Bureau GitHub issue entrypoint. The visitor reviews a public-safe draft and chooses whether to open GitHub; only the visitor can publish it. An inquiry is not an agreement, authorization, payment, settlement or delivery promise. Pricing remains a contributor's offered quote.

## Opening to outside contributors

The companion deployment plan is authoritative. At minimum: review and merge the trusted validator/UI changes separately; configure protected Pages reviewers and disable branch-source auto-deployment; approve publication of each real evidence record and its rights; verify contributor separation and any reproduction attestations; designate maintainers for submissions and moderation; obtain separate approval before publishing this beta or enabling real inquiry acceptance. Update documentation links from the draft branch to the merged version as part of the approved release.

Pages deployment is a manual workflow guarded by `github-pages`, limited to `main`, and blocked by beta artifact checks. It uploads only the curated `docs/beta` bundle, so the deployed route is the Pages site root; legacy receipt files are retained in the repository and excluded from this new publication. Environment protection must be configured in GitHub settings for its review gate to be effective. The old arbitrary-URL/direct-main offer workflow now prepares an artifact from an existing reviewed local receipt; it never commits or publishes it. The legacy CLI permits only explicitly approved HTTPS hosts, rejects redirects and limits response size; reviewed local files are preferred.

The hosted GitHub Actions and protected Pages approval path have been prepared but have not been run or publicly validated. Local tests exercise the same artifact and browser gates; the approved release must verify environment reviewers, branch protections and the live static bundle before inviting a pilot.
