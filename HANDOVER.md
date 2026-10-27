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

### TrueNAS custom-app revision and image identity

- This deployment is a TrueNAS **Custom App** built from Docker Compose YAML (the exported config includes TrueNAS-specific `x-portals` metadata). The TrueNAS catalog `Revision` field is catalog packaging metadata; it is not configurable in a Compose YAML and adding `revision:` to this service will not increment it. Do not confuse that with ARM's `Current git version` shown in General Info.
- ARM's current Git hash display is implemented in `arm/ui/utils.py:get_git_revision_hash()`; it calls `git rev-parse HEAD` in `INSTALLPATH` and truncates to seven characters. This reports the source checkout embedded in the image, not a TrueNAS deployment revision.
- `.github/workflows/publish-custom-arm.yml` runs on pushes to `main` and currently publishes the same build to `latest`, the `VERSION` value (currently `2.24.4`), and the mutable legacy tag `makemkv-2.0.0`. Thus the legacy tag name does not identify a unique build. Main commit `44ee1ccc02ebe7c9b750dd0e69772e87019cdbe9` published successfully after PR #6 was merged, and the latest build for commit `fc56a5a22ba998c3bae1526d93a48edd1c6894fb` also succeeded after PR #7 was merged. Older running images can still show an earlier hash if TrueNAS has not recreated the workload with the newer image digest.
- Recommended follow-up: add an immutable tag such as `git-<short-sha>` (and optionally a workflow run/build number) to the custom publish workflow and document the matching image reference. On TrueNAS, select that exact image tag in the YAML and update/redeploy the Custom App. A mutable tag such as `latest` may keep the same text while its digest changes; don't use the TrueNAS catalog revision as the indicator for this custom image.

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

## Current handover state (2026-10-23)

- PR #5, **Audit UI and fix recurring ARM bugs**, is merged to `main`. It includes the Ripper Settings save handler fix, responsive job-card/poster/status sizing, searchable/collapsible settings, a persistent random Flask session key (or `ARM_FLASK_SECRET_KEY` override), hybrid Blu-ray detection precedence, runtime-first MakeMKV main-feature selection, and a 30-second SQLite connection timeout.
- PR #6, **Improve ripper settings field labels and layout**, is merged to `main`. All 99 current `setup/arm.yaml` keys have human-readable labels above each field, with the actual config key right-aligned in muted gray; boxed left-side labels were removed.
- PR #7, **Fix Python 3.9 UI startup compatibility**, is merged to `main`. It adds `from __future__ import annotations` after the module docstring in `arm/ripper/identify.py` to prevent Python 3.9 from evaluating `str | None` at import time. Its Quality Checks, ShellCheck, and Docker PR build all passed.
- The post-merge Quality Checks, ShellCheck, and `Build and publish custom ARM` workflow all succeeded for main commit `fc56a5a22ba998c3bae1526d93a48edd1c6894fb`. The custom image workflow publishes `latest`, `2.24.4`, and `makemkv-2.0.0`; these names currently point to the same built image for each successful main push.
- The user's TrueNAS app is a Compose-based Custom App using `ghcr.io/mattthebanana/arm-custom:makemkv-2.0.0`. If ARM General Info still shows `e5672a1` after the successful `fc56a5a` build, inspect the container's actual image ID/digest and whether TrueNAS pulled/recreated the workload. A fixed tag can point to a new digest without its text changing. The TrueNAS catalog `Revision` isn't set by this Compose YAML.
- Next useful improvement: publish an immutable per-commit image tag (for example, `git-<short-sha>`) alongside `latest`, the VERSION tag, and the legacy tag. Then TrueNAS deployments can select a specific build and the displayed image reference makes rollouts unambiguous. Check the current TrueNAS app's pull/redeploy behavior before adding `pull_policy: always`.


## Notification drawer email preferences (2026-10-27)

- The notification slide-out drawer includes persistent switches for email notifications overall, errors, successful completion, and other events. The “other events” category is present because ARM also emits informational events such as disc detection and job-start notifications.
- Defaults are declared in `setup/arm.yaml`; descriptions are in `arm/ui/comments.json`. The drawer saves changes through the authenticated, CSRF-protected `/notificationpreferences` endpoint.
- Email category filtering is applied in `arm/ripper/utils.py` before SMTP/Gmail delivery. Local database notifications, Apprise, and post-processing scripts are unchanged by these email-only preferences. Error wording takes precedence over completion wording when a message mentions both.
- Focused categorization tests are in `test/unittest/test_notification_preferences.py`. Run them with `PYTHONPATH=. pytest -q test/unittest/test_notification_preferences.py`; this change has not been run in a project test environment yet.
