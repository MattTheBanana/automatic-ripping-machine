"""
ARM route blueprint for jobs pages
Covers
- jobdetail [GET]
- jobdetailload [POST]
- titlesearch [GET]
- custometitle [GET]
- gettitle / customtitle [GET]
- updatetitle [GET]
- activerips [GET]
- changeparams [GET]
- list_titles [GET]
- json [JSON GET]
"""

import re
from flask_login import LoginManager, login_required, current_user  # noqa: F401
from flask import render_template, request, Blueprint, flash, redirect, url_for
from werkzeug.routing import ValidationError

import arm.ui.utils as ui_utils
from arm.ui import app, db, constants
from arm.models.job import Job, JobState
from arm.models.notifications import Notifications
from arm.ui.forms import TitleSearchForm, ChangeParamsForm, TrackFormDynamic
from arm.media_metadata import (detect_disc_metadata, is_generic_disc_title, parse_media_label, safe_positive_int)

route_jobs = Blueprint('route_jobs', __name__,
                       template_folder='templates',
                       static_folder='../static')

_DISC_METADATA_FIELDS = ("season_number", "disc_number", "episode_start", "episode_end")


def _disc_metadata_values(job, params=None):
    detected = detect_disc_metadata(
        getattr(job, "label", None), getattr(job, "title", None), getattr(job, "title_auto", None)
    )
    values = {}
    explicit_form = params is not None and params.get("metadata_controls")
    for field in _DISC_METADATA_FIELDS:
        submitted = params is not None and field in params and (params.get(field) != "" or explicit_form)
        if submitted:
            raw_value = params.get(field)
        else:
            raw_value = getattr(job, field, None)
            if raw_value in (None, ""):
                raw_value = detected.get(field)
        maximum = 99 if field in ("season_number", "disc_number") else 999
        values[field] = safe_positive_int(raw_value, maximum)
    start, end = values["episode_start"], values["episode_end"]
    if start and end and end < start:
        values["episode_start"], values["episode_end"] = end, start
    side = params.get("disc_side") if params is not None and "disc_side" in params else getattr(job, "disc_side", None)
    side = str(side or "").strip().upper()
    values["disc_side"] = side if side in ("A", "B") else None
    return values


def _metadata_query_args(values):
    args = {field: ("" if values.get(field) is None else str(values[field]))
            for field in _DISC_METADATA_FIELDS}
    args["disc_side"] = values.get("disc_side") or ""
    return args


def _special_features_values(job, params=None, media_type=None, metadata_values=None):
    """Resolve automatic Disc 2 special-feature selection or an explicit user override."""
    params = params or {}
    auto_value = params.get("special_features_auto")
    if auto_value is None:
        automatic = bool(getattr(job, "special_features_auto", True))
    else:
        automatic = str(auto_value).strip().lower() not in ("0", "false", "no", "off")
    feature_value = params.get("special_features")
    if feature_value is None:
        selected = bool(getattr(job, "special_features", False))
    else:
        selected = str(feature_value).strip().lower() in ("1", "true", "yes", "on")

    if metadata_values is None:
        metadata_values = _disc_metadata_values(job, params)
    disc_number = metadata_values.get("disc_number")
    normalized_type = str(media_type or getattr(job, "video_type", "") or "").strip().lower()
    is_movie = normalized_type == "movie"
    known_non_movie = normalized_type not in ("", "movie", "unknown", "none", "not identified")
    if automatic:
        selected = is_movie and disc_number == 2
    if known_non_movie:
        selected = False
    return {"special_features": bool(selected), "special_features_auto": bool(automatic)}


def _save_disc_metadata(job, values, feature_values=None):
    for field in _DISC_METADATA_FIELDS:
        setattr(job, field, values.get(field))
    job.disc_side = values.get("disc_side")
    if feature_values is not None:
        job.special_features = bool(feature_values.get("special_features", False))
        job.special_features_auto = bool(feature_values.get("special_features_auto", True))


def _label_title_year(job):
    parsed = parse_media_label(getattr(job, "label", None))
    current_title = str(getattr(job, "title", "") or "").strip()
    label = str(getattr(job, "label", "") or "").strip()
    if (not current_title or current_title == label or
            is_generic_disc_title(current_title)):
        title = parsed.get("title") or ""
    else:
        title = current_title
    if is_generic_disc_title(title):
        title = ""
    year = getattr(job, "year", None) or parsed.get("year") or ""
    return title, year


_FEATURE_FIELDS = ("title", "year", "type", "poster", "imdbID", "tmdbID", "plot")


def _enabled(value):
    return str(value or "").strip().lower() in ("1", "true", "yes", "on")


def _feature_from_params(params, prefix):
    """Read one selected metadata result using a stable, prefix-based query shape."""
    return {field: str(params.get(f"{prefix}_{field}", "") or "").strip()
            for field in _FEATURE_FIELDS}


def _feature_query_args(feature, prefix):
    return {f"{prefix}_{field}": feature.get(field, "") or ""
            for field in _FEATURE_FIELDS}


def _same_feature(first, second):
    first_id = first.get("tmdbID") or first.get("imdbID")
    second_id = second.get("tmdbID") or second.get("imdbID")
    if first_id and second_id:
        return first_id.casefold() == second_id.casefold()
    normalize = lambda value: re.sub(r"[^a-z0-9]", "", str(value or "").casefold())
    return normalize(first.get("title")) == normalize(second.get("title")) and (
        first.get("year") or ""
    ) == (second.get("year") or "")


@route_jobs.route('/jobdetail')
@login_required
def jobdetail():
    """
    Page for showing in-depth details about a job

    Shows Job/Config/Track class details
    displays them in a clear and easy to ready format
    """
    manual_edit = False

    # Initialise form
    track_form = TrackFormDynamic()

    job_id = request.args.get('job_id')
    if (job := Job.query.get(job_id)) is None:
        raise ValueError('Job not found')

    # Check if a manual job, waiting for input and user has not provided input
    if job.manual_mode and job.status == JobState.MANUAL_WAIT_STARTED.value and not job.manual_start:
        manual_edit = True

    # Get Job and Track data
    tracks = job.tracks.all()
    track_form.track_ref.min_entries = len(tracks)
    app.logger.debug(f"Found [{len(tracks)}] tracks")
    track_form.track_ref.entries.clear()
    # Loop through each track entry and build the WTForms dynamically
    for track_row in tracks:
        track_form.track_ref.append_entry({'track_ref': track_row.track_id,
                                           'checkbox': track_row.process})
    # For Jobs that are not waiting and in manual mode, disable the process checkbox
    if not manual_edit:
        for entry in track_form.track_ref.entries:
            entry.checkbox.render_kw = {'disabled': 'disabled'}

    search_results = ui_utils.metadata_selector("get_details", job.title, job.year, job.imdb_id)

    if search_results and 'Error' not in search_results:
        job.plot = search_results['Plot'] if 'Plot' in search_results else "There was a problem getting the plot"
        job.background = search_results['background_url'] if 'background_url' in search_results else None

    return render_template('jobdetail.html',
                           jobs=job,
                           tracks=tracks,
                           s=search_results,
                           manual_edit=manual_edit,
                           form=track_form)


@route_jobs.route('/jobdetailload', methods=['POST'])
@login_required
def jobdetail_load():
    """
    Process updated track ID fields against a job and load to the ARM database if valid
    All data passed via POST
    """
    # Initialise form
    track_form = TrackFormDynamic()

    job_id = request.args.get('job_id')
    job = Job.query.get(job_id)

    # Data passed back from webpage, process and update track fields
    if request.method == 'POST' and track_form.validate_on_submit():
        app.logger.debug(f"Job id [{job.job_id}]")
        app.logger.debug(f"Returned [{len(track_form.track_ref.entries)}] tracks")
        for track_row in track_form.track_ref.entries:
            # app.logger.debug(f"Track deets [{track_row}]")
            track_id = track_row.data['track_ref']
            checkbox_value = track_row.data['checkbox']
            app.logger.debug(f"Setting [{track_id}] to [{checkbox_value}]")

            db_track = job.tracks.filter_by(track_id=track_id).first()
            if db_track:
                db_track.process = checkbox_value
                db.session.commit()

        # Set job to ready
        job.manual_start = True
        db.session.commit()
        app.logger.debug(f"Setting [{job.job_id}] to [{job.manual_start}], lets get ripping")
        flash("Tracks was updated", "success")

    return redirect(url_for('route_jobs.jobdetail', job_id=job_id))


@route_jobs.route('/titlesearch')
@login_required
def title_search():
    """Search metadata for movies and TV series."""
    job_id = request.args.get("job_id")
    job = Job.query.get(job_id)
    if job is None:
        raise ValidationError(constants.NO_JOB)
    form = TitleSearchForm(request.args)
    suggested_title, suggested_year = _label_title_year(job)
    metadata_values = _disc_metadata_values(job, request.args)
    media_type = request.args.get("type") or job.video_type
    feature_values = _special_features_values(job, request.args, media_type, metadata_values)
    double_feature = _enabled(request.args.get("double_feature"))
    if form.validate():
        title = request.args.get("title", "").strip()
        year = request.args.get("year", "").strip()
        query_args = {
            "title": title, "year": year, "job_id": job_id,
            **_metadata_query_args(metadata_values), **feature_values, "type": media_type,
            "metadata_controls": "1",
        }
        if double_feature:
            query_args["double_feature"] = "1"
        return redirect(url_for("route_jobs.list_titles", **query_args))
    return render_template("titlesearch.html", title="Search metadata", form=form, job=job,
                           suggested_title=suggested_title, suggested_year=suggested_year,
                           media_type=media_type, double_feature=double_feature,
                           **metadata_values, **feature_values)


@route_jobs.route('/customTitle')
@login_required
def customtitle():
    """Manually set title/year with optional season, disc and episode mapping."""
    job_id = request.args.get("job_id")
    ui_utils.job_id_validator(job_id)
    job = Job.query.get(job_id)
    if job is None:
        raise ValidationError("Job not found")
    form = TitleSearchForm(obj=job)
    suggested_title, suggested_year = _label_title_year(job)
    metadata_values = _disc_metadata_values(job, request.args)
    media_type = request.args.get("type") or job.video_type
    feature_values = _special_features_values(job, request.args, media_type, metadata_values)
    title = request.args.get("title", "").strip()
    if title:
        old_title, old_year = job.title, job.year
        new_title = ui_utils.clean_for_filename(title)
        new_year = request.args.get("year") or None
        same_title = re.sub(r"[^a-z0-9]", "", new_title.casefold()) == re.sub(
            r"[^a-z0-9]", "", str(job.title or "").casefold()
        )
        imdb_id, tmdb_id = ui_utils.resolve_media_ids(
            new_title, new_year,
            request.args.get("imdbID") or (job.imdb_id if same_title else None),
            request.args.get("tmdbID") or (job.tmdb_id if same_title else None),
            media_type
        )
        _save_disc_metadata(job, metadata_values, feature_values)
        update_values = {
            "title": new_title, "title_manual": new_title, "year": new_year, "year_manual": new_year,
            "imdb_id": imdb_id, "imdb_id_manual": imdb_id, "tmdb_id": tmdb_id,
            "hasnicetitle": True, "special_features": feature_values["special_features"],
            "secondary_title": None, "secondary_year": None, "secondary_video_type": None,
            "secondary_imdb_id": None, "secondary_tmdb_id": None,
            "secondary_poster_url": None, "secondary_plot": None,
        }
        if request.args.get("type"):
            update_values.update({"video_type": media_type, "video_type_manual": media_type})
        ui_utils.database_updater(update_values, job)
        db.session.add(Notifications(
            f"Job: {job.job_id} was updated",
            f"Title: {old_title} ({old_year}) was updated to {new_title} ({new_year})"
        ))
        db.session.commit()
        flash(f"Custom title changed. Title={job.title}, Year={job.year}.", "success")
        return redirect(url_for("home"))
    return render_template("customTitle.html", title="Change Title", form=form, job=job,
                           suggested_title=suggested_title, suggested_year=suggested_year,
                           media_type=media_type, **metadata_values, **feature_values)


@route_jobs.route('/gettitle')
@route_jobs.route('/select_title')
@login_required
def gettitle():
    """Display the selected metadata record, movie or series."""
    imdb_id = request.args.get("imdbID", "").strip() or None
    tmdb_id = request.args.get("tmdbID", "").strip() or None
    job_id = request.args.get("job_id", "").strip()
    if not job_id:
        flash(constants.NO_JOB, "danger")
        raise ValidationError(constants.NO_JOB)
    job = Job.query.get(job_id)
    if job is None:
        raise ValidationError("Job not found")
    if imdb_id:
        details = ui_utils.metadata_selector("get_details", None, None, imdb_id)
    elif tmdb_id:
        details = ui_utils.tmdb_details(tmdb_id, request.args.get("type", "movie"))
    else:
        flash("No provider ID was supplied for this result", "danger")
        return redirect(url_for("route_jobs.title_search", job_id=job_id))
    if not details:
        flash("Could not retrieve metadata for the selected title", "danger")
        return redirect(url_for("route_jobs.title_search", job_id=job_id))
    metadata_values = _disc_metadata_values(job, request.args)
    media_type = details.get("Type") or request.args.get("type") or job.video_type
    feature_values = _special_features_values(job, request.args, media_type, metadata_values)
    return render_template("showtitle.html", results=details, job_id=job_id,
                           media_type=media_type, **metadata_values, **feature_values)


@route_jobs.route('/updatetitle')
@login_required
def updatetitle():
    """Persist the selected movie/show, identifiers, and explicit episode metadata."""
    job_id = request.args.get("job_id")
    job = Job.query.get(job_id)
    if job is None:
        raise ValidationError("Job not found")
    old_title, old_year = job.title, job.year
    title = request.args.get("title", "").strip()
    if not title:
        flash("A title is required", "danger")
        return redirect(url_for("route_jobs.title_search", job_id=job_id))
    if is_generic_disc_title(title):
        flash("That looks like a generic disc label, not a media title. Enter a real title or choose a search result.", "danger")
        return redirect(url_for("route_jobs.title_search", job_id=job_id))
    new_title = ui_utils.clean_for_filename(title)
    new_year = request.args.get("year") or None
    media_type = request.args.get("type") or job.video_type
    double_feature = _enabled(request.args.get("double_feature"))
    secondary_title = request.args.get("secondary_title", "").strip()
    if double_feature and (not secondary_title or is_generic_disc_title(secondary_title)):
        flash("Choose two valid titles before saving a double feature.", "danger")
        return redirect(url_for("route_jobs.title_search", job_id=job_id))
    imdb_id, tmdb_id = ui_utils.resolve_media_ids(
        new_title, new_year, request.args.get("imdbID"), request.args.get("tmdbID"), media_type
    )
    job.title = job.title_manual = new_title
    job.year = job.year_manual = new_year
    job.video_type = job.video_type_manual = media_type
    job.imdb_id = job.imdb_id_manual = imdb_id
    job.tmdb_id = tmdb_id
    job.poster_url = job.poster_url_manual = request.args.get("poster") or None
    job.plot = request.args.get("plot") or None
    job.hasnicetitle = True
    if double_feature:
        second_type = request.args.get("secondary_type") or media_type
        second_year = request.args.get("secondary_year") or None
        second_imdb, second_tmdb = ui_utils.resolve_media_ids(
            secondary_title, second_year, request.args.get("secondary_imdbID"),
            request.args.get("secondary_tmdbID"), second_type
        )
        job.secondary_title = ui_utils.clean_for_filename(secondary_title)
        job.secondary_year = second_year
        job.secondary_video_type = second_type
        job.secondary_imdb_id = second_imdb
        job.secondary_tmdb_id = second_tmdb
        job.secondary_poster_url = request.args.get("secondary_poster") or None
        job.secondary_plot = request.args.get("secondary_plot") or None
    else:
        job.secondary_title = None
        job.secondary_year = None
        job.secondary_video_type = None
        job.secondary_imdb_id = None
        job.secondary_tmdb_id = None
        job.secondary_poster_url = None
        job.secondary_plot = None
    metadata_values = _disc_metadata_values(job, request.args)
    feature_values = _special_features_values(job, request.args, media_type, metadata_values)
    _save_disc_metadata(job, metadata_values, feature_values)
    db.session.add(Notifications(
        f"Job: {job.job_id} was updated",
        f"Title: {old_title} ({old_year}) was updated to {new_title} ({new_year})"
    ))
    db.session.commit()
    flash(f"Title: {old_title} ({old_year}) was updated to {new_title} ({new_year})", "success")
    return redirect("/")


@route_jobs.route('/activerips')
@login_required
def rips():
    """
    This no longer works properly because of the 'transcoding' status
    """
    active_jobs = Job.query.filter_by(~Job.finished)
    return render_template('activerips.html', jobs=active_jobs)


@route_jobs.route('/changeparams')
@login_required
def changeparams():
    """
    For updating Config params or changing/correcting job.disctype manually
    """
    config_id = request.args.get('config_id')
    job = Job.query.get(config_id)
    config = job.config
    form = ChangeParamsForm(obj=config)
    return render_template('changeparams.html', title='Change Parameters', form=form, config=config)


@route_jobs.route('/list_titles')
@login_required
def list_titles():
    """Search-results page for movies and TV series."""
    title = request.args.get("title", "").strip()
    year = request.args.get("year", "").strip()
    job_id = request.args.get("job_id", "").strip()
    if not job_id:
        flash(constants.NO_JOB, "danger")
        raise ValidationError(constants.NO_JOB)
    job = Job.query.get(job_id)
    if job is None:
        raise ValidationError("Job not found")
    form = TitleSearchForm(obj=job)
    metadata_values = _disc_metadata_values(job, request.args)
    media_type = request.args.get("type") or job.video_type
    feature_values = _special_features_values(job, request.args, media_type, metadata_values)
    search_results = ui_utils.metadata_selector("search", title, year)
    if search_results is None or "Error" in search_results or (
            "Search" in search_results and not search_results["Search"]):
        flash(f"No search results found for {title} ({year}); trying without year", "danger")
        search_results = ui_utils.metadata_selector("search", title, "")
    if search_results is None or "Error" in search_results or (
            "Search" in search_results and not search_results["Search"]):
        flash(f"No search results found for {title}", "danger")
        search_results = {"Search": []}
    suggested_title, suggested_year = _label_title_year(job)
    double_feature = _enabled(request.args.get("double_feature"))
    feature_a = _feature_from_params(request.args, "feature_a")
    feature_b = _feature_from_params(request.args, "feature_b")
    selected_slot = str(request.args.get("select_feature") or "").strip().upper()
    if double_feature and selected_slot in ("A", "B"):
        chosen = _feature_from_params(request.args, "choice")
        other = feature_b if selected_slot == "A" else feature_a
        if is_generic_disc_title(chosen["title"]):
            flash("Choose a real movie or series title for each feature.", "danger")
        elif other.get("title") and _same_feature(chosen, other):
            flash("Feature A and Feature B must be different titles.", "danger")
        elif selected_slot == "A":
            feature_a = chosen
        else:
            feature_b = chosen
    return render_template("list_titles.html", results=search_results, job_id=job_id, form=form,
                           title=title or suggested_title, year=year or suggested_year,
                           suggested_title=suggested_title, suggested_year=suggested_year,
                           media_type=media_type, double_feature=double_feature,
                           feature_a=feature_a, feature_b=feature_b,
                           **metadata_values, **feature_values)
