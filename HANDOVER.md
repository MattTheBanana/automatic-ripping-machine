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


## Current development notes (2026-10-27)

### Recent PRs and verified state

- **PR #14 — Improve MakeMKV progress, failure feedback, and resource UI** is merged to `main` (merge commit `5fd0903c4d498d70d8665e1f2ce610f221c79b18`). It adds separate current-title and total-disc MakeMKV progress bars, progress-log freshness/stall feedback, richer failure notifications with a log action, a resource drawer for system information, and less intrusive notification presentation.
- **PR #15 — Fix duplicate triggers and optical tray lifecycle** remains open and mergeable: https://github.com/MattTheBanana/automatic-ripping-machine/pull/15. Last verified head: `f9c64959548d69bd5516808c0f63e00f17aea5b6`; its Quality Checks, Docker PR build, and ShellCheck passed at that head. It suppresses benign duplicate-trigger failures, avoids finalizing/ejecting an existing active job, detects tray-open cancellation during physical reads, and reduces notification drawer whitespace. Real DVD/Blu-ray/CD hardware testing remains outstanding.
- **PR #16 — Improve rip panel layout and support multi-part discs** remains open and mergeable: https://github.com/MattTheBanana/automatic-ripping-machine/pull/16. Latest verified head: `ec5be13d5991dbcd11a3be257cb2904c229a9a71`. At this exact SHA, Quality Checks, Docker PR build, and ShellCheck all succeeded:
  - Quality Checks: https://github.com/MattTheBanana/automatic-ripping-machine/actions/runs/40542361560
  - Docker PR build: https://github.com/MattTheBanana/automatic-ripping-machine/actions/runs/40542361943
  - ShellCheck: https://github.com/MattTheBanana/automatic-ripping-machine/actions/runs/40542362095
  - Quality Checks includes Python 3.9–3.12 lint/UI-startup coverage, Python and JavaScript CodeQL, and the focused test suite on Python 3.10. The new generic-disc-label test is included in that focused test command. Do not describe PR #16 as merged unless GitHub reports it merged.

### PR #16 implementation notes

- **Compact rip panel and job actions:** active job-card HTML is generated in `arm/ui/static/js/common.js`; styling is in `arm/ui/static/css/arm-modern.css`. The poster column is wider, actions are directly beneath the poster, and Abandon Job is red. The confirmation disables controls while the request runs and shows persistent success/failure/timeout feedback. The success path removes the originating card using its full client card ID, which matters when child/remote server job IDs have prefixes.
- **Side A / Side B:** `disc_side` is a nullable `Job` field, surfaced in `arm/ui/jobs/templates/disc_metadata_controls.html` and active-card badges. This records which side the job represents; ARM does not automatically flip the physical disc or detect which side is facing the laser. For double-sided media, complete the first side as one job, flip the disc, then use a separate job labeled with the other side.
- **Double-feature selection:** existing job title fields represent Feature A. New optional fields on `Job` represent Feature B: `secondary_title`, `secondary_year`, `secondary_video_type`, `secondary_imdb_id`, `secondary_tmdb_id`, `secondary_poster_url`, and `secondary_plot`; `plot` stores Feature A's summary. The title-search flow supports choosing two distinct search results, preserving Feature A while searching for Feature B, previewing poster/type/year/plot symmetrically, and saving both choices together. Active cards show the two feature summaries side by side and refresh them when displayed feature metadata changes.
- **Double-feature scope limitation:** the implementation records and displays two titles but does not determine which MakeMKV title/track corresponds to each film, split output files by film, or trigger a separate rip pass for the second title. Treat end-to-end file mapping/output naming as a separate follow-up requirement; do not claim the current change automatically produces two correctly named movie files.
- **Database migration:** `arm/migrations/versions/8c1d4f2a9b70_side_double_feature.py` adds `disc_side`, Feature A's `plot`, and Feature B metadata columns. Upgrade/downgrade against a copy of an existing database before release. Existing installations need the migration applied before the new model fields are usable. Merging code alone does not update an existing running container.
- **Generic disc-title filtering:** `arm/media_metadata.py:is_generic_disc_title` and `title_search_variants` filter placeholders before search; guards in `arm/ui/metadata.py` also prevent generic direct TMDB poster/search calls. Cases include `undefined`, `unknown`, `video`, `DVD_VIDEO`, `VIDEO_TS`, `disc 1`, `unknown_volume_1`, and other generic/numbered volume labels. The focused regression tests are in `test/unittest/test_generic_disc_labels.py`, and `.github/workflows/main.yml` includes them in the Python 3.10 test step. Keep this list conservative to avoid blocking legitimate film titles.
- **MakeMKV progress-log link:** the freshness text now links to `LOGPATH/progress/<job_id>.log`, the separate MakeMKV progress file, not the regular ARM job logfile. `arm/api/json_api.py` exposes its basename as `progress_logfile`; `arm/ui/static/js/common.js` links the label; `arm/ui/logs/logs.py` handles a restricted progress-source mode and validates numeric `<job_id>.log` names; `arm/ui/logs/templates/logview.html` passes the source flag through to the reader.
- **Job-card refresh contract:** keep relevant element IDs in `common.js` and `jobRefresh.js` consistent. The refresh loop normally updates existing cards incrementally; it rebuilds double-feature cards if their visible metadata/layout changes. Do not put a full card rebuild on every poll.
- **Template/CSS checks:** inspect both desktop and narrow mobile layouts. Verify button placement, visible progress bars, poster clipping, selection persistence while choosing Feature B, and both feature columns' symmetric details. A CI smoke-start is not a browser-based visual check.

### Remaining validation before merge/release

1. Review the full PR #16 diff and manually exercise the title-selection flow, Abandon Job modal success/error paths, and MakeMKV progress-log link in a running UI.
2. If further commits are pushed to PR #16, re-check CI for the exact new head SHA before merge. The currently verified passing SHA is `ec5be13d5991dbcd11a3be257cb2904c229a9a71`.
3. Test Alembic upgrade and downgrade using a backup/copy of a database before production deployment.
4. Test actual optical hardware: normal DVD/Blu-ray ripping, tray-open cancellation, double-sided media as two separate Side A/Side B jobs, and a real double-feature disc. The shared CI runners do not validate physical drive behavior.
5. After merge, verify that the custom ARM image publish workflow succeeded and recreate/redeploy the TrueNAS workload with the updated image. An open PR or merged source commit by itself does not update the running container.

## Notification drawer email preferences (2026-10-27)

- The notification slide-out drawer includes persistent switches for email notifications overall, errors, successful completion, and other events. The “other events” category is present because ARM also emits informational events such as disc detection and job-start notifications.
- Defaults are declared in `setup/arm.yaml`; descriptions are in `arm/ui/comments.json`. The drawer saves changes through the authenticated `/notificationpreferences` endpoint, using the session CSRF token.
- Email category filtering is applied in `arm/ripper/utils.py` before SMTP/Gmail delivery. Local database notifications, Apprise, and post-processing scripts are unchanged by these email-only preferences. Error wording takes precedence over completion wording when a message mentions both.
- Focused categorization tests are in `test/unittest/test_notification_preferences.py`. Run them with `PYTHONPATH=. pytest -q test/unittest/test_notification_preferences.py`; runtime tests still need to be run in a project environment.


## Current development notes (2026-10-28)

### Repository and pull requests

- The verified `main` HEAD is `d5635f034958bfd5a705228b45a14989255ce18d` (PR #19 merge, log text selection/copy improvements).
- **PR #20 — Refresh missing optical drives before starting a rip** remains open and mergeable: https://github.com/MattTheBanana/automatic-ripping-machine/pull/20. Last verified head: `bdc157010f45f5b278567d9929fbd583ed54f7a6`. It retries drive inventory discovery when a `/dev/srN` job has no matching database row and adds MakeMKV failure diagnostics. Recheck CI and update the branch if the merged base changes.
- **PR #21 — Add optional smart title resolution and refine rip progress UI** is open: https://github.com/MattTheBanana/automatic-ripping-machine/pull/21. Initial head: `0c2562067e24977fee891d375a057db3e1cf24b2`; this branch includes the follow-up lint fix and this handover update. Check the latest head/CI before review or merge.
- PR #21's first Quality Checks run failed at lint for `E128` in `arm/ui/metadata.py` and `E303` in `arm/ui/settings/settings.py`; both were corrected in follow-up commit `32d5c1df9c9ddb477a44a161b535ddeb317c33cf`. On that SHA, Python lint, Python/JavaScript CodeQL, the focused Python 3.10 tests, and Python 3.9/3.11 UI smoke tests passed; Python 3.12 and Docker were still running when last checked, then the Docker build also passed. A later CSS-only regular-weight title correction and handover update triggered a new CI run; validate its exact head before merge.

### Optional smart title matching and filename/display punctuation

- Normal ARM matching remains the default. The opt-in resolver is implemented in `arm/ui/metadata.py:smart_title_candidate` and called from `arm/ripper/identify.py:update_job` only when `UISettings.smart_title_matching_enabled` is true.
- The resolver asks a configured local Ollama endpoint to select an index from real TMDB/OMDb results (titles, years, media types, summaries and available popularity signals). The model cannot return a new title/ID for ARM to accept; selections outside the candidate list or below confidence 0.6 are rejected, and the existing deterministic matcher is the fallback.
- Ollama is intentionally a **separate service**; ARM's base image does not install a model runtime, extra Python ML packages or weights. UI Settings asks for confirmation when enabling the feature and offers a button to request model-weight downloads from the configured Ollama URL. The endpoint must be reachable from inside the ARM container. Candidate text and summaries are sent to that configured local endpoint only when enabled.
- Setup guidance is in `docs/optional-smart-title-resolution.md`; focused mocked resolver tests are in `test/unittest/test_optional_smart_title_resolution.py`. The schema migration is `arm/migrations/versions/a2b6c1d8e4f0_smart_title_datetime_settings.py`, which adds the date/time format fields and optional model configuration.
- `arm/media_metadata.py` strips a set of common trailing mastering/format suffixes (including `WS`) for parsing/search variants, so `Mr Mrs Smith Ws` produces the cleaned query `Mr Mrs Smith`. Keep normalization conservative and retain the raw label as a query variant.
- `arm/ripper/identify.py:update_job` now retains the provider's canonical title (including colon punctuation) in job metadata. Filename punctuation is still sanitized at the file/folder naming boundary in `arm/ripper/utils.py:clean_for_filename`/ `fix_job_title`; don't use filesystem-safe strings as display titles.

### Active-rip UI and notification spacing

- Active-card title rendering is in `arm/ui/static/js/common.js` and `arm/ui/static/css/arm-modern.css`: title left-aligned and regular weight; year aligned to its right in muted color without shrinking its font; the separate Year row is removed; Status and Stage share one line. Double-feature cards retain both feature rows.
- Start timestamps support stored UI settings `start_date_format` and `start_time_format`; defaults are `MM/DD/YYYY` and 12-hour AM/PM. Settings are saved by `/save_ui_settings`.
- ETA no longer displays a literal `Unknown` when ARM/MakeMKV has no ETA. The browser uses a valid reported ETA where available and otherwise estimates current-title time remaining only after observing progress movement; if too little progress exists to estimate, the field stays hidden.
- The active progress summary uses a transparent, centered, lower-card-aligned layout. Toast stack spacing was tightened by removing each toast's bottom margin (the toast holder owns the gap) and reducing inner padding. Confirm appearance at desktop and mobile widths; CI does not run a visual browser check.

### Current hardware investigation (requires the user's system)

- Additional power appeared to help the LG BU40N, but the latest provided rip still logged repeated `ILLEGAL REQUEST: INVALID FIELD IN CDB` and failed to save MakeMKV title 30 (process exit code 1). This is separate from title disambiguation and is not evidence the smart matcher caused the rip failure. A drive/media/SCSI-command path problem remains possible; use a known-good Blu-ray, another drive/cable/enclosure if available, and the full MakeMKV progress/job logs before changing firmware again.
- Tray auto-close remained after setting `dev.cdrom.autoclose=0`. That sysctl controls a kernel automatic-close behavior; it cannot block an explicit tray-close command from a process. `arm/models/system_drives.py:SystemDrives.eject(method="close")` explicitly invokes `eject --trayclose`, while `DriveUtils.update_tray_status` only polls status. No responsible process/timer is confirmed yet; trace the issuing process before attributing it to ARM or recommending another kernel setting.
- The earlier `NoResultFound` error for an unregistered `/dev/sr3` fails during drive lookup before creating a rip job. PR #20 addresses that inventory path but does not establish the cause of the separate MakeMKV read/save failure.

### Deployment / validation reminders

- Changes on PR #21 do not update the running TrueNAS container or published `latest` image. Merge, confirm the custom image publish workflow succeeds, then pull/recreate the app; inspect image digest and ARM's displayed Git revision if it remains stale.
- Apply the new Alembic migration on upgrade; test upgrade/downgrade on a database copy before production release. No actual Ollama service, browser visual test, or optical hardware is exercised by generic CI.
