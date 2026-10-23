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

function getRipperName(job, idsplit) {
    let ripperName;
    if (job.ripper) {
        ripperName = job.ripper;
    } else {
        if (idsplit[0] === "0") {
            ripperName = "Local";
        } else {
            ripperName = "";
        }
    }
    return ripperName;
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
    if (job.status === "transcoding" && job.stage !== "" && job.progress || job.disctype === "music" && job.stage !== "") {
        x += `<div id="jobId${job.job_id}_stage"><strong>Stage: </strong>${job.stage}</div>`;
        x += `<div id="jobId${job.job_id}_progress" >`;
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
    // YYYY-MM-DD
    const d = new Date(Date.parse(job.start_time));
    const datestring = `${d.getFullYear()}-${d.getMonth() + 1}-${d.getDate()}`

    x += `<strong>Start Date:</strong> ${datestring}<br>`;
    x += `<strong>Start Time:</strong> ${d.getHours().toString().padStart(2, '0')}:${d.getMinutes().toString().padStart(2, '0')}<br>`;
    x += `<strong>Job Time:</strong> ${job.job_length === undefined ? "Ongoing" : job.job_length}<br>`;
    return x;
}

function musicCheck(job, idsplit) {
    let x = "";
    if (job.video_type !== "Music") {
        x = `<a href="titlesearch?job_id=${idsplit[1]}" class="btn btn-primary">Title Search</a>
             <a href="customTitle?job_id=${idsplit[1]}" class="btn btn-primary">Custom Title</a>
             <a href="changeparams?config_id=${idsplit[1]}" class="btn btn-primary">Edit Settings</a>`;
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
    let x;
    if (job.title_manual !== "None") {
        x = `${job.title_manual}(${job.year})`;
    } else {
        x = `${job.title}(${job.year})`;
    }
    return x;
}

function buildMiddleSection(job) {
    let x = "<div class=\"arm-job-info-column\"><div class=\"card-body px-2 py-2\">";
    x += `<div id="jobId${job.job_id}_year"><strong>Year: </strong>${job.year}</div>`;
    x += `<div id="jobId${job.job_id}_video_type"><strong>Type: </strong>${job.video_type}</div>`;
    x += `<div id="jobId${job.job_id}_devpath"><strong>Device: </strong>${job.devpath}</div>`;
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
    let x = "<div class=\"arm-job-actions-column\"><div class=\"card-body px-2 py-2\">";
    x += `<div id="jobId${job.job_id}_RIPPER"><strong>Ripper: </strong>${getRipperName(job, idsplit)}</div>`;
    x += `<div id="jobId${job.job_id}_RIPMETHOD"><strong>Rip Method: </strong>${job.config.RIPMETHOD}</div>`;
    x += `<div id="jobId${job.job_id}_MAINFEATURE"><strong>Main Feature: </strong>${job.config.MAINFEATURE}</div>`;
    x += `<div id="jobId${job.job_id}_MINLENGTH"><strong>Min Length: </strong>${job.config.MINLENGTH}</div>`;
    x += `<div id="jobId${job.job_id}_MAXLENGTH"><strong>Max Length: </strong>${job.config.MAXLENGTH}</div>`;
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
