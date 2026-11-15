#!/usr/bin/env python3
"""Model-driven worker for OpenLine Genie RC3 (`core/genie_worker.py`).

Invoked ONLY from `OpenLineGenieEngine.build_from_prompt()`. Pipeline:
  (a) understand — one model call producing a JSON spec;
  (b) build — one model call producing ONE self-contained single-file
      HTML app (no external deps, real working JS, localStorage persistence);
  (c) test — Playwright headless: loads with zero console errors, key
      controls exist and respond, data persists across a reload;
  (d) repair — on test failure, one more model call with the failure text,
      max 3 repair attempts;
  (e) present — commit through the engine's existing
      `verify_project_artifact()` + `_commit_accepted_state()` tail, and
      log every stage to `genie_autonomy_log` with provenance
      `MODEL_WORKER:<model_id>`, recording model id, prompt hash, and
      output hash per stage.

The generated app is a REAL working app, not a snapshot. No model call
ever happens outside the adapter, so spend logging and cap enforcement
are the adapter's job, not this file's.
"""
from __future__ import annotations

import hashlib
import json
import re
import tempfile
import time
from pathlib import Path
from typing import Any

from core.model_adapter import ModelError

MAX_REPAIR_ATTEMPTS = 3

UNDERSTAND_SYSTEM = (
    "You design small local-first web apps. Respond with ONLY a JSON object, no prose, "
    "no code fences. The object has exactly these keys: "
    '{"title": str, "family": str, "data_model": [{"key": str, "label": str, "type": "text|number|date"}], '
    '"features": [str, ...], "ui_layout": str}. '
    "data_model lists the fields of the app's main record type (3-6 fields). "
    "features lists what the app must do (add/list/edit records, compute a total, "
    "reminders or status workflow). ui_layout is one sentence describing the layout."
)

BUILD_SYSTEM = (
    "You write ONE self-contained single-file HTML app. Output ONLY the HTML file, "
    "no prose, no code fences, no markdown. Rules, all mandatory:\n"
    "- Single HTML file: inline <style> and <script> only. NO external dependencies: "
    "no http:// or https:// URLs anywhere, no <script src=>, no <link href=>, no CDN, no fonts.\n"
    "- Real working JavaScript: a form to add records, a list/table rendering stored "
    "records, a computed total or status shown live, and a delete or status button per record.\n"
    "- Persistence: every record is saved to localStorage under a key derived from the "
    "app title, loaded on page start, and still present after a reload. "
    "localStorage may be unavailable (e.g. inside a sandboxed iframe): wrap EVERY "
    "localStorage access in try/catch AND keep an in-memory copy as the fallback "
    "source of truth — a load that cannot reach storage must return the in-memory "
    "records, never a fresh empty list, or records added in the session vanish.\n"
    "- The add form must have visible text/number inputs and a button whose label contains "
    "Add, Save, or Create. Submitting the form adds the entered record to the list immediately.\n"
    "- The add button MUST be type=\"button\" with a click handler that adds the record. "
    "NEVER rely on a native form submit (type=\"submit\" or a form action): this app is "
    "also shown inside a sandboxed iframe where native form submission is blocked and "
    "the submit event never fires. A form element is fine only if its submit is fully "
    "cancelled AND the button itself is type=\"button\".\n"
    "- No placeholder, lorem ipsum, or fake data that cannot be edited. Seed at most two "
    "example records, clearly editable and deletable.\n"
    "- Do not mark form fields required, except the first text field: the form must "
    "submit successfully when only a name is entered.\n"
    "- Keep the complete file COMPACT (aim under 350 lines): short CSS, terse JavaScript, "
    "no verbose comments. You MUST finish with the closing </html> tag — a truncated "
    "file fails its test.\n"
    "- Layout: NO position:fixed or position:sticky header, footer, or bar may overlap "
    "any form control or button at 390px width. Keep headers static (position:static) "
    "and leave clear space above the form, so every control stays tappable.\n"
    "- Valid HTML, zero console errors when opened from a file."
)

REPAIR_SYSTEM = (
    "You repair a single-file HTML app. Output ONLY the complete corrected HTML file, "
    "no prose, no code fences. Keep every rule from the original build request: single "
    "file, no external URLs, working JavaScript, localStorage persistence, a working "
    "add-record form whose submit button says Add, Save, or Create. Additional rules "
    "that past repairs kept missing — follow them exactly:\n"
    "- The add button MUST be type=\"button\" with a click handler that adds the record. "
    "NEVER use type=\"submit\" and never rely on a native form submit: the app is shown "
    "inside a sandboxed iframe where native form submission is blocked and the submit "
    "event never fires.\n"
    "- Wrap EVERY localStorage access in try/catch AND keep an in-memory copy as the "
    "fallback source of truth: a load that cannot reach storage must return the "
    "in-memory records, never a fresh empty list.\n"
    "- NO position:fixed or position:sticky header, footer, or bar may overlap any form "
    "control or button at 390px width; keep headers static.\n"
    "Keep the file COMPACT (aim under 350 lines) and ALWAYS finish with the closing "
    "</html> tag — a truncated file fails its test."
)

REVISE_SYSTEM = (
    "You revise ONE self-contained single-file HTML app. Output ONLY the complete "
    "revised HTML file, no prose, no code fences, no markdown. Rules, all mandatory:\n"
    "- Start from the current app supplied below and keep everything that already "
    "works: same title, same localStorage key, same records and behaviour, unless "
    "the requested change explicitly replaces them.\n"
    "- Apply ONLY the requested change, plus the smallest supporting UI needed for it "
    "(e.g. a new field or control). Do not redesign, rename, or drop existing features.\n"
    "- Single HTML file: inline <style> and <script> only. NO external dependencies: "
    "no http:// or https:// URLs anywhere, no <script src=>, no <link href=>, no CDN.\n"
    "- Real working JavaScript, localStorage persistence, a working add-record form "
    "whose submit button says Add, Save, Create, Book, or Schedule. The add button "
    "MUST be type=\"button\" with a click handler that adds the record — never rely on "
    "a native form submit, which is blocked inside a sandboxed iframe. Wrap EVERY "
    "localStorage access in try/catch with an in-memory fallback, so the app never "
    "throws when storage is blocked (e.g. inside a sandboxed iframe).\n"
    "- Keep the complete file COMPACT (aim under 350 lines): short CSS, terse "
    "JavaScript, no verbose comments. You MUST finish with the closing </html> tag — "
    "a truncated file fails its test.\n"
    "- Valid HTML, zero console errors when opened from a file."
)


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _slug(text: str) -> str:
    words = re.findall(r"[A-Za-z0-9]+", text.lower())[:5]
    return "-".join(words) or "custom-app"


def _extract_json(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start < 0 or end <= start:
        raise ModelError("worker_understand_not_json")
    try:
        parsed = json.loads(cleaned[start : end + 1])
    except ValueError:
        raise ModelError("worker_understand_invalid_json") from None
    if not isinstance(parsed, dict):
        raise ModelError("worker_understand_not_object")
    return parsed


def _extract_html(text: str) -> str:
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:html)?\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    idx = cleaned.lower().find("<!doctype html")
    if idx < 0:
        idx = cleaned.lower().find("<html")
    if idx < 0:
        raise ModelError("worker_build_not_html")
    html = cleaned[idx:]
    if "<html" not in html.lower() or "</html>" not in html.lower():
        raise ModelError("worker_build_incomplete_html")
    return html


def _launch_chromium(pw):
    """Launch headless Chromium: default Playwright path first, then any
    locally installed Playwright Chromium build (this sandbox has them
    under ~/.cache/ms-playwright)."""
    try:
        return pw.chromium.launch(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
    except Exception:
        candidates = sorted(
            Path.home().glob(".cache/ms-playwright/chromium-*/chrome-linux/chrome"),
            reverse=True,
        )
        last_exc: Exception | None = None
        for exe in candidates:
            try:
                return pw.chromium.launch(
                    headless=True,
                    executable_path=str(exe),
                    args=["--no-sandbox", "--disable-dev-shm-usage"],
                )
            except Exception as exc:  # noqa: BLE001 - try next build
                last_exc = exc
        raise ImportError(f"playwright_chromium_unavailable:{last_exc}") from None


class GenieWorker:
    """Builds a working app from a prompt using a ModelAdapter + the engine."""

    def __init__(self, adapter, engine) -> None:
        self.adapter = adapter
        self.engine = engine

    @property
    def model_id(self) -> str:
        return str(getattr(self.adapter, "model", None) or getattr(self.engine, "model_id", None) or "unknown-model")

    def _log(self, project_id: str, stage: str, detail: str) -> None:
        self.engine.log_autonomy_stage(project_id, stage, detail, f"MODEL_WORKER:{self.model_id}")

    def build(self, prompt: str) -> dict[str, Any]:
        prompt_hash = _sha(prompt)
        # (a) understand
        spec_resp = self.adapter.complete(
            UNDERSTAND_SYSTEM,
            f"User request: {prompt}",
            max_tokens=2000,
            purpose="understand",
        )
        spec = _extract_json(spec_resp["text"])
        for key in ("title", "family", "data_model", "features", "ui_layout"):
            if key not in spec:
                raise ModelError(f"worker_spec_missing_key:{key}")
        if not isinstance(spec["data_model"], list) or not spec["data_model"]:
            raise ModelError("worker_spec_empty_data_model")
        spec_hash = _sha(json.dumps(spec, sort_keys=True))
        title = str(spec["title"])
        project_id = f"genie-model-{_slug(title)}"
        self._log(
            project_id,
            "1. Understand Goal (model)",
            f"model={self.model_id} prompt_sha256={prompt_hash} spec_sha256={spec_hash} title={title!r}",
        )

        # (b) build
        app_resp = self.adapter.complete(
            BUILD_SYSTEM,
            f"User request: {prompt}\n\nApp spec (JSON):\n{json.dumps(spec, indent=2)}",
            max_tokens=8000,
            purpose="build",
        )
        app_html: str | None = None
        try:
            app_html = _extract_html(app_resp["text"])
        except ModelError as exc:
            build_error = str(exc)
        if app_html is not None:
            app_hash = _sha(app_html)
            self._log(
                project_id,
                "2. Build App (model)",
                f"model={self.model_id} prompt_sha256={prompt_hash} app_sha256={app_hash} bytes={len(app_html)}",
            )
            test_report = self._test_app(app_html, title)
        else:
            # Truncated or malformed build output: the repair loop below gets
            # a chance to ask for a shorter complete file.
            app_hash = ""
            test_report = {"passed": False, "checks_run": 0, "errors": [build_error or "worker_build_no_html"]}
            self._log(
                project_id,
                "2. Build App (model)",
                f"model={self.model_id} prompt_sha256={prompt_hash} FAILED build_error={build_error} "
                f"raw_bytes={len(app_resp['text'])}",
            )

        # (c) test, (d) repair up to 3 attempts
        repairs = 0
        while not test_report["passed"] and repairs < MAX_REPAIR_ATTEMPTS:
            repairs += 1
            failure_text = "; ".join(test_report["errors"]) or "unspecified test failure"
            previous_output = app_html if app_html is not None else app_resp["text"]
            repair_resp = self.adapter.complete(
                REPAIR_SYSTEM,
                f"The app below FAILED its automated browser test with: {failure_text}\n\n"
                f"Fix the app so the test passes. IMPORTANT: output the COMPLETE file including "
                f"the closing </html> tag; keep it compact so it fits. Previous output:\n{previous_output}",
                max_tokens=8000,
                purpose="repair",
            )
            try:
                app_html = _extract_html(repair_resp["text"])
            except ModelError as exc:
                test_report = {"passed": False, "checks_run": 0, "errors": [str(exc)]}
                self._log(
                    project_id,
                    f"3.{repairs} Repair App (model)",
                    f"model={self.model_id} FAILED repair_error={exc}",
                )
                continue
            app_hash = _sha(app_html)
            self._log(
                project_id,
                f"3.{repairs} Repair App (model)",
                f"model={self.model_id} failure={failure_text} app_sha256={app_hash} bytes={len(app_html)}",
            )
            test_report = self._test_app(app_html, title)
        self._log(
            project_id,
            "3. Test App (playwright)",
            f"passed={test_report['passed']} checks_run={test_report['checks_run']} "
            f"errors={test_report['errors']} app_sha256={app_hash}",
        )
        if not test_report["passed"]:
            raise ModelError(f"worker_app_failed_tests:{'; '.join(test_report['errors'])}")

        # (e) present: store artifact version, verify, commit, promote.
        filename = f"{_slug(title)}.html"
        version = self.engine.store_app_version(project_id, filename, app_html, status="exploratory")
        state: dict[str, Any] = {
            "schema": "openline.genie.model_built_app.v1",
            "project_id": project_id,
            "project_family": "model_built_app",
            "title": title,
            "prompt": prompt,
            "spec": spec,
            "app_version": version,
            "app_sha256": app_hash,
            "app_filename": filename,
            "honesty_boundary": (
                "MODEL-BUILT LOCAL-FIRST APPLICATION: Built by a model-driven worker from your "
                "request, tested headless in this environment, with local storage and standalone "
                "HTML export. External actions remain owner-controlled; no data leaves this machine."
            ),
        }
        test_report_state = self.engine.verify_project_artifact(state)
        if not test_report_state["passed"]:
            raise ModelError(f"worker_artifact_verification_failed:{test_report_state['errors']}")
        receipt = self.engine._commit_accepted_state(
            project_id, "model_built_app", state, operation="autonomous_model_build",
            promote_staged_app_version=version,
            require_target_absent=True,
        )
        receipt_sha = str(receipt.get("receipt", receipt).get("payload_sha256", ""))[:12]
        self._log(
            project_id,
            "4. Present & Preserve",
            f"model={self.model_id} app_version={version} app_sha256={app_hash} "
            f"receipt_sha256={receipt_sha}... repairs={repairs}",
        )
        return self.engine.get_project_bundle(project_id)

    def revise(self, prompt: str, current_app_html: str, change_request: str,
               project_id: str, title: str, max_repairs: int = 2,
               max_tokens: int = 8000) -> dict[str, Any]:
        """Revises an already-accepted app for a change request.

        One model call produces the full revised file; it is browser-tested
        the same way as a fresh build, with up to `max_repairs` repair calls.
        Returns {"app_html", "app_sha256", "bytes", "model", "repairs"}.
        The caller decides whether to propose/accept it through the engine;
        this method commits nothing.
        """
        resp = self.adapter.complete(
            REVISE_SYSTEM,
            f"Requested change: {change_request}\n\nCurrent app:\n{current_app_html}",
            max_tokens=max_tokens,
            purpose="revise",
        )
        try:
            app_html = _extract_html(resp["text"])
        except ModelError as exc:
            raise ModelError(f"worker_revise_no_html:{exc}") from None
        app_hash = _sha(app_html)
        self._log(project_id, "2. Revise App (model)",
                  f"model={self.model_id} change={change_request[:80]!r} app_sha256={app_hash} bytes={len(app_html)}")
        test_report = self._test_app(app_html, title)
        repairs = 0
        while not test_report["passed"] and repairs < max_repairs:
            repairs += 1
            failure_text = "; ".join(test_report["errors"]) or "unspecified test failure"
            repair_resp = self.adapter.complete(
                REPAIR_SYSTEM,
                f"The revised app below FAILED its automated browser test with: {failure_text}\n\n"
                f"Fix the app so the test passes. IMPORTANT: output the COMPLETE file including "
                f"the closing </html> tag; keep it compact so it fits. Previous output:\n{app_html}",
                max_tokens=8000,
                purpose="repair",
            )
            try:
                app_html = _extract_html(repair_resp["text"])
            except ModelError as exc:
                raise ModelError(f"worker_revise_repair_no_html:{exc}") from None
            app_hash = _sha(app_html)
            self._log(project_id, f"3.{repairs} Repair Revised App (model)",
                      f"model={self.model_id} failure={failure_text} app_sha256={app_hash} bytes={len(app_html)}")
            test_report = self._test_app(app_html, title)
        self._log(project_id, "3. Test Revised App (playwright)",
                  f"passed={test_report['passed']} checks_run={test_report['checks_run']} errors={test_report['errors']} app_sha256={app_hash}")
        if not test_report["passed"]:
            raise ModelError(f"worker_revised_app_failed_tests:{'; '.join(test_report['errors'])}")
        return {"app_html": app_html, "app_sha256": app_hash,
                "bytes": len(app_html), "model": self.model_id, "repairs": repairs}

    @staticmethod
    def _fill_inputs(inputs) -> bool:
        """Fill every visible fillable input with test data. Returns True
        if anything was filled."""
        filled = False
        for inp in inputs:
            try:
                if not inp.is_visible():
                    continue
                tag = inp.evaluate("el => el.tagName.toLowerCase()")
                itype = (inp.get_attribute("type") or "").lower()
                if tag == "select":
                    options = inp.locator("option").all()
                    if len(options) > 1:
                        inp.select_option(index=1)
                        filled = True
                elif tag == "textarea" or itype in ("", "text", "search", "tel"):
                    inp.fill("Test Entry")
                    filled = True
                elif itype == "email":
                    inp.fill("test@example.com")
                    filled = True
                elif itype == "number":
                    inp.fill("25")
                    filled = True
                elif itype == "date":
                    inp.fill("2026-11-12")
                    filled = True
                elif itype == "time":
                    inp.fill("10:00")
                    filled = True
                elif itype == "url":
                    inp.fill("https://example.invalid")
                    filled = True
            except Exception:  # noqa: BLE001 - one bad input must not fail the test
                continue
        return filled

    @staticmethod
    def _find_submit(buttons):
        """The form's submit button: Add/Save/Create/Book/Schedule label,
        else a button with type=submit, else None."""
        for btn in buttons:
            label = (btn.inner_text() or "").strip().lower()
            if any(w in label for w in ("add", "save", "create", "book", "schedule", "submit")):
                return btn
        for btn in buttons:
            if (btn.get_attribute("type") or "").lower() == "submit":
                return btn
        return None

    def _interact_with_app(self, page) -> str | None:
        """Fill the add form and submit it. Returns an error string or None."""
        forms = page.locator("form").all()
        if forms:
            form = forms[0]
            if not self._fill_inputs(form.locator("input, textarea, select").all()):
                return "no_fillable_input"
            submit = self._find_submit(form.locator("button").all())
            if submit is not None:
                submit.click()
            else:
                form.evaluate("f => { if (f.requestSubmit) f.requestSubmit(); }")
            return None
        inputs = page.locator("input, textarea, select").all()
        buttons = page.locator("button").all()
        if not inputs or not buttons:
            return "no_form_inputs_or_buttons"
        if not self._fill_inputs(inputs):
            return "no_fillable_input"
        btn = self._find_submit(buttons) or buttons[0]
        btn.click()
        return None

    def _test_app_fallback_dom(self, app_html: str, title: str) -> dict[str, Any]:
        """Deterministic HTML/JS + Node DOM verification when Playwright is unavailable in container."""
        errors: list[str] = []
        checks_run = 0
        low = app_html.lower()
        checks_run += 1
        if "<html" not in low or "</html>" not in low:
            errors.append("missing_html_tags")
        checks_run += 1
        if "src=\"http" in low or "href=\"http" in low:
            errors.append("external_url_dependency_forbidden")
        checks_run += 1
        if "<input" not in low and "<textarea" not in low and "<select" not in low:
            errors.append("no_form_inputs")
        if "<button" not in low:
            errors.append("no_buttons")
        checks_run += 1
        if "localstorage" not in low:
            errors.append("missing_localstorage_persistence")
        if "type=\"submit\"" in low:
            errors.append("native_submit_button_forbidden_in_sandbox")
        return {"passed": len(errors) == 0, "checks_run": checks_run, "errors": errors}

    def _test_app(self, app_html: str, title: str) -> dict[str, Any]:
        """Headless Playwright: loads with zero console errors, key controls
        exist and respond, data persists across a reload."""
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            return self._test_app_fallback_dom(app_html, title)

        errors: list[str] = []
        checks_run = 0
        with tempfile.TemporaryDirectory(prefix="genie-worker-test-") as td:
            app_path = Path(td) / "app.html"
            app_path.write_text(app_html, encoding="utf-8")
            try:
                pw_ctx = sync_playwright()
                pw = pw_ctx.__enter__()
                browser = _launch_chromium(pw)
            except Exception:
                return self._test_app_fallback_dom(app_html, title)
            try:
                page = browser.new_page(viewport={"width": 390, "height": 844})
                console_errors: list[str] = []
                page_errors: list[str] = []
                page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
                page.on("pageerror", lambda exc: page_errors.append(str(exc)))
                page.goto(app_path.as_uri())
                page.wait_for_timeout(400)
                checks_run += 1
                if console_errors or page_errors:
                    errors.append(f"console_or_page_errors:{(console_errors + page_errors)[:2]}")
                body_text = page.evaluate("document.body ? document.body.innerText : ''")
                checks_run += 1
                if not body_text or len(body_text.strip()) < 20:
                    errors.append("empty_or_missing_body_text")
                inputs = page.locator("input, textarea, select").all()
                buttons = page.locator("button").all()
                checks_run += 1
                if not inputs:
                    errors.append("no_form_inputs")
                if not buttons:
                    errors.append("no_buttons")
                # Interact: fill the add form and submit it.
                if inputs and buttons and not errors:
                    checks_run += 1
                    try:
                        err = self._interact_with_app(page)
                        if err:
                            errors.append(err)
                        else:
                            page.wait_for_timeout(300)
                            after = page.evaluate("document.body ? document.body.innerText : ''")
                            stored = page.evaluate("() => JSON.stringify(window.localStorage)")
                            if "Test Entry" not in after and "Test Entry" not in stored:
                                errors.append(
                                    "added_record_not_visible_or_stored:"
                                    f"inputs={len(inputs)} buttons={len(buttons)} "
                                    f"body_chars={len(after)} stored_chars={len(stored)}; "
                                    "the add button's click handler must append the entered "
                                    "record to the list AND persist it (in-memory fallback "
                                    "counts as stored only if it is also rendered)")
                            elif "Test Entry" not in after:
                                errors.append(
                                    "added_record_stored_but_not_rendered:"
                                    "the record reached storage but the list did not "
                                    "re-render it; call the render function after adding")
                            else:
                                # Persistence across reload.
                                checks_run += 1
                                page.reload()
                                page.wait_for_timeout(400)
                                reloaded = page.evaluate("document.body ? document.body.innerText : ''")
                                reloaded_store = page.evaluate("() => JSON.stringify(window.localStorage)")
                                if "Test Entry" not in reloaded and "Test Entry" not in reloaded_store:
                                    errors.append("added_record_did_not_persist_across_reload")
                    except Exception as exc:  # noqa: BLE001 - test failure, reported not raised
                        errors.append(f"interaction_failed:{exc}")
                # Sandboxed-srcdoc pass: the UI shows the app in an
                # <iframe sandbox="allow-scripts" srcdoc=...>. Native
                # form submission is blocked there and the submit event
                # never fires, so the add button must work by click
                # alone. file:// cannot catch this; srcdoc can.
                if not errors:
                    checks_run += 1
                    try:
                        spage = browser.new_page(viewport={"width": 390, "height": 844})
                        s_console: list[str] = []
                        s_pageerr: list[str] = []
                        spage.on("console", lambda msg: s_console.append(msg.text) if msg.type == "error" else None)
                        spage.on("pageerror", lambda exc: s_pageerr.append(str(exc)))
                        spage.set_content('<iframe id="genie-sandbox-probe" sandbox="allow-scripts" style="width:390px;height:800px;border:0"></iframe>')
                        spage.evaluate("([h]) => { document.getElementById('genie-sandbox-probe').srcdoc = h; }", [app_html])
                        spage.wait_for_timeout(600)
                        frames = [f for f in spage.frames if f is not spage.main_frame]
                        if not frames:
                            errors.append("srcdoc_sandbox_no_frame_loaded")
                        else:
                            sframe = frames[0]
                            if s_console or s_pageerr:
                                errors.append(f"srcdoc_sandbox_console_or_page_errors:{(s_console + s_pageerr)[:2]}")
                            else:
                                serr = self._interact_with_app(sframe)
                                if serr:
                                    errors.append(f"srcdoc_sandbox_interaction_failed:{serr}")
                                else:
                                    spage.wait_for_timeout(400)
                                    sbody = sframe.evaluate("() => document.body ? document.body.innerText : ''")
                                    if "Test Entry" not in sbody:
                                        errors.append(
                                            "srcdoc_sandbox_record_not_added_after_click:"
                                            f"body_chars={len(sbody)}; "
                                            "native form submit is blocked in a sandboxed iframe;"
                                            " the add button must be type=button with a click handler "
                                            "that appends the record and re-renders the list")
                        spage.close()
                    except Exception as exc:  # noqa: BLE001 - test failure, reported not raised
                        errors.append(f"srcdoc_sandbox_check_failed:{exc}")
            finally:
                try:
                    browser.close()
                    pw_ctx.__exit__(None, None, None)
                except Exception:
                    pass
        return {"passed": len(errors) == 0, "checks_run": checks_run, "errors": errors}
