/*jshint multistr: true */
/*jshint esversion: 6 */
/*global $:false, jQuery:false */
/* jshint node: true */
/* jshint strict: false */


let hrrref = "";
let activeJob = null;
let actionType = null;
var activeServers = [];
var activeJobs = [];

$(document).ready(function () {
    pushChildServers();
    refreshJobs();
    activeTab("home");

    $("#save-yes").bind("click", function () {
        console.log(hrrref);
        if (hrrref !== "") {
            // Add the spinner to let them know we are loading
            $("#m-body").append("<div class=\"d-flex justify-content-center\"><div class=\"spinner-border\" role=\"status\">" +
                                "<span class=\"sr-only\">Loading...</span></div></div>");
            $.get(hrrref, function (data) {
                console.log(data.success);
                console.log("#jobId" + activeJob);
                if (data.success && data.mode === "abandon") {
                    $("#id" + activeJob).remove();
                    $("#message1 .alert-heading").html("Job was successfully abandoned");
                    $(MODEL_ID).modal("toggle");
                    $("#message1").removeClass("d-none");
                    setTimeout(
                        function () {
                            $("#message1").addClass("d-none");
                        },
                        5000
                    );
                }
            }, "json");
        }
    });
    $("#save-no").bind("click", function () {
        $(MODEL_ID).modal("toggle");
    });
    $(MODEL_ID).on("show.bs.modal", function (event) {
        const button = $(event.relatedTarget); // Button that triggered the modal
        actionType = button.data("type"); // Extract info from data-* attributes
        hrrref = button.data("href");
        activeJob = button.data("jobid");
        const modal = $(this);
        updateModal(modal);
    });
});

/**
 * Function to update the current progress
 * @param    {Class} job    current job
 * @param    {Class} oldJob    Copy of old job
 */
function updateProgress(job) {
    const details = document.getElementById(`jobId${job.job_id}_progress_details`);
    if (!details) return;
    const isMakeMKV = job.status === "ripping" && job.progress_kind === "makemkv";
    if (isMakeMKV) {
        const currentBar = document.getElementById(`jobId${job.job_id}_current_title_progress_bar`);
        const totalBar = document.getElementById(`jobId${job.job_id}_total_progress_bar`);
        if (!currentBar || !totalBar) {
            details.innerHTML = makeMKVProgressMarkup(job);
        }
        updateContents($(`#jobId${job.job_id}_stage`), job, "Stage", job.stage || "Reading disc");
        const currentTitle = document.getElementById(`jobId${job.job_id}_current_title_progress_title`);
        const totalTitle = document.getElementById(`jobId${job.job_id}_total_progress_title`);
        if (currentTitle) currentTitle.textContent = job.current_title || "Current title";
        if (totalTitle) totalTitle.textContent = job.total_progress_title || "Total disc progress";
        setProgressBar(job.job_id, "current_title_progress",
            job.current_title_progress_round !== undefined ? job.current_title_progress_round : job.progress_round);
        setProgressBar(job.job_id, "total_progress", job.total_progress_round);
        updateContents($(`#jobId${job.job_id}_eta`), job, "ETA for current title", job.eta || "Unknown");
    } else if (checkTranscodeStatus(job)) {
        const progressBar = document.getElementById(`jobId${job.job_id}_progress_bar`);
        const wasMakeMKV = document.getElementById(`jobId${job.job_id}_total_progress_bar`);
        if (!progressBar || wasMakeMKV) {
            details.innerHTML = standardProgressMarkup(job);
        }
        updateContents($(`#jobId${job.job_id}_stage`), job, "Stage", job.stage || "Working");
        setProgressBar(job.job_id, "progress", job.progress_round);
        updateContents($(`#jobId${job.job_id}_eta`), job, "ETA", job.eta || "Unknown");
        const curFpsDiv = $(`#jobId${job.job_id}_cur_fps`);
        const avgFpsDiv = $(`#jobId${job.job_id}_avg_fps`);
        if (job.cur_fps === undefined || job.cur_fps === "-1") curFpsDiv.hide();
        else {
            curFpsDiv.show();
            updateContents(curFpsDiv, job, "CUR FPS", job.cur_fps);
        }
        if (job.avg_fps === undefined || job.avg_fps === "-1") avgFpsDiv.hide();
        else {
            avgFpsDiv.show();
            updateContents(avgFpsDiv, job, "AVG FPS", job.avg_fps);
        }
    } else {
        details.innerHTML = "";
    }
    updateProgressHealth(details, job);
}
/**
 * Checks if current job needs a stage/progress bar added
 * This is enabled for music discs to enable current ripping track in job.stage
 * @param job current job object
 * @returns {boolean} True if job is transcoding or disc is an audio disc
 */
function checkTranscodeStatus(job) {
    let status = false;
    // HandBrake has the disc/files and should be outputting stage and eta
    if (job.status === "transcoding") {
        status = true;
    }
    // MakeMKV has the disc and should be outputting stage and eta
    if (job.status === "ripping" && job.stage !== "" && job.progress) {
        status = true;
    }
    // abcde is ripping the audio disc and is outputting stage and eta
    if (job.disctype === "music" && job.stage !== "") {
        status = true;
    }
    return status;
}

/**
 * Function to check and update the job values
 * @param {jQuery} item    Dom item to update
 * @param {Class} _job    Current job
 * @param {String} keyString    String that pairs with config item for display purposes
 * @param itemContents    item of job class to update
 */
function updateContents(item, _job, keyString, itemContents) {
    if (item[0] === undefined) {
        return false;
    }
    const value = String(itemContents === null || itemContents === undefined ? "" : itemContents);
    const expectedText = `${keyString}: ${value}`;
    if (item[0].innerText.trim() !== expectedText.trim()) {
        const label = document.createElement("b");
        label.textContent = `${keyString}: `;
        item[0].replaceChildren(label, document.createTextNode(value));
    }
    return true;
}

/**
 * Function that goes through the whole job card and updates outdated values
 * @param {Class} oldJob    Old job used to compare against fresh job from api
 * @param {Class} job     Fresh job pulled from api
 */
function updateJobItem(oldJob, job) {
    const cardHeader = $(`#jobId${job.job_id}_header`);
    const posterUrl = $(`#jobId${job.job_id}_poster_url`);
    const status = $(`#jobId${job.job_id}_status`);
    // Keep the title header consistent with manual title overrides and optional year.
    const updatedCardTitle = titleManual(job);
    if (cardHeader[0].innerText !== updatedCardTitle) {
        cardHeader[0].innerText = updatedCardTitle;
    }
    // Update card poster image
    if (job.poster_url !== posterUrl[0].src && job.poster_url !== "None" && job.poster_url !== "N/A") {
        posterUrl[0].src = job.poster_url;
    }
    // Update job status image
    if (job.status !== status[0].title) {
        status[0].src = `static/img/${job.status}.png`;
        status[0].alt = job.status;
        status[0].title = job.status;
    }
    // Go through and update job values as needed
    updateContents($(`#jobId${job.job_id}_year`), job, "Year", job.year);
    updateContents($(`#jobId${job.job_id}_devpath`), job, "Device", job.display_device || job.devpath || "—");
    updateContents($(`#jobId${job.job_id}_video_type`), job, "Type", mediaTypeLabel(job.video_type));
    const metadataNode = document.getElementById(`jobId${job.job_id}_disc_metadata`);
    if (metadataNode) metadataNode.innerHTML = buildDiscMetadataBadges(job);
    const elapsedNode = document.querySelector(`#jobId${job.job_id}_elapsed .arm-elapsed-time`);
    if (elapsedNode && job.elapsed_seconds !== null && job.elapsed_seconds !== undefined) {
        elapsedNode.dataset.elapsedSeconds = String(Math.max(0, Number(job.elapsed_seconds) || 0));
        elapsedNode.dataset.running = String(!["success", "fail"].includes(String(job.status || "").toLowerCase()));
        elapsedNode.textContent = formatElapsedSeconds(elapsedNode.dataset.elapsedSeconds);
    }
    updateProgress(job);
    // Reapply current UI preferences on every refresh so cards already ripping
    // respond immediately when visibility or device-name preferences change.
    const cardSettings = job.card_settings && typeof job.card_settings === "object"
        ? job.card_settings : {};
    const configurableFields = [
        ["RIPPER", "show_job_ripper"],
        ["RIPMETHOD", "show_job_rip_method"],
        ["MAINFEATURE", "show_job_main_feature"],
        ["MINLENGTH", "show_job_min_length"],
        ["MAXLENGTH", "show_job_max_length"]
    ];
    let anyConfigVisible = false;
    configurableFields.forEach(function (field) {
        const node = document.getElementById(`jobId${job.job_id}_${field[0]}`);
        const visible = cardSettings[field[1]] !== false;
        if (node) {
            node.style.display = visible ? "" : "none";
            anyConfigVisible = anyConfigVisible || visible;
        }
    });
    const configSection = document.querySelector(`#jobId${job.job_id} .arm-job-config`);
    if (configSection) configSection.style.display = anyConfigVisible ? "" : "none";

    updateContents($(`#jobId${job.job_id}_RIPPER`), job, "Ripper", getRipperName(job, String(job.job_id).split("_")));
    updateContents($(`#jobId${job.job_id}_RIPMETHOD`), job, "Rip Method", job.config.RIPMETHOD);
    updateContents($(`#jobId${job.job_id}_MAINFEATURE`), job, "Main Feature", job.config.MAINFEATURE || "False");
    updateContents($(`#jobId${job.job_id}_MINLENGTH`), job, "Min Length", job.config.MINLENGTH || "0");
    updateContents($(`#jobId${job.job_id}_MAXLENGTH`), job, "Max Length", job.config.MAXLENGTH || "—");
}

/**
 * Removes a job from the card deck
 * @param {Class} job
 */
function removeJobItem(job) {
    $("#jobId" + job.job_id).remove();
}

/**
 * Function that runs after ajax request completes successfully
 * Will check for inactive jobs and then remove them
 * Then sorts the jobs in ascending order
 */
function refreshJobsComplete() {
    // Loop through all active jobs and remove any that have finished
    // Notes: This breaks when arm child servers are added
    $.each(activeJobs, function (index, job) {
        if (typeof (job) !== "undefined" && !job.active) {
            console.log("Job isn't active:" + job.job_id.split("_")[1]);
            console.log(job)
            removeJobItem(job);
            activeJobs.splice(index, 1);
        }
    });

    $("#joblist .col-md-4").sort(function (a, b) {
        if (a.id === b.id) {
            return 0;
        }
        return (a.id < b.id ? -1 : 1);
    }).each(function () {
        const elem = $(this);
        elem.remove();
        $(elem).appendTo("#joblist");
    });
}

/**
 * Function to check for active jobs from the return from api
 * *** This doesn't work as it should when arm has child links
 * @param data returned data from ajax
 * @param serverIndex current server index count (added to the front of job id's)
 */
function checkActiveJobs(data, serverIndex) {
    // Loop through each active job
    $.each(activeJobs, function (AJIndex) {
        // Turn off job active and re-enable it later if we find it
        activeJobs[AJIndex].active = false;
        // Loop through each result and search for our active job
        $.each(data.results, function (_index, job) {
            console.log(`Looking for ${activeJobs[AJIndex].job_id}!==${serverIndex}_${job.job_id}`)
            // We found a match for the current job id and the active job id
            if (activeJobs[AJIndex].job_id === `${serverIndex}_${job.job_id}`) {
                console.log(`Match found for ${job.job_id}`)
                activeJobs[AJIndex].active = true;
                return false;
            } else {
                console.log(`No match: ${activeJobs[AJIndex].job_id}!==${serverIndex}_${job.job_id}`)
            }
        });
    });
}

/**
 * Function that is run when data is received back from json api
 * @param data all data returned from the ajax request
 * @param serverIndex
 * @param serverUrl the url of the server the job is running on
 * @param serverCount
 * @returns {*}
 */
function refreshJobsSuccess(data, serverIndex, serverUrl, serverCount) {
    checkActiveJobs(data, serverIndex);
    $.each(data.results, function (_index, job) {
        console.log(job.job_id)
        job.job_id = `${serverIndex}_${job.job_id}`;
        job.ripper = (data.arm_name ? data.arm_name : "");
        job.server_url = serverUrl;
        job.active = true;
        if (activeJobs.some(e => e.job_id === job.job_id)) {
            var oldJob = activeJobs.find(e => e.job_id === job.job_id);
            activeJobs[activeJobs.indexOf(oldJob)] = job;
            updateJobItem(oldJob, job);
        } else {
            activeJobs.push(job);
            $("#joblist").append(addJobItem(job, data.authenticated));
        }
        serverCount--;
    });
    return serverCount;
}

function checkNotifications(data) {
    $.each(data.notes, function (notifyIndex, note) {
        if ($(`#toast${note.id}`).length) {
            // Exists.
            console.log("element exists, skipping add");
        }else {
            console.log(note);
            addToast(note.title, note.message, note.id);
        }
    });
}

/**
 * Function set as an interval to update all jobs from api
 */
function refreshJobs() {
    let serverCount = activeServers.length;
    $.each(activeServers, function (serverIndex, serverUrl) {
        $.ajax({
            url: serverUrl + "/json?mode=joblist",
            type: "get",
            cache: false,
            timeout: 2000,
            error: function () {
                --serverCount;
            },
            success: function (data) {
                serverCount = refreshJobsSuccess(data, serverIndex, serverUrl, serverCount);
            },
            complete: function (data) {
                refreshJobsComplete();
                if(typeof data !== 'undefined' && data.responseJSON) {
                    checkNotifications(data.responseJSON);
                }
            }
        });
    });
}

/**
 * Function to push all child servers from arm.yaml config into links on the homepage
 */
function pushChildServers() {
    activeServers.push(location.origin);
    const childs = $("#children");
    const children = childs.text().trim();
    if (children) {
        const childLinks = [];
        const childrenArr = children.split(",");
        $.each(childrenArr, function (_index, value) {
            activeServers.push(value);
            childLinks.push(`<a target="_blank" href="${value}">${value}</a>`);
        });
        childs.html(`Children: <br />${childLinks.join("<br />")}`);
    }
}
