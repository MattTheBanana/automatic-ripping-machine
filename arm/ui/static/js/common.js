/*jshint multistr: true */
/*jshint esversion: 6 */
/*global $:false, jQuery:false */
/* jshint node: true */
/* jshint strict: false */

const MODEL_ID = "#exampleModal";
const DB_SUCCESS_BTN_ID = "#save-get-success";
const DB_FAIL_BTN_ID = "#save-get-failed";
const MSG_1_ID = "#message1 .alert-heading";
const SEARCH_BOX_ID = "#searchquery";
const MODAL_TITLE = ".modal-title";
const CARD_DECK = ".card-deck";
const SUCCESS_CLASS = "alert-success";
const MODAL_FOOTER = ".modal-footer";

function escapeHtml(value) {
    const entities = {"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"};
    return String(value === null || value === undefined ? "" : value)
        .replace(/[&<>"']/g, character => entities[character]);
}

function mediaTypeLabel(value) {
    const type = String(value || "Unknown").trim();
    return type ? type.charAt(0).toUpperCase() + type.slice(1).toLowerCase() : "Unknown";
}

function positiveNumber(value) {
    const number = parseInt(value, 10);
    return Number.isFinite(number) && number > 0 ? number : null;
}

function isEnabled(value) {
    return value === true || ["1", "true", "yes", "on"].includes(String(value).toLowerCase());
}

function formatElapsedSeconds(value) {
    let seconds = Math.max(0, Math.floor(Number(value) || 0));
    const days = Math.floor(seconds / 86400);
    seconds %= 86400;
    const hours = Math.floor(seconds / 3600);
    seconds %= 3600;
    const minutes = Math.floor(seconds / 60);
    seconds %= 60;
    const clock = [hours, minutes, seconds].map(part => String(part).padStart(2, "0")).join(":");
    return days > 0 ? `${days}d ${clock}` : clock;
}

function formatActivityAge(seconds) {
    const value = Math.max(0, Math.floor(Number(seconds) || 0));
    if (value < 60) return `${value}s`;
    if (value < 3600) return `${Math.floor(value / 60)}m ${value % 60}s`;
    return `${Math.floor(value / 3600)}h ${Math.floor((value % 3600) / 60)}m`;
}

function renderProgressHealthNode(node, age) {
    const seconds = Math.max(0, Math.floor(Number(age) || 0));
    node.dataset.progressAgeSeconds = String(seconds);
    const stale = seconds >= Number(node.dataset.staleThreshold || 120);
    node.classList.toggle("arm-progress-health-stale", stale);
    const ageValue = node.querySelector(".arm-progress-age");
    const warning = node.querySelector(".arm-progress-warning-message");
    if (ageValue) ageValue.textContent = formatActivityAge(seconds);
    if (warning) {
        warning.textContent = stale
            ? `No new updates for ${formatActivityAge(seconds)}. The drive may be reading a difficult sector or the job may be stalled; check the job log if this continues.`
            : "";
    }
    if (stale) node.setAttribute("role", "status");
    else node.removeAttribute("role");
}

function startElapsedJobClock() {
    if (window.armElapsedJobClockStarted) return;
    window.armElapsedJobClockStarted = true;
    window.setInterval(function () {
        document.querySelectorAll(".arm-elapsed-time[data-running='true']").forEach(function (node) {
            const elapsed = Math.max(0, Number(node.dataset.elapsedSeconds) || 0) + 1;
            node.dataset.elapsedSeconds = String(elapsed);
            node.textContent = formatElapsedSeconds(elapsed);
        });
        document.querySelectorAll(".arm-progress-health[data-progress-age-seconds]").forEach(function (node) {
            const age = Math.max(0, Number(node.dataset.progressAgeSeconds) || 0) + 1;
            renderProgressHealthNode(node, age);
        });
    }, 1000);
}
startElapsedJobClock();

function buildDiscMetadataBadges(job) {
    const badges = [];
    const season = positiveNumber(job.season_number);
    const disc = positiveNumber(job.disc_number);
    const first = positiveNumber(job.episode_start);
    const last = positiveNumber(job.episode_end);
    if (season) badges.push(`<span class="arm-job-metadata-badge">Season ${String(season).padStart(2, "0")}</span>`);
    if (disc) badges.push(`<span class="arm-job-metadata-badge">Disc ${disc}</span>`);
    const side = String(job.disc_side || "").trim().toUpperCase();
    if (side === "A" || side === "B") badges.push(`<span class="arm-job-metadata-badge">Side ${side}</span>`);
    if (hasDisplayValue(job.secondary_title)) badges.push('<span class="arm-job-metadata-badge arm-job-double-feature-badge">Double feature</span>');
    if (first && last) {
        const range = first === last ? String(first).padStart(2, "0")
            : `${String(first).padStart(2, "0")}–${String(last).padStart(2, "0")}`;
        badges.push(`<span class="arm-job-metadata-badge">Episodes ${range}</span>`);
    } else if (first || last) {
        const episode = String(first || last).padStart(2, "0");
        badges.push(`<span class="arm-job-metadata-badge">Episode ${episode}</span>`);
    }
    if (isEnabled(job.special_features)) {
        badges.push('<span class="arm-job-metadata-badge arm-job-special-badge">Special Features</span>');
    }
    return badges.join("");
}

function getRipperName(job, idsplit) {
    const reportedName = String(job.ripper || "").trim();
    if (reportedName && !["none", "null", "undefined"].includes(reportedName.toLowerCase())) {
        return reportedName;
    }
    return idsplit[0] === "0" ? "Local" : "";
}

function addJobItem(job, authenticated) {
    const idsplit = String(job.job_id || "").split("_");
    if (idsplit[1] === undefined) {
        idsplit[0] = "0";
        idsplit[1] = job.job_id;
    }
    const serverJob = idsplit[0] !== "0";
    const detailUrl = serverJob
        ? `${job.server_url}/jobdetail?job_id=${encodeURIComponent(idsplit[1])}`
        : `/jobdetail?job_id=${encodeURIComponent(idsplit[1])}`;
    const doubleFeature = hasDisplayValue(job.secondary_title);
    // A two-feature job needs a full dashboard row so both movie summaries and
    // the rip configuration remain readable side by side while the job refreshes.
    const columnClass = doubleFeature
        ? "col-12 arm-job-column arm-job-column-double-feature"
        : "col-md-6 col-xl-4 arm-job-column";
    let x = `<div class="${columnClass}" id="jobId${job.job_id}">`;
    x += `<div class="card arm-job-card mx-auto${doubleFeature ? " arm-job-card-double-feature" : ""}">`;
    x += "<div class=\"card-header arm-job-card-header\"><div id=\"jobId" + job.job_id +
        "_header\" class=\"arm-job-title-header\">" + titleHeaderMarkup(job) + "</div></div>";
    if (doubleFeature) {
        x += `<div class="arm-job-double-feature-media">${featureSummaryMarkup(job, false)}${featureSummaryMarkup(job, true)}</div>`;
        x += `<div class="arm-job-double-feature-details">${buildMiddleSection(job)}${buildRightSection(job, idsplit, authenticated)}</div>`;
        x += `<div class="arm-job-double-feature-actions">${buildJobActions(job, idsplit, authenticated, serverJob)}</div>`;
    } else {
        x += `<div class="row no-gutters arm-job-card-content">`;
        x += `<div class="arm-job-poster-column"><a href="${detailUrl}">${posterCheck(job)}</a>${buildJobActions(job, idsplit, authenticated, serverJob)}</div>`;
        x += `<div class="arm-job-details-column">${buildMiddleSection(job, false)}${buildRightSection(job, idsplit, authenticated)}<div id="jobId${job.job_id}_progress_section" class="arm-job-progress-section">${transcodingCheck(job)}</div></div>`;
        x += "</div>";
    }
    x += "</div></div>";
    return x;
}

function progressPercent(value) {
    const number = Number(value);
    if (!Number.isFinite(number)) return 0;
    return Math.max(0, Math.min(100, number));
}

function progressBarMarkup(job, key, heading, subtitle, percentage) {
    const value = progressPercent(percentage);
    return `<div class="arm-progress-row">
        <div class="arm-progress-heading">
            <strong>${escapeHtml(heading)}</strong>
            <span id="jobId${job.job_id}_${key}_title">${escapeHtml(subtitle || "")}</span>
        </div>
        <div id="jobId${job.job_id}_${key}" class="progress arm-progress-track" role="progressbar"
             aria-label="${escapeHtml(heading)}" aria-valuenow="${value}" aria-valuemin="0" aria-valuemax="100">
            <div id="jobId${job.job_id}_${key}_bar" class="progress-bar progress-bar-striped"
                 style="width: ${value}%;"></div>
            <span id="jobId${job.job_id}_${key}_value" class="arm-progress-value">${value.toFixed(1)}%</span>
        </div>
    </div>`;
}

function makeMKVProgressMarkup(job) {
    let x = progressBarMarkup(
        job, "total_progress", "Total disc progress",
        job.total_progress_title || "Entire disc", job.total_progress_round
    );
    x += progressBarMarkup(
        job, "current_title_progress", "Current title",
        job.current_title || "Current title",
        job.current_title_progress_round !== undefined ? job.current_title_progress_round : job.progress_round
    );
    x += "<div id=\"jobId" + job.job_id + "_eta\" class=\"arm-progress-eta\" hidden>" +
        "<strong>ETA for current title: </strong><span class=\"arm-progress-eta-value\"></span></div>";
    return x;
}

function standardProgressMarkup(job) {
    const value = progressPercent(job.progress_round);
    let x = progressBarMarkup(job, "progress", "Progress", "", value);
    x += "<div id=\"jobId" + job.job_id + "_eta\" class=\"arm-progress-eta\" hidden>" +
        "<strong>ETA: </strong><span class=\"arm-progress-eta-value\"></span></div>";
    x += "<div id=\"jobId" + job.job_id + "_cur_fps\"><strong>CUR FPS: </strong>" +
        escapeHtml(job.cur_fps || "—") + "</div>";
    x += "<div id=\"jobId" + job.job_id + "_avg_fps\"><strong>AVG FPS: </strong>" +
        escapeHtml(job.avg_fps || "—") + "</div>";
    return x;
}

function buildProgressMarkup(job) {
    if (job.status === "ripping" && job.progress_kind === "makemkv") {
        return makeMKVProgressMarkup(job);
    }
    if ((job.status === "transcoding" && job.stage !== "" && job.progress) ||
        (job.disctype === "music" && job.stage !== "")) {
        return standardProgressMarkup(job);
    }
    return "";
}

function buildProgressHealth(job) {
    const age = job.progress_age_seconds === null || job.progress_age_seconds === undefined
        ? NaN : Number(job.progress_age_seconds);
    if (!Number.isFinite(age) || !job.progress_activity_source) return "";
    const source = String(job.progress_activity_source);
    const isMakeMKVLog = /makemkv.*progress log/i.test(source);
    const progressLogfile = String(job.progress_logfile || "").trim();
    const sourceLabel = isMakeMKVLog && /^\d+\.log$/.test(progressLogfile)
        ? `<a href="logs?logfile=${encodeURIComponent(progressLogfile)}&amp;mode=full&amp;source=progress">MakeMKV progress log</a>`
        : escapeHtml(source);
    return `<div id="jobId${job.job_id}_progress_health" class="arm-progress-health"
                 data-progress-age-seconds="${Math.max(0, Math.floor(age))}" data-stale-threshold="120"
                 data-progress-source="${escapeHtml(source)}" data-progress-logfile="${escapeHtml(progressLogfile)}">
        <span>Last update to ${sourceLabel}: <strong class="arm-progress-age">${formatActivityAge(age)}</strong> ago.</span>
        <span class="arm-progress-warning-message"></span>
    </div>`;
}

function updateProgressHealth(container, job) {
    if (!container) return;
    const age = job.progress_age_seconds === null || job.progress_age_seconds === undefined
        ? NaN : Number(job.progress_age_seconds);
    const source = String(job.progress_activity_source || "");
    const progressLogfile = String(job.progress_logfile || "").trim();
    let node = document.getElementById(`jobId${job.job_id}_progress_health`);
    if (!Number.isFinite(age) || !source) {
        if (node) node.remove();
        return;
    }
    if (node && (node.dataset.progressSource !== source ||
            node.dataset.progressLogfile !== progressLogfile)) {
        node.remove();
        node = null;
    }
    if (!node) {
        container.insertAdjacentHTML("beforeend", buildProgressHealth(job));
        node = document.getElementById(`jobId${job.job_id}_progress_health`);
    }
    if (!node) return;
    node.dataset.progressSource = source;
    node.dataset.progressLogfile = progressLogfile;
    renderProgressHealthNode(node, age);
}

function setProgressBar(jobId, key, percentage) {
    const value = progressPercent(percentage);
    const container = document.getElementById(`jobId${jobId}_${key}`);
    const bar = document.getElementById(`jobId${jobId}_${key}_bar`);
    const label = document.getElementById(`jobId${jobId}_${key}_value`);
    if (container) container.setAttribute("aria-valuenow", String(value));
    if (bar) bar.style.width = `${value}%`;
    if (label) label.textContent = `${value.toFixed(1)}%`;
}

function formatStartDateTime(value) {
    const timestamp = Date.parse(value);
    if (!Number.isFinite(timestamp)) return "";
    const date = new Date(timestamp);
    const preferences = document.getElementById("joblist");
    const dateFormat = preferences && preferences.dataset.startDateFormat
        ? preferences.dataset.startDateFormat : "MM/DD/YYYY";
    const timeFormat = preferences && preferences.dataset.startTimeFormat
        ? preferences.dataset.startTimeFormat : "12h";
    const yyyy = String(date.getFullYear());
    const mm = String(date.getMonth() + 1).padStart(2, "0");
    const dd = String(date.getDate()).padStart(2, "0");
    let formattedDate = mm + "/" + dd + "/" + yyyy;
    if (dateFormat === "YYYY-MM-DD") formattedDate = yyyy + "-" + mm + "-" + dd;
    else if (dateFormat === "DD/MM/YYYY") formattedDate = dd + "/" + mm + "/" + yyyy;
    else if (dateFormat === "MM-DD-YYYY") formattedDate = mm + "-" + dd + "-" + yyyy;

    let hours = date.getHours();
    const minutes = String(date.getMinutes()).padStart(2, "0");
    let formattedTime;
    if (timeFormat === "24h") {
        formattedTime = String(hours).padStart(2, "0") + ":" + minutes;
    } else {
        const suffix = hours >= 12 ? "PM" : "AM";
        hours = hours % 12 || 12;
        formattedTime = String(hours) + ":" + minutes + " " + suffix;
    }
    return formattedDate + " " + formattedTime;
}

function transcodingCheck(job) {
    let x = "<div class=\"arm-job-progress-summary\">";
    x += "<div id=\"jobId" + job.job_id + "_progress_details\" class=\"arm-job-progress-details\">";
    x += buildProgressMarkup(job);
    x += buildProgressHealth(job);
    x += "</div>";
    const start = formatStartDateTime(job.start_time);
    if (start) {
        x += "<div class=\"arm-job-progress-times\"><div><strong>Start:</strong> " +
            escapeHtml(start) + "</div>";
    } else {
        x += "<div class=\"arm-job-progress-times\">";
    }
    const elapsed = job.elapsed_seconds === null || job.elapsed_seconds === undefined
        ? 0 : Math.max(0, Number(job.elapsed_seconds) || 0);
    const running = !["success", "fail"].includes(String(job.status || "").toLowerCase());
    const elapsedText = job.job_length && job.job_length !== "None" && !running
        ? job.job_length : formatElapsedSeconds(elapsed);
    x += "<div id=\"jobId" + job.job_id + "_elapsed\"><strong>Elapsed Job Time:</strong> " +
        "<span class=\"arm-elapsed-time\" data-elapsed-seconds=\"" + elapsed +
        "\" data-running=\"" + running + "\">" + escapeHtml(elapsedText) + "</span></div>";
    x += "</div></div>";
    return x;
}
function musicCheck(job, idsplit) {
    let x = "";
    const mediaType = String(job.video_type || "").trim().toLowerCase();
    if (mediaType !== "music") {
        x += `<a href="titlesearch?job_id=${encodeURIComponent(idsplit[1])}" class="btn btn-primary">Title Search</a>
             <a href="customTitle?job_id=${encodeURIComponent(idsplit[1])}" class="btn btn-primary">Custom Title</a>
             <a href="changeparams?config_id=${encodeURIComponent(idsplit[1])}" class="btn btn-primary">Edit Settings</a>`;
    }
    if (mediaType === "movie" || mediaType === "unknown" || mediaType === "") {
        const params = new URLSearchParams({
            job_id: String(idsplit[1]),
            type: job.video_type || "movie",
            season_number: job.season_number || "",
            disc_number: job.disc_number || "",
            episode_start: job.episode_start || "",
            episode_end: job.episode_end || "",
            special_features: "1",
            special_features_auto: "0",
            metadata_controls: "1"
        });
        x += `<a href="titlesearch?${params.toString()}" class="btn btn-primary">Special Features</a>`;
    }
    return x;
}

function hasDisplayValue(value) {
    const normalized = String(value === null || value === undefined ? "" : value).trim().toLowerCase();
    return normalized !== "" && !["none", "null", "undefined", "n/a"].includes(normalized);
}

function posterMarkup(url, alt, imageId, className) {
    const source = hasDisplayValue(url) ? String(url) : "/static/img/none.png";
    return `<img id="${imageId}" alt="${escapeHtml(alt)}" src="${escapeHtml(source)}" class="img-thumbnail ${className}" loading="lazy">`;
}

function posterCheck(job) {
    const hasPoster = hasDisplayValue(job.poster_url);
    const fallback = String(job.video_type || "").toLowerCase() === "music" ? "/static/img/music.png" : "/static/img/none.png";
    return posterMarkup(hasPoster ? job.poster_url : fallback,
        hasPoster ? `Poster for ${job.title || "media"}` : "No poster available",
        `jobId${job.job_id}_poster_url`, "arm-job-poster");
}

function featureSummaryMarkup(job, secondary) {
    const title = secondary ? job.secondary_title : job.title;
    const year = secondary ? job.secondary_year : job.year;
    const type = secondary ? job.secondary_video_type : job.video_type;
    const poster = secondary ? job.secondary_poster_url : job.poster_url;
    const plot = secondary ? job.secondary_plot : job.plot;
    const imageId = secondary ? `jobId${job.job_id}_secondary_poster_url` : `jobId${job.job_id}_poster_url`;
    const titleId = secondary ? `jobId${job.job_id}_secondary_title` : `jobId${job.job_id}_feature_a_title`;
    const label = secondary ? "Feature B" : "Feature A";
    return `<article class="arm-job-feature-summary" aria-label="${label}">
        <div class="arm-job-feature-label">${label}</div>
        ${posterMarkup(poster, `Poster for ${title || label}`, imageId, "arm-job-feature-poster")}
        <h3 id="${titleId}" class="arm-job-feature-title">${escapeHtml(hasDisplayValue(title) ? title : "Title not set")}</h3>
        <div class="arm-job-feature-subtitle">${escapeHtml(type || "Media")}${hasDisplayValue(year) ? ` · ${escapeHtml(year)}` : ""}</div>
        <p class="arm-job-feature-plot">${escapeHtml(hasDisplayValue(plot) ? plot : "No plot available.")}</p>
    </article>`;
}

function titleParts(job) {
    const manualTitle = job.title_manual && job.title_manual !== "None" ? job.title_manual : job.title;
    const rawTitle = hasDisplayValue(manualTitle) ? String(manualTitle).trim() : "";
    const title = ["undefined", "unknown", "not identified", "video", "dvd", "disc", "disk", "untitled"].includes(rawTitle.toLowerCase())
        ? "Title not set" : (rawTitle || "Title not set");
    return {
        title: title,
        year: hasDisplayValue(job.year) ? String(job.year) : "",
        secondaryTitle: hasDisplayValue(job.secondary_title) ? String(job.secondary_title).trim() : "",
        secondaryYear: hasDisplayValue(job.secondary_year) ? String(job.secondary_year) : ""
    };
}

function titleManual(job) {
    const parts = titleParts(job);
    return parts.title + (parts.year ? " (" + parts.year + ")" : "") +
        (parts.secondaryTitle ? " + " + parts.secondaryTitle +
        (parts.secondaryYear ? " (" + parts.secondaryYear + ")" : "") : "");
}

function titleHeaderMarkup(job) {
    const parts = titleParts(job);
    let markup = "<div class=\"arm-job-title-line\"><span class=\"arm-job-title-name\">" +
        escapeHtml(parts.title) + "</span>" +
        "<span class=\"arm-job-title-year\">" + escapeHtml(parts.year) + "</span></div>";
    if (parts.secondaryTitle) {
        markup += "<div class=\"arm-job-title-line arm-job-title-secondary-line\">" +
            "<span class=\"arm-job-title-name\">+ " + escapeHtml(parts.secondaryTitle) + "</span>" +
            "<span class=\"arm-job-title-year\">" + escapeHtml(parts.secondaryYear) + "</span></div>";
    }
    return markup;
}

function buildMiddleSection(job, includeProgress = true) {
    let x = "<div class=\"arm-job-info-column\"><div class=\"card-body px-2 py-2\">";
    x += "<div id=\"jobId" + job.job_id + "_video_type\"><strong>Type: </strong>" +
        escapeHtml(mediaTypeLabel(job.video_type)) + "</div>";
    x += "<div id=\"jobId" + job.job_id + "_devpath\"><strong>Device: </strong>" +
        escapeHtml(job.display_device || job.devpath || "—") + "</div>";
    x += "<div id=\"jobId" + job.job_id + "_disc_metadata\" class=\"arm-job-metadata\">" +
        buildDiscMetadataBadges(job) + "</div>";
    const stage = job.stage || (job.status === "ripping" ? "Reading disc" : "Working");
    x += "<div class=\"arm-rip-status-stage-line\">";
    x += "<div class=\"arm-rip-status\"><strong>Status: </strong>" +
        "<img id=\"jobId" + job.job_id + "_status\" class=\"arm-job-status-icon\" " +
        "src=\"/static/img/" + escapeHtml(job.status) + ".png\" width=\"20\" height=\"20\" " +
        "alt=\"" + escapeHtml(job.status) + "\" title=\"" + escapeHtml(job.status) + "\"></div>";
    x += "<div id=\"jobId" + job.job_id + "_stage\" class=\"arm-rip-stage\"><strong>Stage: </strong>" +
        escapeHtml(stage) + "</div></div>";
    if (includeProgress) {
        x += "<div id=\"jobId" + job.job_id + "_progress_section\" class=\"arm-job-progress-section\">" +
            transcodingCheck(job) + "</div>";
    }
    x += "</div></div>";
    return x;
}

function buildRightSection(job, idsplit) {
    const config = job.config && typeof job.config === "object" ? job.config : {};
    const settings = job.card_settings && typeof job.card_settings === "object" ? job.card_settings : {};
    const visibilityKeys = [
        "show_job_ripper", "show_job_rip_method", "show_job_main_feature",
        "show_job_min_length", "show_job_max_length"
    ];
    const anyConfigVisible = visibilityKeys.some(key => settings[key] !== false);
    const fieldDisplay = key => settings[key] === false ? ' style="display:none;"' : "";
    let x = `<div class="arm-job-actions-column"><div class="card-body px-2 py-1 arm-job-config"${anyConfigVisible ? "" : ' style="display:none;"'}>`;
    x += `<div id="jobId${job.job_id}_RIPPER"${fieldDisplay("show_job_ripper")}><strong>Ripper: </strong>${escapeHtml(getRipperName(job, idsplit))}</div>`;
    x += `<div id="jobId${job.job_id}_RIPMETHOD"${fieldDisplay("show_job_rip_method")}><strong>Rip Method: </strong>${escapeHtml(config.RIPMETHOD || "—")}</div>`;
    x += `<div id="jobId${job.job_id}_MAINFEATURE"${fieldDisplay("show_job_main_feature")}><strong>Main Feature: </strong>${escapeHtml(config.MAINFEATURE || "False")}</div>`;
    x += `<div id="jobId${job.job_id}_MINLENGTH"${fieldDisplay("show_job_min_length")}><strong>Min Length: </strong>${escapeHtml(config.MINLENGTH || "0")}</div>`;
    x += `<div id="jobId${job.job_id}_MAXLENGTH"${fieldDisplay("show_job_max_length")}><strong>Max Length: </strong>${escapeHtml(config.MAXLENGTH || "—")}</div>`;
    x += "</div></div>";
    return x;
}

function buildJobActions(job, idsplit, authenticated, serverJob) {
    if (authenticated !== true) return "";
    const hidden = serverJob ? ' style="display:none;"' : "";
    const jobId = encodeURIComponent(idsplit[1]);
    let x = `<div class="arm-job-actions"><div class="btn-group-vertical w-100" role="group" aria-label="Job actions"${hidden}>`;
    x += `<button type="button" class="btn btn-danger" data-toggle="modal" data-target="#exampleModal" data-type="abandon" data-jobid="${jobId}" data-cardid="${escapeHtml(job.job_id)}" data-href="json?job=${jobId}&mode=abandon">Abandon Job</button>`;
    x += `<a href="logs?logfile=${encodeURIComponent(job.logfile || "")}&mode=full" class="btn btn-outline-primary">View logfile</a>`;
    x += musicCheck(job, idsplit);
    x += `<button type="button" class="btn btn-outline-secondary" data-toggle="modal" data-target="#exampleModal" data-type="fixperms" data-jobid="${jobId}" data-href="json?mode=fixperms&job=${jobId}">Fix Permissions</button>`;
    x += "</div></div>";
    return x;
}

function updateModal(modal, modalTitle = "", modalBody = "") {
    switch (actionType) {
        case "abandon":
            modalTitle = "Abandon This Job ?";
            modalBody = "This item will be set to abandoned. You cannot set it back to active! Are you sure?";
            break;
        case "delete":
            modalTitle = "Delete this job forever ?";
            modalBody = "This item will be permanently deleted and cannot be recovered. Are you sure?";
            break;
        case "fixperms":
            modalTitle = "Try to fix this jobs folder permissions ?";
            modalBody = "This will try to set the chmod values from your arm.yaml. It wont always work, you may need to do this manually";
            break;
        case "search":
            modalTitle = "Search the database";
            modalBody = `<div class="input-group mb-3"><div class="input-group-prepend"><span class="input-group-text" id="searchlabel">Search </span></div>
                       <input type="text" class="form-control" id="searchquery" aria-label="searchquery" name="searchquery" placeholder="Search...."
                       value="" aria-describedby="searchlabel"><div id="validationServer03Feedback" class="invalid-feedback">Search string too short.</div></div>`;
            break;
        default:
            modalTitle = "Do you want to leave this page ?";
            modalBody = "To view the log file you need to leave this page. Would you like to leave ?";
    }
    modal.find(".modal-title").text(modalTitle);
    modal.find(".modal-body").html(modalBody);
}


function hideModal() {
    $('#exampleModal').modal('hide');
    $('#message1').removeClass('d-none');
    $('#message2').addClass('d-none');
    $('#message3').addClass('d-none');
}

function pingReadNotify(toastId) {
    $.ajax({
        url: "/json?mode=read_notification&notify_id=" + toastId,
        type: "get",
        timeout: 2000,
        success: function (data) {
            console.log(data)
        }
    });
}

function notificationBodyMarkup(body) {
    const raw = String(body === null || body === undefined ? "" : body);
    const marker = raw.match(/\[View log:([^\]\r\n]+?\.log)\]/i);
    let markup = escapeHtml(raw);
    if (marker) {
        const filename = marker[1].trim();
        if (filename && filename.indexOf("/") === -1 && filename.indexOf(String.fromCharCode(92)) === -1) {
            const action = `<a class="btn btn-sm btn-outline-primary arm-toast-action" href="logs?logfile=${encodeURIComponent(filename)}&amp;mode=full">View log</a>`;
            markup = markup.replace(escapeHtml(marker[0]), action);
        }
    }
    return markup.replace(/\r?\n/g, "<br>");
}

function addToast(title, body, toastId) {
    const toastTimeout = Math.max(2500, parseInt(getNotifyTimeout(), 10) || 6500);
    const hasLogAction = /\[View log:[^\]\r\n]+?\.log\]/i.test(String(body || ""));
    const icon = /fail|error|stalled|asleep/i.test(String(title || "")) ? "fail.png" : "info.png";
    const toast = `<div id="toast${toastId}" class="toast arm-toast" role="status" aria-live="polite" aria-atomic="true" data-autohide="${hasLogAction ? "false" : "true"}" data-animation="true" data-delay="${toastTimeout}">
        <div class="toast-header">
            <img src="/static/img/${icon}" class="rounded mr-2" alt="" height="18" width="18">
            <strong class="mr-auto">${escapeHtml(title)}</strong>
            <small class="text-muted">just now</small>
            <button type="button" class="ml-2 mb-1 close" data-dismiss="toast" aria-label="Dismiss notification">
                <span aria-hidden="true">&times;</span>
            </button>
        </div>
        <div class="toast-body">${notificationBodyMarkup(body)}</div>
    </div>`;
    $("#toastHolder").append(toast);
    const newToast = $(`#toast${toastId}`);
    newToast.toast("show");
    newToast.on("click", ".arm-toast-action", function () {
        pingReadNotify(toastId);
    });
    newToast.on("hidden.bs.toast", function () {
        pingReadNotify(toastId);
    });
}

// Cache the timeout setting. The old asynchronous request always returned the default
// value immediately, before the configured timeout had arrived.
let cachedNotifyTimeout = 6500;
let notifyTimeoutRequested = false;

function getNotifyTimeout() {
    if (!notifyTimeoutRequested) {
        notifyTimeoutRequested = true;
        $.ajax({
            url: "/json?mode=notify_timeout",
            type: "get",
            timeout: 2000,
            success: function (data) {
                const configured = parseInt(data.notify_timeout, 10);
                if (Number.isFinite(configured) && configured >= 1000) {
                    cachedNotifyTimeout = configured;
                }
            },
            error: function () {
                notifyTimeoutRequested = false;
            }
        });
    }
    return cachedNotifyTimeout;
}
