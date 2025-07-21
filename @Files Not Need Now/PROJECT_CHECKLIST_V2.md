# Project Checklist V2: Automated Website Monitoring System

This checklist tracks the progress of the Automated Website Monitoring System.
It incorporates feedback from `Libraries to use .md` and reflects current project status.

## Phase 0: Initial Setup & Design (Mostly Completed)
- [x] **Task 0.1:** Initialize Git Repository
- [x] **Task 0.2:** Define Project Structure (`src`, `tests`, `data`, `config`, `docs`, `scripts`)
- [x] **Task 0.3:** Create `requirements.txt`
- [x] **Task 0.4:** Design YAML-based Configuration System (`config/config.yaml`)
- [x] **Task 0.5:** Implement Configuration Loader (`src/config_loader.py`)
- [x] **Task 0.6:** Implement Logging System (`src/logger_setup.py`)

## Phase 1: Website List Management (Completed)
- [x] **Task 1.1:** Define Data Model for `data/websites.json`
- [x] **Task 1.2:** Create empty `data/websites.json`
- [x] **Task 1.3:** Implement Website Manager (`src/website_manager.py`) for CRUD operations.

## Phase 2: Scheduler & Runner (Completed)
- [x] **Task 2.1:** Integrate `schedule` library.
- [x] **Task 2.2:** Create `src/scheduler.py` to load and schedule website checks.
- [x] **Task 2.3:** Implement placeholder for `perform_website_check`.
- [x] **Task 2.4:** Refine scheduler loop for graceful shutdown (`signal`, `threading.Event`).

## Phase 3: Web Content Retriever (Completed)
- [x] **Task 3.1:** Integrate `requests` library.
- [x] **Task 3.2:** Implement `src/content_retriever.py` with `fetch_website_content()`.
    - [x] HTTP error handling, timeouts, User-Agent.

## Phase 4: Snapshot Tool (Completed)
- [x] **Task 4.1:** Create `src/snapshot_tool.py`.
- [x] **Task 4.2:** Implement `save_html_snapshot()` (save HTML, calculate SHA256).
- [x] **Task 4.3:** Implement `save_visual_snapshot()`
    - [x] Use `Playwright` for screenshots.
    - [x] Configurable browser settings via `config.yaml` (e.g., `playwright_browser_type`).

## Phase 5: Content Comparator & Change Detector (Partially Completed & Needs Review)
- [x] **Task 5.1:** Integrate `beautifulsoup4`, `Pillow`, `numpy`.
- [x] **Task 5.2:** Create `src/comparators.py`.
    - [x] `extract_text_from_html()`
    - [x] `compare_html_text_content()` (difflib)
    - [x] `compare_html_structure()` (difflib after parsing/cleaning)
    - [x] `extract_meta_tags()` & `compare_meta_tags()`
    - [x] `extract_links()` & `compare_links()`
    - [x] `extract_canonical_url()` & `compare_canonical_urls()`
    - [x] `extract_image_sources()` & `compare_image_sources()`
    - [x] `compare_screenshots()` (Pillow, MSE, diff image)
- [x] **Task 5.3:** Review and Enhance Change Detection Logic in `scheduler.py`.
    - [x] Verified `determine_significance` function; improved logging and handling of missing scores.
    - [ ] TODO: Test with various change scenarios (manual testing or future automated tests).
- [x] **Task 5.4:** Implement Semantic Comparison using `diff-match-patch`.
    - [x] Added `diff-match-patch` to `requirements.txt`.
    - [x] Implemented `compare_text_semantic` in `src/comparators.py`.
    - [x] Integrated into `src/scheduler.py` (compare, store results, use in significance check).
    - [x] Added `semantic_similarity_threshold` to `config/config.yaml`.
    - [x] Updated `src/alerter.py` to include semantic diff score in alerts.
- [x] **Task 5.5:** Implement more advanced image comparison (SSIM with OpenCV & scikit-image).
    - [x] Added `opencv-python` and `scikit-image` to `requirements.txt`.
    - [x] Implemented `compare_screenshots_ssim` in `src/comparators.py` (handles missing libraries gracefully).
    - [x] Integrated into `src/scheduler.py` (call if libraries available, store score, use in significance check).
    - [x] Added `ssim_similarity_threshold` to `config/config.yaml`.
    - [x] Updated `src/alerter.py` to include SSIM score in alerts.
- [x] **Task 5.6:** Configuration for ignoring/masking dynamic regions in screenshots.
    - [x] Added `visual_comparison_ignore_regions` to `config/config.yaml` (global setting).
    - [x] Implemented `_apply_ignore_regions` helper in `src/comparators.py`.
    - [x] Updated `compare_screenshots` (MSE) and `compare_screenshots_ssim` to use ignore regions.
    - [x] Updated `src/scheduler.py` to pass global ignore regions to comparison functions.
    - [ ] TODO: Implement per-site ignore regions and UI for managing them.

## Phase 6: Version History (Completed)
- [x] **Task 6.1:** Add `check_history_file_path` to `config.yaml`.
- [x] **Task 6.2:** Create `src/history_manager.py` for `data/check_history.json`.
    - [x] `add_check_record()`, `get_check_history_for_site()`, `get_latest_check_for_site()`.

## Phase 7: Alerting & Notification (Completed)
- [x] **Task 7.1:** Create `src/alerter.py`.
- [x] **Task 7.2:** Implement `send_email_alert()` (smtplib, multipart).
- [x] **Task 7.3:** Implement `format_alert_message()`.
- [x] **Task 7.4:** Add `smtp_use_tls` to `config.yaml`.

## Phase 8: Reporting (Completed)
- [x] **Task 8.1:** Create `src/report_generator.py`.
- [x] **Task 8.2:** Implement `generate_json_report()`.
- [x] **Task 8.3:** Implement `generate_csv_report()`.
- [ ] **Task 8.4:** Implement PDF report generation (e.g., using `reportlab`).
    - Suggested in `Libraries to use .md`.

## Phase 9: Integration & Refinement (Completed for V1)
- [x] **Task 9.1:** Enhance `perform_website_check` in `scheduler.py` to orchestrate the full monitoring cycle.
- [x] **Task 9.2:** Add relevant thresholds and configurations to `config.yaml`.

## Phase 10: User Interface (CLI - Completed)
- [x] **Task 10.1:** Integrate `click` library.
- [x] **Task 10.2:** Create `src/cli.py` with commands for:
    - [x] Website management (`add-site`, `list-sites`, `remove-site`, `update-site`).
    - [x] History (`get-history`).
    - [x] Manual checks (`run-check`).
    - [x] Report generation (`generate-report`).
- [x] **Task 10.3:** Create `main.py` as CLI entry point.

## Phase 11: Non-Functional Requirements (Partially Addressed)
- [ ] **Task 11.1:** Performance Optimization.
    - [ ] Analyze and optimize critical paths (e.g., snapshotting, comparison).
    - [ ] Consider asynchronous operations for I/O bound tasks (e.g., `asyncio` with `aiohttp`, `aiosmtplib`).
- [ ] **Task 11.2:** Scalability.
    - [ ] Evaluate current design for handling a larger number of websites.
    - [ ] Investigate message queues (e.g., Celery, Redis Queue) if scaling becomes a bottleneck (mentioned in `Libraries to use .md`).
- [x] **Task 11.3:** Robust Error Handling (Initial implementation in place, requires ongoing review).
    - [ ] Ensure comprehensive error logging and graceful failure across all modules.
- [ ] **Task 11.4:** Security Considerations.
    - [ ] Review handling of sensitive data (e.g., SMTP passwords in config).
    - [ ] Sanitize inputs if exposing any web interfaces.
- [ ] **Task 11.5:** Configuration for Retries (Fetch retries implemented, consider for other operations).
    - [x] `fetch_retry_total`, `fetch_retry_backoff_factor`, `fetch_retry_status_forcelist` in `config.yaml`.

## Phase 12: Documentation (Partially Completed)
- [x] **Task 12.1:** Create `README.md` (Covers overview, setup, running, modules).
- [x] **Task 12.2:** Create `.gitignore`.
- [ ] **Task 12.3:** Add Code Documentation / Docstrings.
    - [ ] Ensure all functions, classes, and modules have clear docstrings.
- [ ] **Task 12.4:** User Guide (More detailed than README, if necessary).
- [ ] **Task 12.5:** Deployment Guide.

## Phase 13: Advanced Features & Enhancements (Future)
- [ ] **Task 13.1:** Web Dashboard for Monitoring Results.
    - Suggested in `Libraries to use .md` (Flask or FastAPI).
    - Existing config options `dashboard_port`, `log_level_dashboard`, `log_file_dashboard`, `dashboard_history_limit`, `dashboard_api_history_limit` suggest this was planned.
- [ ] **Task 13.2:** Performance Monitoring (Page Load Time).
    - Mentioned as optional in `Libraries to use .md`. Could use Playwright/Selenium navigation timings.
- [ ] **Task 13.3:** JavaScript Execution Analysis.
    - Monitor for changes in JS-heavy sites, detect JS errors.
- [ ] **Task 13.4:** More Granular Change Detection.
    - E.g., identify changes within specific CSS selectors.
- [ ] **Task 13.5:** Headless Browser Choice & Implementation Verification.
    - Current: Assumed `Playwright` based on `config.yaml` settings (`playwright_*` options).
    - `Libraries to use .md` also mentions `pyppeteer` and `Selenium` as options initially considered.
    - [x] Verify `src/snapshot_tool.py` consistently uses Playwright as indicated by `config.yaml` and update if necessary.
- [ ] **Task 13.6:** Database for Storage.
    - `Libraries to use .md` mentions SQLite for lightweight storage. This could replace JSON files for `websites.json` and `check_history.json` for better querying and atomicity.

## Phase 14: Testing
- [ ] **Task 14.1:** Unit Tests.
    - [ ] Write unit tests for individual functions and modules (e.g., comparators, managers).
- [ ] **Task 14.2:** Integration Tests.
    - [ ] Test interactions between components (e.g., full check cycle).
- [ ] **Task 14.3:** End-to-End Tests.
    - [ ] Test CLI commands and scheduler behavior.

This V2 checklist should provide a good roadmap. We can now focus on the "Needs Review" and new items, particularly improving the change detection and then moving on to other enhancements. 