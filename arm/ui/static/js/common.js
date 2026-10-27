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

function startElapsedJobClock() {
    if (window.armElapsedJobClockStarted) return;
    window.armElapsedJobClockStarted = true;
    window.setInterval(function () {
        document.querySelectorAll(".arm-elapsed-time[data-running='true']").forEach(function (node) {
            const elapsed = Math.max(0, Number(node.dataset.elapsedSeconds) || 0) + 1;
            node.dataset.elapsedSeconds = String(elapsed);
            node.textContent = formatElapsedSeconds(elapsed);
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
    // Local server or remote.
    const idsplit = String(job.job_id || "").split("_");
    let x = `<div class="col-md-6 col-xl-4 arm-job-column" id="jobId${job.job_id}">`;
    x += `<div class="card arm-job-card mx-auto">`;
    x += `<div class="card-header text-center arm-job-card-header"><strong id="jobId${job.job_id}_header">${titleManual(job)}</strong></div>`;
    x += `<div class="row no-gutters arm-job-card-content">`;
    if (idsplit[1] === undefined) {
        x += `<div class="arm-job-poster-column"><a href="/jobdetail?job_id=${job.job_id}">${posterCheck(job)}</a></div>`;
    } else {
        x += `<div class="arm-job-poster-column"><a href="${job.server_url}/jobdetail?job_id=${idsplit[1]}">${posterCheck(job)}</a></div>`;
    }
    x += buildMiddleSection(job);
    x += buildRightSection(job, idsplit, authenticated);
    // Close the content row, card, and outer grid column.
    x += "</div></div></div>";
    return x;
}

function transcodingCheck(job) {
    let x = "";
    if ((job.status === "transcoding" && job.stage !== "" && job.progress) ||
        (job.disctype === "music" && job.stage !== "")) {
        x += `<div id="jobId${job.job_id}_stage"><strong>Stage: </strong>${job.stage}</div>`;
        x += `<div id="jobId${job.job_id}_progress">`;
        x += `<div class="progress">
                <div class="progress-bar progress-bar-striped progress-bar-animated" role="progressbar"
                aria-valuenow="${job.progress_round}" aria-valuemin="0" aria-valuemax="100"
                style="width: ${job.progress_round}%; background-color: #cbcbcb;">
                    <small class="justify-content-center d-flex position-absolute w-100" style="color: black; z-index: 2;">
                        ${job.progress}%
                    </small>
                </div>
              </div></div>`;
        x += `<div id="jobId${job.job_id}_eta"><strong>ETA: </strong>${job.eta}</div>`;
        x += `<div id="jobId${job.job_id}_cur_fps"><strong>CUR FPS: </strong>${job.cur_fps}</div>`;
        x += `<div id="jobId${job.job_id}_avg_fps"><strong>AVG FPS: </strong>${job.avg_fps}</div>`;
    }
    const start = Date.parse(job.start_time);
    const startValid = Number.isFinite(start);
    if (startValid) {
        const d = new Date(start);
        const datestring = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
        x += `<div><strong>Start:</strong> ${datestring} ${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}</div>`;
    }
    const elapsed = job.elapsed_seconds === null || job.elapsed_seconds === undefined
        ? 0 : Math.max(0, Number(job.elapsed_seconds) || 0);
    const running = !["success", "fail"].includes(String(job.status || "").toLowerCase());
    const elapsedText = job.job_length && job.job_length !== "None" && !running
        ? job.job_length : formatElapsedSeconds(elapsed);
    x += `<div id="jobId${job.job_id}_elapsed"><strong>Elapsed Job Time:</strong> <span class="arm-elapsed-time" data-elapsed-seconds="${elapsed}" data-running="${running}">${elapsedText}</span></div>`;
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

function posterCheck(job) {
    let image;
    if (job.poster_url !== "None" && job.poster_url !== "N/A") {
        return `<img id="jobId${job.job_id}_poster_url" alt="Poster thumbnail" src="${job.poster_url}" class="img-thumbnail arm-job-poster" loading="lazy">`;
    }
    image = job.video_type === "Music" ? "music.png" : "none.png";
    return `<img id="jobId${job.job_id}_poster_url" alt="No poster available" src="/static/img/${image}" class="img-thumbnail arm-job-poster" loading="lazy">`;
}

function titleManual(job) {
    const manualTitle = job.title_manual && job.title_manual !== "None" ? job.title_manual : job.title;
    const title = manualTitle && manualTitle !== "None" ? manualTitle : "Unknown title";
    const year = job.year && job.year !== "None" ? ` (${job.year})` : "";
    return `${title}${year}`;
}

function buildMiddleSection(job) {
    let x = "<div class=\"arm-job-info-column\"><div class=\"card-body px-2 py-2\">";
    x += `<div id="jobId${job.job_id}_year"><strong>Year: </strong>${job.year || "—"}</div>`;
    x += `<div id="jobId${job.job_id}_video_type"><strong>Type: </strong>${mediaTypeLabel(job.video_type)}</div>`;
    x += `<div id="jobId${job.job_id}_devpath"><strong>Device: </strong>${escapeHtml(job.display_device || job.devpath || "—")}</div>`;
    x += `<div id="jobId${job.job_id}_disc_metadata" class="arm-job-metadata">${buildDiscMetadataBadges(job)}</div>`;
    x += `<div><strong>Status: </strong><img id="jobId${job.job_id}_status" class="arm-job-status-icon" src="/static/img/${job.status}.png" width="20" height="20" alt="${job.status}" title="${job.status}"></div>`;
    x += `<div id="jobId${job.job_id}_progress_section">${transcodingCheck(job)}</div>`;
    x += "</div></div>";
    return x;
}

function buildRightSection(job, idsplit, authenticated) {
    // idsplit[1] is undefined on the database page; use its local job identifier.
    if (idsplit[1] === undefined) {
        idsplit[0] = "0";
        idsplit[1] = job.job_id;
    }
    const config = job.config && typeof job.config === "object" ? job.config : {};
    const settings = job.card_settings && typeof job.card_settings === "object" ? job.card_settings : {};
    const visibilityKeys = [
        "show_job_ripper", "show_job_rip_method", "show_job_main_feature",
        "show_job_min_length", "show_job_max_length"
    ];
    const anyConfigVisible = visibilityKeys.some(key => settings[key] !== false);
    const fieldDisplay = key => settings[key] === false ? ' style="display:none;"' : "";
    let x = `<div class="arm-job-actions-column"><div class="card-body px-2 py-2 arm-job-config"${anyConfigVisible ? "" : ' style="display:none;"'}>`;
    x += `<div id="jobId${job.job_id}_RIPPER"${fieldDisplay("show_job_ripper")}><strong>Ripper: </strong>${getRipperName(job, idsplit)}</div>`;
    x += `<div id="jobId${job.job_id}_RIPMETHOD"${fieldDisplay("show_job_rip_method")}><strong>Rip Method: </strong>${config.RIPMETHOD || "—"}</div>`;
    x += `<div id="jobId${job.job_id}_MAINFEATURE"${fieldDisplay("show_job_main_feature")}><strong>Main Feature: </strong>${config.MAINFEATURE || "False"}</div>`;
    x += `<div id="jobId${job.job_id}_MINLENGTH"${fieldDisplay("show_job_min_length")}><strong>Min Length: </strong>${config.MINLENGTH || "0"}</div>`;
    x += `<div id="jobId${job.job_id}_MAXLENGTH"${fieldDisplay("show_job_max_length")}><strong>Max Length: </strong>${config.MAXLENGTH || "—"}</div>`;
    x += "</div><div class=\"card-body px-2 py-1 arm-job-actions\">";
    if (authenticated === true) {
        x += `<div class="btn-group-vertical w-100" role="group" aria-label="Job actions" ${idsplit[0] !== "0" ? "style=\"display: none;\"" : ""}>`;
        x += `<button type="button" class="btn btn-primary" data-toggle="modal" data-target="#exampleModal" data-type="abandon" data-jobid="${idsplit[1]}" data-href="json?job=${idsplit[1]}&mode=abandon">Abandon Job</button>`;
        x += `<a href="logs?logfile=${job.logfile}&mode=full" class="btn btn-primary">View logfile</a>`;
        x += musicCheck(job, idsplit);
        x += `<button type="button" class="btn btn-primary" data-toggle="modal" data-target="#exampleModal" data-type="fixperms" data-jobid="${idsplit[1]}" data-href="json?mode=fixperms&job=${idsplit[1]}">Fix Permissions</button>`;
        x += "</div>";
    }
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

function addToast(title, body, toastId) {
    // Get the toast timeout from UISettings
    const toast_timeout = getNotifyTimeout();
    console.log("Notification timeout: " + toast_timeout);

    const toast = `<div id="toast${toastId}" class="toast" role="alert" aria-live="assertive" aria-atomic="true" data-autohide="true" data-animation="true" data-delay="${parseInt(toast_timeout)}" style="z-index:1000">
        <div class="toast-header">
            <img src="static/img/success.png" class="rounded mr-2" alt="arm message" height="20px" width="20px">
                <strong class="mr-auto">${title}</strong>
                <small class="text-muted">just now</small>
                <button type="button" class="ml-2 mb-1 close" data-dismiss="toast" aria-label="Close">
                    <span aria-hidden="true">&times;</span>
                </button>
        </div>
        <div class="toast-body">
            ${body}
        </div>
    </div>`;
    $("#toastHolder").append(toast);
    const newToast = $(`#toast${toastId}`);
    newToast.toast('show');
    newToast.on('hidden.bs.toast', function () {
        // do something...
        pingReadNotify(toastId)
    })
}

// Get the toast timeout settings from UI Settings via JSON
function getNotifyTimeout() {
    // initilise notify and set a default of 6.5 seconds
    let notify = 6500;

    $.ajax({
        url: "/json?mode=notify_timeout",
        type: "get",
        timeout: 2000,
        success: function (data) {
            console.log("UI timeout: " + data.notify_timeout);
            notify = data.notify_timeout;
        }
    });

    return notify;
}
