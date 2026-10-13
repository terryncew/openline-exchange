#!/usr/bin/env python3
"""Exercise the Exchange beta in Chromium without contacting external services.

Uses an ephemeral loopback-only static server by default. Requires Python's
Playwright package and a local Chromium executable; it never downloads browsers.
All non-loopback browser requests are aborted. Optional screenshots contain
synthetic examples only. No inquiry is submitted and no customer data is stored.
"""

from __future__ import annotations

import argparse
import contextlib
import functools
import hashlib
import http.server
import json
from pathlib import Path
import threading
from urllib.parse import parse_qs, urljoin, urlsplit

from playwright.sync_api import expect, sync_playwright


REPO = Path(__file__).resolve().parents[1]


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, _format: str, *_args: object) -> None:
        pass


@contextlib.contextmanager
def local_server():
    handler = functools.partial(QuietHandler, directory=str(REPO / "docs"))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def is_loopback(url: str) -> bool:
    parsed = urlsplit(url)
    return parsed.scheme in {"http", "https"} and parsed.hostname in {
        "127.0.0.1", "localhost", "::1"
    }


def snapshot(page, output: Path | None, name: str) -> None:
    if output:
        output.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(output / name), full_page=True)


def run_browser(base_url: str, chromium: str, screenshots: Path | None) -> None:
    if not is_loopback(base_url):
        raise ValueError("Browser tests accept a loopback base URL only.")
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            executable_path=chromium, headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )
        try:
            exercise_beta(browser, base_url, screenshots)
        finally:
            browser.close()


def exercise_beta(browser, base_url: str, screenshots: Path | None) -> None:
    """UI contract checks are kept together to preserve a readable user journey."""
    context = browser.new_context(viewport={"width": 1440, "height": 1050}, reduced_motion="reduce")
    console_errors: list[str] = []
    page_errors: list[str] = []
    external_requests: list[str] = []

    def network_guard(route):
        if is_loopback(route.request.url):
            route.continue_()
        else:
            external_requests.append(route.request.url)
            route.abort("blockedbyclient")

    context.route("**/*", network_guard)

    def record_errors(page):
        page.on("pageerror", lambda error: page_errors.append(str(error)))
        page.on("console", lambda message: console_errors.append(message.text) if message.type == "error" else None)

    context.on("page", record_errors)
    page = context.new_page()
    page.goto(urljoin(base_url, "beta/"), wait_until="networkidle")
    expect(page.get_by_role("heading", level=1)).to_contain_text("Evidence you can inspect")
    expect(page.locator("#synthetic-toggle")).not_to_be_checked()
    expect(page.locator("#empty")).to_be_visible()
    expect(page.locator("#empty")).to_contain_text("No reviewed capabilities are published yet")
    expect(page.locator("#cards .card")).to_have_count(0)
    expect(page.locator("#synthetic-notice")).to_be_hidden()
    expect(page.locator(".boundary")).to_contain_text("No payment")
    snapshot(page, screenshots, "beta-reviewed-empty-desktop.png")

    # Keyboard users can skip navigation and reach the main content.
    page.keyboard.press("Tab")
    expect(page.locator("a.skip")).to_be_focused()
    page.keyboard.press("Enter")
    assert page.evaluate("document.activeElement.id") == "main", "Skip link did not focus the main content."

    # The contribution path is reviewed GitHub data, and agent discovery is JSON.
    for link in page.locator("#contribute a[href^='https:']").all():
        parsed = urlsplit(link.get_attribute("href"))
        assert parsed.scheme == "https" and parsed.netloc == "github.com"
        assert parsed.path.startswith("/terryncew/openline-bureau/")
        assert "noopener" in (link.get_attribute("rel") or "")
    expect(page.locator("#contribute")).to_contain_text("pull request")
    expect(page.locator("#contribute")).to_contain_text("Attribution metadata records credit")
    json_href = page.locator("#discover .text-link").get_attribute("href")
    assert json_href and json_href.endswith("catalog/v1/index.json")
    json_url = urljoin(page.url, json_href)
    assert is_loopback(json_url), "Agent discovery unexpectedly points outside the local test server."
    response = context.request.get(json_url)
    assert response.ok, f"Agent catalog unavailable: HTTP {response.status}"
    catalog = response.json()
    assert catalog.get("format") == "openline.catalog.v1", "Catalog schema is not versioned."
    assert catalog.get("synthetic") is False, "The reviewed catalog is mislabeled."
    assert catalog.get("capabilities") == [], "Default shipped catalog must contain no unsupported real listings."

    exercise_synthetic_journey(page, catalog, screenshots)
    exercise_injected_security_and_inquiry(context, base_url)
    exercise_mobile(context, base_url, screenshots)
    assert not page_errors, f"Browser runtime exceptions: {page_errors}"
    assert not console_errors, f"Browser console errors: {console_errors}"
    assert not external_requests, f"UI attempted external requests: {external_requests}"
    assert page.evaluate("localStorage.length") == 0, "The workflow unexpectedly stored browser data."
    assert page.evaluate("sessionStorage.length") == 0, "The workflow unexpectedly stored session data."
    context.close()
    print("PASS: empty reviewed catalog, synthetic journey, Bureau Select, contribution/agent discovery, inquiry safety, XSS, mobile and keyboard.")


def exercise_synthetic_journey(page, catalog: dict, screenshots: Path | None) -> None:
    synthetic_url = urljoin(page.url, "synthetic/v1/index.json")
    assert is_loopback(synthetic_url)
    response = page.context.request.get(synthetic_url)
    assert response.ok, f"Synthetic walkthrough unavailable: HTTP {response.status}"
    synthetic = response.json()
    assert synthetic.get("format") == catalog["format"]
    assert synthetic.get("synthetic") is True
    capabilities = synthetic["capabilities"]
    assert len(capabilities) >= 3, "Walkthrough needs comparison, improvement and sparse-evidence cases."
    assert synthetic["workers"] and synthetic["evaluations"]
    assert all(row["synthetic"] is True for kind in ("capabilities", "workers", "evaluations") for row in synthetic[kind])
    assert all(row["inquiry"]["accepts_inquiries"] is False for kind in ("capabilities", "workers") for row in synthetic[kind])
    page.locator("#synthetic-toggle").check()
    cards = page.locator("#cards .card")
    expect(cards).to_have_count(len(capabilities))
    expect(page.locator("#synthetic-notice")).to_be_visible()
    expect(page.locator("#catalog-mode-title")).to_have_text("Synthetic example catalog")
    expect(page.locator("#synthetic-notice")).to_contain_text("Every skill, worker, price and evaluation below is invented")
    expect(page.locator("#cards .label.synthetic")).to_have_count(len(capabilities))
    snapshot(page, screenshots, "beta-synthetic-catalog-desktop.png")

    page.locator("#search").fill(capabilities[0]["name"].upper())
    assert cards.count() >= 1, "Case-insensitive name search did not find a capability."
    page.locator("#search").fill("no-matching-capability-test-431927")
    expect(cards).to_have_count(0)
    expect(page.locator("#empty")).to_be_visible()
    page.locator("#search").fill("")
    task = capabilities[0]["tasks"][0]
    page.locator("#task-filter").select_option(task)
    expect(cards).to_have_count(sum(task in capability["tasks"] for capability in capabilities))
    for card in cards.all():
        expect(card.locator(".task-tags")).to_contain_text(task)
    page.locator("#task-filter").select_option("")

    page.locator("#type-filter").select_option("workers")
    expect(cards).to_have_count(len(synthetic["workers"]))
    expect(page.locator("#cards .label.synthetic").first).to_contain_text("SYNTHETIC WORKER")
    expect(page.locator("#cards")).to_contain_text("Capability evidence does not establish worker performance")
    worker_checks = page.locator("#cards input[type='checkbox']")
    worker_checks.nth(0).check()
    expect(page.locator("#compare-content .compare-item")).to_have_count(1)
    worker_checks.nth(1).check()
    worker_comparisons = page.locator("#compare-content .compare-item")
    expect(worker_comparisons).to_have_count(2)
    for comparison in worker_comparisons.all():
        expect(comparison).to_contain_text("Worker executions only")
        expect(comparison).to_contain_text("Skill evaluations do not establish this worker’s performance")
        expect(comparison).to_contain_text("No worker execution evaluation documented")
        independent_count = comparison.locator("dt", has_text="Separate-contributor worker evaluations").locator("xpath=following-sibling::dd[1]")
        expect(independent_count).to_have_text("0")
        expect(comparison).to_contain_text("No worker-level price is offered")
    snapshot(page, screenshots, "beta-synthetic-worker-compare-desktop.png")
    worker = synthetic["workers"][0]
    assert not any(evaluation.get("worker_id") == worker["id"] for evaluation in synthetic["evaluations"])
    worker_card = page.locator(f"#cards .card[data-id='{worker['id']}']")
    worker_card.locator("[data-action='worker-details']").click()
    worker_detail = page.locator("#detail-content")
    expect(page.locator("#detail-title")).to_have_text(worker["name"])
    expect(worker_detail).to_contain_text("No worker-specific evaluation is documented")
    expect(worker_detail).to_contain_text("Associated capabilities (inspect each version)")
    for capability in capabilities:
        if capability["id"] in worker["capability_ids"]:
            expect(worker_detail).to_contain_text(f"v{capability['version']}")
            for documented_task in capability["tasks"]:
                expect(worker_detail).to_contain_text(documented_task)
            if capability["price"]:
                expect(worker_detail).to_contain_text(f"{capability['price']['amount']} {capability['price']['currency']}")
            else:
                expect(worker_detail).to_contain_text("Price not offered")
    worker_original_url = urljoin(page.url, f"synthetic/v1/{worker['record_url']}")
    assert is_loopback(worker_original_url)
    worker_original = page.context.request.get(worker_original_url)
    assert worker_original.ok
    assert hashlib.sha256(worker_original.body()).hexdigest() == worker["record_sha256"]
    assert worker_original.json()["format"] == "openline.worker.v1"
    page.get_by_role("button", name="Create a local sample inquiry").click()
    assert "version worker profile" in page.locator("#inquiry-body").input_value()
    assert "SYNTHETIC SAMPLE" in page.locator("#inquiry-body").input_value()
    expect(page.locator("#inquiry-action a[href^='https:']")).to_have_count(0)
    page.keyboard.press("Escape")
    page.locator("#clear-compare").click()
    page.locator("#type-filter").select_option("capabilities")
    expect(cards).to_have_count(len(capabilities))
    page.locator("#sort").select_option("price")
    assert cards.count() == len(capabilities), "Price sort lost capabilities with no offered price."
    page.locator("#sort").select_option("name")

    checkboxes = page.locator("#cards input[type='checkbox']")
    checkboxes.nth(0).check()
    expect(page.locator("#compare-content .compare-item")).to_have_count(1)
    checkboxes.nth(1).check()
    expect(page.locator("#compare-content .compare-item")).to_have_count(2)
    expect(page.locator("#comparison")).to_contain_text("No cross-task score is assigned")
    expect(page.locator("#compare-content")).to_contain_text("Cryptographic authenticity")
    expect(page.locator("#compare-content")).to_contain_text("Missing evidence")
    expect(page.locator("#compare-content")).to_contain_text("Limitations")
    page.locator("#clear-compare").click()
    expect(page.locator("#comparison")).to_be_hidden()
    assert not any(box.is_checked() for box in checkboxes.all())

    improved = next(capability for capability in capabilities if capability["lineage"])
    improved_card = page.locator(f"#cards .card[data-id='{improved['id']}']").filter(has_text=f"v{improved['version']}")
    expect(improved_card).to_have_count(1)
    improved_card.locator("[data-action='details']").click()
    detail = page.locator("#detail-content")
    expect(page.locator("#detail-dialog")).to_be_visible()
    expect(page.locator("#close-detail")).to_be_focused()
    expect(detail).to_contain_text("SYNTHETIC EXAMPLE")
    for text in ("Provenance and usage terms", "Known limitations", "Evaluations: outcomes, failures and context", "Missing evidence", "Improvement and attribution history", "does not create legal ownership"):
        expect(detail).to_contain_text(text)
    for limitation in improved["limitations"]:
        expect(detail).to_contain_text(limitation)
    evaluations = [row for row in synthetic["evaluations"] if row["capability_id"] == improved["id"] and row["capability_version"] == improved["version"]]
    assert evaluations, "Improvement needs an inspectable independent evaluation example."
    for evaluation in evaluations:
        assert evaluation["evaluator_id"].lower() != improved["contributor_id"].lower()
        assert evaluation["independence"] == "SEPARATE_REVIEWED_CONTRIBUTOR"
        expect(detail).to_contain_text(evaluation["method"])
        expect(detail).to_contain_text(evaluation["environment"])
        expect(detail).to_contain_text("Outcome verification: SYNTHETIC")
        for failure in evaluation["failures"]:
            expect(detail).to_contain_text(failure)
        for limitation in evaluation["limitations"]:
            expect(detail).to_contain_text(limitation)
        expect(detail).to_contain_text(evaluation["sample"]["dataset"])
        expect(detail).to_contain_text(evaluation["sample"]["selection"])
        expect(detail).to_contain_text(evaluation["conflicts"])
        original_url = urljoin(page.url, f"synthetic/v1/{evaluation['record_url']}")
        assert is_loopback(original_url)
        original = page.context.request.get(original_url)
        assert original.ok, "Original evaluation JSON is not published beside the catalog."
        assert hashlib.sha256(original.body()).hexdigest() == evaluation["record_sha256"], "Published evaluation no longer matches its provenance hash."
        assert original.json()["format"] == "openline.evaluation.v1"
    original_capability_url = urljoin(page.url, f"synthetic/v1/{improved['record_url']}")
    assert is_loopback(original_capability_url)
    original_capability = page.context.request.get(original_capability_url)
    assert original_capability.ok
    assert hashlib.sha256(original_capability.body()).hexdigest() == improved["record_sha256"]
    assert original_capability.json()["format"] == "openline.capability.v1"
    expect(detail.get_by_role("link", name="Inspect original capability JSON")).to_be_visible()
    expect(detail.get_by_role("link", name="Inspect original evaluation JSON")).to_be_visible()
    assert any(row["sample"]["failed"] for row in synthetic["evaluations"]), "Failure evidence must remain visible in the walkthrough."
    expect(detail).to_contain_text(improved["lineage"][0]["record_sha256"])
    snapshot(page, screenshots, "beta-synthetic-detail-desktop.png")
    page.get_by_role("button", name="Inspect earlier version").click()
    ancestor = improved["lineage"][0]
    expect(detail.locator("p.byline")).to_contain_text(f"version {ancestor['version']}")
    ancestor_evaluations = [row for row in synthetic["evaluations"] if row["capability_id"] == ancestor["capability_id"] and row["capability_version"] == ancestor["version"]]
    assert any(row["sample"]["failed"] for row in ancestor_evaluations), "Earlier failures should remain in the immutable history."
    for evaluation in ancestor_evaluations:
        for failure in evaluation["failures"]:
            expect(detail).to_contain_text(failure)
    detail.locator(".evaluation").first.scroll_into_view_if_needed()
    snapshot(page, screenshots, "beta-synthetic-detail-outcomes-desktop.png")
    page.keyboard.press("Escape")
    expect(page.locator("#detail-dialog")).not_to_be_visible()

    # The sample inquiry is a local download, never a real issue draft.
    improved_card.locator("[data-action='details']").click()
    detail.locator("[data-action='inquiry']").click()
    expect(page.locator("#inquiry-dialog")).to_be_visible()
    assert "SYNTHETIC SAMPLE" in page.locator("#inquiry-body").input_value()
    expect(page.locator("#inquiry-action a[href^='https:']")).to_have_count(0)
    with page.expect_download() as info:
        page.get_by_role("button", name="Download synthetic sample draft").click()
    download = info.value
    assert download.suggested_filename == "synthetic-work-inquiry.txt"
    path = download.path()
    assert path and "SYNTHETIC SAMPLE" in Path(path).read_text(encoding="utf-8")
    page.keyboard.press("Escape")

    # Prices are asking prices with comparable currency and basis. Synthetic
    # evidence can create an inspectable shortlist but cannot justify a purchase.
    priced = [capability for capability in capabilities if capability["price"]]
    supported_currency = set(page.locator("#currency option").evaluate_all("options => options.map(option => option.value)"))
    candidate = next(capability for capability in priced if capability["price"]["currency"] in supported_currency and any(evaluation["capability_id"] == capability["id"] and evaluation["capability_version"] == capability["version"] and evaluation["independence"] == "SEPARATE_REVIEWED_CONTRIBUTOR" for evaluation in synthetic["evaluations"]))
    selected_task = next(evaluation["task"] for evaluation in synthetic["evaluations"] if evaluation["capability_id"] == candidate["id"] and evaluation["capability_version"] == candidate["version"] and evaluation["independence"] == "SEPARATE_REVIEWED_CONTRIBUTOR")
    price = candidate["price"]
    comparable = [capability for capability in priced if selected_task in capability["tasks"] and capability["price"]["currency"] == price["currency"] and capability["price"]["basis"] == price["basis"]]
    cheapest = min(comparable, key=lambda capability: (float(capability["price"]["amount"]), capability["id"]))
    page.locator("#select-task").select_option(selected_task)
    page.locator("#price-basis").select_option(price["basis"])
    page.locator("#currency").select_option(price["currency"])
    page.locator("#budget").fill(str(max(float(capability["price"]["amount"]) for capability in comparable)))
    page.locator("#deadline").fill("2030-01-15")
    page.locator("#brief").fill("Synthetic walkthrough only: summarize a generic public text and document acceptance criteria.")
    page.locator("#select-form button[type='submit']").click()
    result = page.locator("#select-result")
    expect(result).to_be_visible()
    expect(result).to_contain_text("Synthetic evidence shortlist")
    expect(result).to_contain_text(f"Ordinary cheapest-offer baseline: {cheapest['name']}")
    expect(result).to_contain_text("No real outcome or economic benefit has been demonstrated")
    expect(result).to_contain_text("No availability or delivery commitment has been verified")
    expect(result).to_contain_text("No automatic award, execution, purchase, payment")
    assert result.locator(".card").count() >= 1
    snapshot(page, screenshots, "beta-synthetic-select-desktop.png")
    page.locator("#min-evaluations").select_option("2")
    page.locator("#select-form button[type='submit']").click()
    expect(result).to_contain_text("No candidate meets the independent evaluation requirement")
    expect(result.locator(".card")).to_have_count(0)
    page.locator("#budget").fill("0")
    page.locator("#select-form button[type='submit']").click()
    expect(result).to_contain_text("No offered price matches")
    expect(result).to_contain_text("baseline: unavailable")

    page.locator("#synthetic-toggle").uncheck()
    expect(page.locator("#cards .card")).to_have_count(0)
    expect(page.locator("#empty")).to_be_visible()
    expect(page.locator("#comparison")).to_be_hidden()
    expect(page.locator("#synthetic-notice")).to_be_hidden()
    expect(page.locator("#select-result")).to_be_hidden()


def exercise_injected_security_and_inquiry(context, base_url: str) -> None:
    # This intentionally emulates the compiled reviewed-contact shape so the
    # genuine inquiry path is exercised. It is synthetic test input intercepted
    # in one local browser page only: never a file, listing, screenshot, or claim
    # of a real public contribution or review.
    record = {
        "id": "synthetic-browser-test-only",
        "synthetic": False,
        "version": "1.0.0",
        "name": "Synthetic browser test fixture — not a real service",
        "contributor_id": "synthetic-browser-test-author",
        "summary": "Synthetic test input, held only in a local intercepted response.",
        "tasks": ["test-only-json-validation"],
        "price": {"amount": 12, "currency": "USD", "basis": "job"},
        "evidence_summary": {
            "label": "SELF_REPORTED", "independent_evaluation_count": 0,
            "cryptographic_authenticity": "UNKNOWN",
            "missing": ["Synthetic test fixture; no real evidence or review."],
        },
        "publication": {
            "reviewed": True,
            "identity_basis": "SYNTHETIC BROWSER TEST ONLY; no real publication",
        },
        "inquiry": {
            "accepts_inquiries": True,
            "url": "https://github.com/terryncew/openline-bureau/issues/new",
        },
        "provenance": {"source_url": "https://github.com/terryncew/openline-bureau", "authors": ["Synthetic test author"]},
        "usage_terms": {"license": "TEST-ONLY", "summary": "Synthetic test input; unavailable."},
        "limitations": ["Not a real capability."],
        "lineage": [], "record_sha256": "0" * 64,
        "record_url": "submissions/capabilities/synthetic-browser-test-only.json",
    }
    payload = {
        "format": "openline.catalog.v1", "synthetic": False,
        "policy": {"inquiries_enabled": True, "payment_processing": False, "contributed_code_execution": False},
        "capabilities": [record], "workers": [], "evaluations": [],
    }
    page = context.new_page()

    def inject_catalog(route):
        assert is_loopback(route.request.url), "Test interception must remain local."
        route.fulfill(status=200, content_type="application/json", body=json.dumps(payload))

    page.route("**/beta/catalog/v1/index.json", inject_catalog)
    page.goto(urljoin(base_url, "beta/"), wait_until="networkidle")
    expect(page.locator("#cards .card")).to_have_count(1)
    page.locator("#cards [data-action='details']").click()
    expect(page.locator("#close-detail")).to_be_focused()
    page.keyboard.press("Escape")
    expect(page.locator("#detail-dialog")).not_to_be_visible()
    page.locator("#cards [data-action='details']").click()
    page.locator("#detail-content [data-action='inquiry']").click()
    expect(page.locator("#inquiry-dialog")).to_be_visible()
    expect(page.locator("#inquiry-dialog")).to_contain_text("GitHub issues are public")
    expect(page.locator("#inquiry-dialog")).to_contain_text("This is not a purchase or payment")
    initial_body = page.locator("#inquiry-body").input_value()
    assert "no real" in initial_body.lower() or "Synthetic browser test fixture" in initial_body
    draft = "Synthetic local test only: compare JSON & CSV? # evidence / no customer data."
    page.locator("#inquiry-body").fill(draft)
    inquiry = page.locator("#inquiry-link")
    expect(inquiry).to_be_visible()
    href = inquiry.get_attribute("href")
    parsed = urlsplit(href)
    assert parsed.scheme == "https" and parsed.netloc == "github.com"
    assert parsed.path == "/terryncew/openline-bureau/issues/new"
    params = parse_qs(parsed.query)
    assert params.get("body") == [draft], "Inquiry query did not preserve the edited public draft."
    assert params.get("title") == [f"Work inquiry: {record['name']}"]
    assert "%26" in href and "%23" in href, "Inquiry parameters are not encoded safely."
    assert inquiry.get_attribute("target") == "_blank"
    assert "noopener" in (inquiry.get_attribute("rel") or "")
    # Deliberately never click the real GitHub link or send any inquiry.
    page.keyboard.press("Escape")
    expect(page.locator("#inquiry-dialog")).not_to_be_visible()

    payload["policy"]["inquiries_enabled"] = False
    page.reload(wait_until="networkidle")
    expect(page.locator("#load-error")).to_contain_text("Catalog inquiry policy is disabled")
    expect(page.locator("#cards .card")).to_have_count(0)
    record["inquiry"]["accepts_inquiries"] = False
    page.reload(wait_until="networkidle")
    page.locator("#cards [data-action='details']").click()
    expect(page.locator("#detail-content [data-action='inquiry']")).to_have_count(0)
    page.keyboard.press("Escape")
    payload["policy"]["inquiries_enabled"] = True
    record["inquiry"]["accepts_inquiries"] = True

    # A worker's execution report remains specific to that worker and exact
    # capability version. It cannot satisfy Select's generic skill evaluation
    # requirement or become a claim about any other worker.
    worker = {
        "id": "synthetic-browser-worker-only", "synthetic": False,
        "name": "Synthetic browser worker fixture — not a real worker",
        "contributor_id": "synthetic-browser-worker-author",
        "summary": "Synthetic, local-only worker evidence scope test.",
        "capability_ids": [record["id"]], "record_sha256": "1" * 64,
        "record_url": "submissions/workers/synthetic-browser-worker-only.json",
        "publication": {"reviewed": True, "identity_basis": "SYNTHETIC TEST ONLY"},
        "inquiry": {"accepts_inquiries": False, "url": "https://github.com/terryncew/openline-bureau/issues/new"},
        "provenance": {"source_url": "https://github.com/terryncew/openline-bureau", "authors": ["Synthetic test author"]},
        "limitations": ["Synthetic fixture, never a real worker."],
        "evidence_summary": {"independent_evaluation_count": 1, "missing": ["Synthetic test evidence only."]},
    }
    evaluation = {
        "id": "synthetic-browser-worker-evaluation", "synthetic": False,
        "publication": {"reviewed": True, "identity_basis": "SYNTHETIC TEST ONLY"},
        "capability_id": record["id"], "capability_version": record["version"],
        "worker_id": worker["id"], "scope": "WORKER_EXECUTION",
        "evaluator_id": "synthetic-browser-independent-evaluator",
        "task": record["tasks"][0], "method": "Synthetic local-only scope test.",
        "environment": "Synthetic browser-only input; no actual outcome execution.",
        "sample": {"total": 3, "passed": 2, "failed": 1, "inconclusive": 0, "dataset": "Synthetic cases", "selection": "Synthetic fixture only"},
        "failures": ["Synthetic case failure; not a real reported outcome."],
        "limitations": ["Specific to this synthetic worker test shape."],
        "conflicts": "Synthetic test only", "independence_limit": "Synthetic test only",
        "independence": "SEPARATE_REVIEWED_CONTRIBUTOR",
        "outcome_verification": "EVALUATOR_REPORTED",
        "evidence": [], "results": [], "record_sha256": "2" * 64,
        "record_url": "submissions/evaluations/synthetic-browser-worker-evaluation.json",
    }
    payload["workers"] = [worker]
    payload["evaluations"] = [evaluation]
    page.reload(wait_until="networkidle")
    page.locator("#select-task").select_option(record["tasks"][0])
    page.locator("#price-basis").select_option("job")
    page.locator("#currency").select_option("USD")
    page.locator("#budget").fill("20")
    page.locator("#select-form button[type='submit']").click()
    expect(page.locator("#select-result")).to_contain_text("No candidate meets the independent evaluation requirement")
    expect(page.locator("#select-result .card")).to_have_count(0)
    page.locator("#type-filter").select_option("workers")
    page.locator("#cards [data-action='worker-details']").click()
    expect(page.locator("#detail-content")).to_contain_text("2/3 passed")
    expect(page.locator("#detail-content")).to_contain_text("EVALUATOR_REPORTED")
    expect(page.locator("#detail-content")).to_contain_text(evaluation["failures"][0])
    page.keyboard.press("Escape")
    page.locator("#type-filter").select_option("capabilities")
    page.locator("#cards [data-action='details']").click()
    expect(page.locator("#detail-content")).to_contain_text("No task outcome evaluation documented")
    skill_count = page.locator("#detail-content dt", has_text="Separate contributor evaluations").locator("xpath=following-sibling::dd[1]")
    expect(skill_count).to_have_text("0")
    expect(page.locator("#detail-content")).to_contain_text("Scope: WORKER_EXECUTION")
    expect(page.locator("#detail-content")).to_contain_text("it is not generic skill reliability")
    page.keyboard.press("Escape")
    payload["workers"] = []
    payload["evaluations"] = []

    # Contributed strings must remain text, and disallowed/credential-bearing
    # URLs must never become clickable or expose credential strings.
    attack = '<img src="https://example.invalid/x" onerror="window.__xssProof=1">'
    record["name"] = attack
    record["summary"] = '<script>window.__xssProof=1</script>'
    record["provenance"]["source_url"] = "https://testuser:testsecret@github.com/terryncew/openline-bureau"
    record["publication"]["source_pr_url"] = "javascript:window.__xssProof=1"
    record["inquiry"]["url"] = "https://example.invalid/issues/new"
    record["limitations"] = [attack]
    page.reload(wait_until="networkidle")
    expect(page.locator("#cards h3")).to_have_text(attack)
    expect(page.locator("#cards img, #cards script")).to_have_count(0)
    page.locator("#cards [data-action='details']").click()
    expect(page.locator("#detail-title")).to_have_text(attack)
    expect(page.locator("#detail-content img, #detail-content script")).to_have_count(0)
    expect(page.locator("#detail-content [data-action='inquiry']")).to_have_count(0)
    expect(page.locator("a[href^='javascript:'], a[href*='testsecret'], a[href*='example.invalid']")).to_have_count(0)
    assert page.evaluate("window.__xssProof === undefined"), "Contributed HTML executed."
    assert "testsecret" not in page.locator("#detail-content").inner_text(), "Rejected URL exposed a credential string."
    page.keyboard.press("Escape")

    # A forged synthetic-to-real label cannot bypass the mode boundary.
    record["evidence_summary"]["label"] = "SYNTHETIC"
    page.reload(wait_until="networkidle")
    expect(page.locator("#load-error")).to_be_visible()
    expect(page.locator("#load-error")).to_contain_text("Synthetic records cannot appear")
    expect(page.locator("#cards .card")).to_have_count(0)
    record["evidence_summary"]["label"] = "SELF_REPORTED"
    record["synthetic"] = True
    page.reload(wait_until="networkidle")
    expect(page.locator("#load-error")).to_contain_text("crosses the synthetic boundary")
    expect(page.locator("#cards .card")).to_have_count(0)
    page.close()


def exercise_mobile(context, base_url: str, screenshots: Path | None) -> None:
    page = context.new_page()
    page.set_viewport_size({"width": 390, "height": 844})
    page.goto(urljoin(base_url, "beta/"), wait_until="networkidle")
    page.locator("#synthetic-toggle").check()
    expect(page.locator("#synthetic-notice")).to_be_visible()
    expect(page.locator("#cards .card").first).to_be_visible()
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth"), "Mobile page overflows horizontally."
    snapshot(page, screenshots, "beta-synthetic-mobile.png")
    page.locator("#cards [data-action='details']").first.click()
    expect(page.locator("#detail-dialog")).to_be_visible()
    dialog_box = page.locator("#detail-dialog").bounding_box()
    assert dialog_box and dialog_box["x"] >= 0 and dialog_box["x"] + dialog_box["width"] <= 390, "Mobile evidence dialog overflows."
    page.keyboard.press("Escape")
    expect(page.locator("#detail-dialog")).not_to_be_visible()
    page.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", help="Existing loopback server; defaults to an ephemeral docs server.")
    parser.add_argument("--chromium", default="/usr/bin/chromium", help="Installed Chromium executable.")
    parser.add_argument("--screenshots-dir", type=Path, help="Capture synthetic-only review screenshots.")
    args = parser.parse_args()
    if args.base_url:
        run_browser(args.base_url, args.chromium, args.screenshots_dir)
    else:
        with local_server() as base_url:
            run_browser(base_url, args.chromium, args.screenshots_dir)


if __name__ == "__main__":
    main()
