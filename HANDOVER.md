# Project handover: MattTheBanana / Automatic Ripping Machine

## Purpose and scope

This repository is a TrueNAS-oriented fork of Automatic Ripping Machine (ARM). It preserves the upstream optical-disc workflow while adding fork-specific container publishing, TrueNAS deployment guidance, media-library naming, responsive UI work, disc-label parsing, TV-series mapping, and configurable email notifications.

The intended user journey is: insert a disc; ARM detects and classifies it; metadata and optional manual corrections determine naming and episode mapping; rip/transcode jobs run; the browser UI displays progress and manages jobs/settings; notifications report important events.

Keep changes backwards-compatible where practical. Never commit real API keys, passwords, app passwords, OAuth refresh tokens, media paths, or user data.

## Repository map

- `arm/ripper/`: ripping orchestration, notification fan-out, process execution, job lifecycle, external tools.
- `arm/models/`: SQLAlchemy models and database-backed state.
- `arm/config/config.py`: loads the live YAML config, merges it over defaults from `setup/arm.yaml`, and migrates newly introduced keys into the live file.
- `setup/arm.yaml`: default config. Add every new setting here.
- `arm/ui/`: Flask setup, browser pages, templates, forms, static assets, and UI-specific helpers.
- `arm/api/`: JSON/AJAX routes and response helpers. API and UI still share the Flask process/database; the separation is by code ownership, not deployment.
- `arm/ui/jobs/jobs.py`: HTML job pages, title search, manual title and TV-series mapping.
- `arm/ui/json_api.py`: compatibility shim for the old API helper module. New API code belongs in `arm/api/`.
- `arm/media_metadata.py`: shared disc-label and title metadata parsing.
- `test/unittest/`: focused unit tests for metadata, naming, notification integrations, and helpers.
- `.github/workflows/`: CI, ShellCheck, image publishing, PR image validation, and upstream-only automation.

## API and UI boundary

The web server still serves the UI and JSON API on the same port. Source responsibilities are separated as follows:

- HTML pages, templates, forms, browser redirects, and presentation stay in `arm/ui/`.
- JSON/AJAX routes are registered by `arm/api/routes.py` under the `route_api` blueprint.
- JSON response and job helpers live in `arm/api/json_api.py`.
- The existing `/json` URL and current response format are retained for existing JavaScript clients.
- `arm/ui/json_api.py` is a small compatibility shim; do not add new API logic there.

When adding an API feature, write the endpoint in `arm/api/routes.py` and reusable request/response logic in `arm/api/json_api.py`. Avoid moving unrelated functions in the same change. Keep the response contract stable unless an explicit migration is planned.

A separately deployable API service is not implemented. That future change first needs an app factory, shared service layer, explicit auth/CSRF/CORS decisions, and API contract tests.

## Configuration and secrets

Add config defaults in `setup/arm.yaml` and setting descriptions in `arm/ui/comments.json`. The config loader merges defaults into existing installs.

The generic settings form auto-renders basic text inputs. Select widgets and secret inputs need explicit handling in `arm/ui/settings/templates/settings/ripper.html`. Secret inputs should render blank, preserve existing values when left blank, and never emit secrets into logs. `arm/ui/utils.py` redacts config values whose keys contain `KEY`, `API`, `PASSWORD`, `SECRET`, or `TOKEN`.

## Email notification providers

`EMAIL_NOTIFICATION_METHOD` selects exactly one provider:

- `none`: email is disabled.
- `smtp`: `arm/smtp_notifications.py`; supports authenticated SMTP/app passwords, STARTTLS, and implicit TLS.
- `gmail_oauth`: `arm/gmail_notifications.py`; exchanges a stored OAuth refresh token for a short-lived Gmail API token.

Only the selected provider sends email so notifications are not duplicated. Provider failures must not interrupt ripping or other Apprise notifications. Tests should use mocked SMTP/API calls and must not require live credentials or network access.

## Development and validation

From the repository root:

```sh
python -m pip install -r requirements.txt
python -m pip install pytest flake8
flake8 . --max-complexity=15 --max-line-length=120 --show-source --statistics
PYTHONPATH=. pytest -q test/unittest/test_ripper_title_naming.py
PYTHONPATH=. pytest -q test/unittest/test_gmail_notifications.py test/unittest/test_smtp_notifications.py
```

GitHub Actions smoke-starts the Flask UI on Python 3.9–3.12 and runs focused tests on Python 3.10. ShellCheck covers shell scripts and Docker workflows cover image builds. Optical-drive integration cannot be fully exercised on generic CI runners, so mock external commands and isolate decision logic.

For each change: inspect current behavior/tests, add focused tests, run tests/lint where possible, clearly state what was not run, and review the full diff for accidental configuration/template/workflow changes.

## GitHub Actions and TrueNAS publishing

`Quality Checks` runs for PRs targeting `main` and pushes to `main`. ShellCheck runs on PRs targeting `main` and pushes to `main`; do not trigger it on every branch push as well, because each PR commit otherwise starts duplicate push and pull-request runs. Concurrency cancels superseded jobs on the same workflow/ref. Each PR synchronization can still create a new CI set, so avoid pushing intermediate commits unnecessarily.

The fork does not need its own `.github/workflows/version_bump.yml`; that workflow is designed for the upstream `automatic-ripping-machine/automatic-ripping-machine` repository. Removing the fork copy stops a skipped upstream-only workflow from appearing on every PR update. Wiki sync is also upstream-only.

TrueNAS images use `ghcr.io/mattthebanana/arm-custom`, based on `ghcr.io/mattthebanana/arm-dependencies-custom:2.0.0`. Keep image tags/base references consistent across the publish workflows, Docker configuration, and README. For anonymous TrueNAS pulls, GHCR packages must be public; otherwise configure pull credentials.

After a code change is merged to `main`, the `Build and publish custom ARM` workflow should publish the custom image. A new image digest/tag is what lets TrueNAS see a refreshed image; merely changing UI code on an unmerged branch does not update the published `latest` image.

## Multiple-agent working agreements

- Use short-lived `feature/<topic>` or `fix/<topic>` branches and open PRs against this fork's `main`.
- Define file ownership when parallelizing. For example: one agent owns API routes/services, another owns UI templates/styles, a third owns tests/docs/workflows.
- Avoid parallel edits to shared files such as `arm/ui/__init__.py`, `arm/ripper/utils.py`, `setup/arm.yaml`, and `arm/ui/comments.json`; integrate changes to these files serially.
- Before continuing after another agent pushes, fetch and integrate the updated branch. Never force-update a ref without checking its current head.
- Put architecture/runtime decisions in the PR summary and keep this handover current.
## Audit notes (October 2026)

- The settings-save handler must bind to the `#ripperSettings` form (not the settings-tab element or submit button). The UI now reports failed save requests instead of silently ignoring them.
- `arm/ui/security.py` creates and persists a cryptographically random Flask session key when no key is configured. Set `ARM_FLASK_SECRET_KEY` as an environment variable to keep it outside `arm.yaml`; writable config storage is needed for automatic persistence.
- Do not reintroduce a fixed `WERKZEUG_DEBUG_PIN` or fixed Flask `SECRET_KEY`.
- SQLite's connection timeout is configured to allow transient concurrent writes more time to complete. This is a mitigation for temporary lock contention, not a substitute for keeping SQLite on suitable local storage.
- Disc identification checks `BDMV` before `VIDEO_TS` so hybrid discs remain identified as Blu-ray. Main-feature selection prioritizes runtime, then file size and chapter count, to avoid choosing a heavily chaptered short extra over the film.
- Job-card HTML is generated in `arm/ui/static/js/common.js`; keep every opened wrapper closed exactly once. Posters and status indicators use dedicated classes with explicit size limits to avoid oversized artwork.
- Ripper settings are grouped into collapsible sections with live filtering. If adding a new setting, update `setup/arm.yaml` and `arm/ui/comments.json`; the section assignment in `settings/ripper.html` may also need updating.
