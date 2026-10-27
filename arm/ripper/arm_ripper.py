""" Main file for running DVDs/Blu-rays/CDs/data ?
It would help clear up main and make things easier to find
"""
import sys
import os
import logging
from importlib.util import find_spec
from pathlib import Path

# If the arm module can't be found, add the folder this file is in to PYTHONPATH
# This is a bad workaround for non-existent packaging
if find_spec("arm") is None:
    sys.path.append(str(Path(__file__).parents[2]))

from arm.ripper import utils, makemkv, handbrake, ffmpeg  # noqa E402
from arm.ui import app, db, constants  # noqa E402
from arm.models.job import JobState  # noqa E402
from arm.media_metadata import detect_disc_metadata  # noqa E402


def _apply_disc_feature_defaults(job):
    """Persist label metadata and automatically select movie Disc 2 special features."""
    detected = detect_disc_metadata(
        getattr(job, "label", None),
        getattr(job, "title", None),
        getattr(job, "title_auto", None),
    )
    for field in ("season_number", "disc_number", "episode_start", "episode_end"):
        if getattr(job, field, None) is None and detected.get(field) is not None:
            setattr(job, field, detected[field])

    if getattr(job, "special_features_auto", True):
        job.special_features = (
            str(getattr(job, "video_type", "") or "").strip().lower() == "movie"
            and getattr(job, "disc_number", None) == 2
        )
    elif str(getattr(job, "video_type", "") or "").strip().lower() not in ("", "movie", "unknown", "none"):
        job.special_features = False
    db.session.commit()


def _prepare_output_paths(have_dupes, job, type_sub_folder, job_title):
    """Build output paths while treating special-feature discs as part of their movie."""
    is_special_features = (
        bool(getattr(job, "special_features", False)) and str(job.video_type or "").lower() == "movie"
    )
    transcode_out_path = os.path.join(job.config.TRANSCODE_PATH, type_sub_folder, job_title)
    final_directory = os.path.join(job.config.COMPLETED_PATH, type_sub_folder, job_title)
    special_marker = os.path.join(final_directory, ".arm-special-features-only")

    if is_special_features:
        transcode_out_path = os.path.join(
            job.config.TRANSCODE_PATH, type_sub_folder,
            f"{job_title} - Special Features - Job {job.job_id}"
        )
        utils.make_dir(transcode_out_path)
        utils.make_dir(final_directory)
        main_movie_file = os.path.join(
            final_directory, f"{job_title}.{job.config.DEST_EXT}"
        )
        if not os.path.isfile(main_movie_file) and not os.path.exists(special_marker):
            with open(special_marker, "w", encoding="utf-8") as marker_file:
                marker_file.write(f"Special-feature disc job {job.job_id} created this directory.\\n")
    else:
        # Reuse a directory created by a special-feature disc before the movie disc was ripped.
        if os.path.isfile(special_marker):
            logging.info(
                "Reusing movie directory previously created for special features: %s", final_directory
            )
        else:
            final_directory = utils.check_for_dupe_folder(have_dupes, final_directory, job)
        transcode_out_path = utils.check_for_dupe_folder(have_dupes, transcode_out_path, job)

    return transcode_out_path, final_directory, is_special_features, special_marker


def rip_visual_media(have_dupes, job, logfile, protection):
    """
    Main ripping function for dvd and Blu-rays, movies or series
    \n
    :param have_dupes: Does this disc already exist in the database
    :param job: Current job
    :param logfile: Current logfile
    :param protection: Does the disc have 99 track protection
    :return: None
    """
    # Keep label metadata available to the UI and select movie Disc 2 automatically.
    _apply_disc_feature_defaults(job)

    # Fix the sub-folder type - (movie|tv|unknown)
    type_sub_folder = utils.convert_job_type(job.video_type)
    # Fix the job title - Title (Year) | Title
    job_title = utils.fix_job_title(job)

    # Construct output directories with special-feature discs sharing their movie folder.
    transcode_out_path, final_directory, is_special_features, special_marker = _prepare_output_paths(
        have_dupes, job, type_sub_folder, job_title
    )

    # Update the job.path with the movie directory, not the temporary special-feature output.
    utils.database_updater({'path': final_directory}, job)
    # Preserve the main movie poster when processing its special-feature disc.
    if not is_special_features:
        utils.save_disc_poster(final_directory, job)

    logging.info(f"Processing files to: {transcode_out_path}")
    makemkv_out_path = None
    transcode_in_path = str(job.devpath)
    # Do we need to use MakeMKV - Blu-rays, protected dvd's, and dvd with mainfeature off
    use_make_mkv = rip_with_mkv(job, protection)
    logging.debug(f"Using MakeMKV: [{use_make_mkv}]")
    if use_make_mkv:
        logging.info("************* Ripping disc with MakeMKV *************")
        # Run MakeMKV and get path to output
        job.status = JobState.VIDEO_RIPPING.value
        db.session.commit()
        try:
            makemkv_out_path = makemkv.makemkv(job)
        except Exception as mkv_error:  # noqa: E722
            # MakeMKV may detect the open tray before the watchdog's next poll.
            abort_reason = utils.detect_open_tray_abort(job)
            if abort_reason:
                raise utils.RipperException(abort_reason) from mkv_error
            raise utils.RipperException("Error while running MakeMKV") from mkv_error

        if job.config.NOTIFY_RIP:
            utils.notify(job, constants.NOTIFY_TITLE, f"{job.title} rip complete. Starting transcode. ")
        logging.info("************* Ripping with MakeMKV completed *************")
        # point HB/FFMPEG to the path MakeMKV ripped to
        transcode_in_path = makemkv_out_path
    # Begin transcoding section - only transcode if skip_transcode is false
    start_transcode(job, logfile, transcode_in_path, transcode_out_path, protection)

    # --------------- POST PROCESSING ---------------
    # If ripped with MakeMKV remove the 'out' folder and set the raw as the output
    logging.debug(f"Transcode status: [{job.config.SKIP_TRANSCODE}] and MakeMKV Status: [{use_make_mkv}]")
    if job.config.SKIP_TRANSCODE and use_make_mkv:
        utils.delete_raw_files([transcode_out_path])
        transcode_out_path = transcode_in_path

    # Reconcile the output path if the title was changed while this job ran.
    logging.debug("Job title status: [%s]", job.title_manual)
    if job.title_manual:
        job_title = utils.fix_job_title(job)
        manual_final_directory = os.path.join(job.config.COMPLETED_PATH, type_sub_folder, job_title)
        current_path = os.path.normcase(os.path.abspath(final_directory))
        updated_path = os.path.normcase(os.path.abspath(manual_final_directory))
        if current_path != updated_path:
            # Keep special-feature content if its movie directory needs to be renamed.
            if os.path.isfile(special_marker) and not os.path.exists(manual_final_directory):
                os.rename(final_directory, manual_final_directory)
            else:
                utils.delete_raw_files([final_directory])
            final_directory = manual_final_directory
            special_marker = os.path.join(final_directory, ".arm-special-features-only")
            utils.database_updater({'path': final_directory}, job)

    # Move to final folder
    move_files_post(transcode_out_path, job)
    # A matching movie file now exists, so future jobs should follow the normal duplicate policy.
    if not is_special_features and os.path.isfile(special_marker):
        expected_movie_file = os.path.join(job.path, utils.fix_job_title(job) + "." + job.config.DEST_EXT)
        if os.path.isfile(expected_movie_file):
            try:
                os.remove(special_marker)
            except OSError as error:
                logging.warning("Could not remove special-feature directory marker %s: %s", special_marker, error)
    # Preserve the movie poster when processing a special-feature disc.
    if not is_special_features:
        utils.move_movie_poster(final_directory, transcode_out_path)
    # Scan Emby if arm.yaml requires it
    utils.scan_emby()
    # Set permissions if arm.yaml requires it
    utils.set_permissions(final_directory)
    # If set in the arm.yaml remove the raw files
    utils.delete_raw_files([transcode_in_path, transcode_out_path, makemkv_out_path])
    # report errors if any
    notify_exit(job)
    logging.info("************* ARM processing complete *************")


def start_transcode(job, logfile, raw_in_path, transcode_out_path, protection):
    """
    This checks if transcoding is enabled for the job and then passes it off to the correct
    transcoding function, first if handbrake or ffmpegshould be used, then how it should be ripped\n
    :param raw_in_path: HandBrake in path (makeMKV_out_path|/dev/sr0)
    :param transcode_out_path: Path HandBrake should put the files (transcode_path)
    :param job: Current job
    :param logfile: Current logfile
    :param protection: If disc has 99 track protection
    :return: None
    """
    if job.config.SKIP_TRANSCODE:
        logging.info("Transcoding is disabled, skipping transcode")
        return None

    # Update db with transcoding status
    utils.database_updater({'status': "transcoding"}, job)
    # Use FFMPEG or HandBrake depending on arm.yaml setting
    if job.config.USE_FFMPEG:
        logging.info("************* Starting Transcode With FFMPEG *************")
        # If it was ripped with MakeMKV or we are doing a mkv rip then run the ffmpeg_mkv function
        if rip_with_mkv(job, protection) and job.config.RIPMETHOD == "mkv":
            logging.debug(f"ffmpeg_mkv: {raw_in_path}, {transcode_out_path}")
            ffmpeg.ffmpeg_mkv(raw_in_path, transcode_out_path, job)
        # Otherwise if it is a movie and mainfeature is enabled then run ffmpeg_main_feature
        elif (
            job.video_type == "movie"
            and job.config.MAINFEATURE
            and job.hasnicetitle
            and not bool(getattr(job, "special_features", False))
        ):
            logging.debug(f"ffmpeg_main_feature: {raw_in_path}, {transcode_out_path}")
            ffmpeg.ffmpeg_main_feature(raw_in_path, transcode_out_path, job)
            db.session.commit()
        # Finally if it is a series or mainfeature is disabled run ffmpeg_all to transcode all tracks
        else:
            logging.debug(f"ffmpeg_all: {raw_in_path}, {transcode_out_path}")
            ffmpeg.ffmpeg_all(raw_in_path, transcode_out_path, job)
            db.session.commit()
        logging.info("************* Finished Transcode With FFMPEG *************")
        # After transcoding update db status back to active
        utils.database_updater({'status': "active"}, job)
        return True

    elif not job.config.USE_FFMPEG:
        logging.info("************* Starting Transcode With HandBrake *************")
        # If it was ripped with MakeMKV or we are doing a mkv rip then run the handbrake_mkv function
        if rip_with_mkv(job, protection) and job.config.RIPMETHOD == "mkv":
            logging.debug(f"handbrake_mkv: {raw_in_path}, {transcode_out_path}, {logfile}")
            handbrake.handbrake_mkv(raw_in_path, transcode_out_path, logfile, job)
        # Otherwise if it is a movie and mainfeature is enabled then run handbrake_main_feature
        elif (
            job.video_type == "movie"
            and job.config.MAINFEATURE
            and job.hasnicetitle
            and not bool(getattr(job, "special_features", False))
        ):
            logging.debug(f"handbrake_main_feature: {raw_in_path}, {transcode_out_path}, {logfile}")
            handbrake.handbrake_main_feature(raw_in_path, transcode_out_path, logfile, job)
            db.session.commit()
        # Finally if it is a series or mainfeature is disabled run handbrake_all to transcode all tracks
        else:
            logging.debug(f"handbrake_all: {raw_in_path}, {transcode_out_path}, {logfile}")
            handbrake.handbrake_all(raw_in_path, transcode_out_path, logfile, job)
            db.session.commit()
        logging.info("************* Finished Transcode With HandBrake *************")
        # After transcoding update db status back to active
        utils.database_updater({'status': "active"}, job)
        return True
    else:
        logging.info("Invalid transcoding option selected. Skipping transcode."
                     "Set USE_FFMPEG with valid boolean value fix error")
        return None


def notify_exit(job):
    """
    Notify post transcoding - ARM finished\n
    Includes any errors
    :param job: current job
    :return: None
    """
    if job.config.NOTIFY_TRANSCODE:
        if job.errors:
            errlist = ', '.join(job.errors)
            utils.notify(job, constants.NOTIFY_TITLE,
                         f" {job.title} processing completed with errors. "
                         f"Title(s) {errlist} failed to complete. ")
            logging.info(f"Transcoding completed with errors.  Title(s) {errlist} failed to complete. ")
        else:
            utils.notify(job, constants.NOTIFY_TITLE, f"{job.title} {constants.PROCESS_COMPLETE}")


def move_files_post(transcode_out_path, job):
    """
    Logic for moving files post transcoding\n
    if series move all to 1 folder\n
    if movie check what source we got them from, for MakeMKV use skip_transcode_movie, so we can check filesize\n
    :param transcode_out_path: This should either be the RAW_PATH from MakeMKV, /dev/srX or TRANSCODE_PATH
    :param job: current job
    :return: None
    """
    tracks = job.tracks.filter_by(ripped=True)  # .order_by(job.tracks.length.desc())
    if bool(getattr(job, "special_features", False)) and str(job.video_type or "").lower() == "movie":
        for track in tracks:
            utils.move_files(transcode_out_path, track.filename, job, False)
        return

    if job.video_type == "series":
        for track in tracks:
            utils.move_files(transcode_out_path, track.filename, job, False)
    else:
        for track in tracks:
            if tracks.count() == 1:
                utils.move_files(transcode_out_path, track.filename, job, True)
            else:
                # If source is MakeMKV we know the mainfeature will be wrong let skip_transcode_movie handle it
                if track.source == "MakeMKV":
                    skip_transcode_movie(os.listdir(transcode_out_path), job, transcode_out_path)
                    break
                # If HandBrake was used we can pass track.main_feature
                utils.move_files(transcode_out_path, track.filename, job, track.main_feature)


def rip_with_mkv(current_job, protection=0):
    """
    Test to check if title was or should be ripped by MakeMKV\n
    :param current_job: current job
    :param protection: If the disc have 99 track protection
    :return: Bool
    """
    mkv_ripped = False
    # Rip bluray
    if current_job.disctype == "bluray":
        mkv_ripped = True
    # Rip dvd with mode: mkv and mainfeature: false
    if current_job.disctype == "dvd" and (not current_job.config.MAINFEATURE and current_job.config.RIPMETHOD == "mkv"):
        mkv_ripped = True
    # Rip dvds with skip transcode
    if current_job.disctype == "dvd" and current_job.config.SKIP_TRANSCODE:
        mkv_ripped = True
    # If dvd has 99 protection force MakeMKV to be used
    if protection and current_job.disctype == "dvd":
        mkv_ripped = True
    # if backup_dvd, always use mkv
    if current_job.config.RIPMETHOD == "backup_dvd":
        mkv_ripped = True
    return mkv_ripped


def skip_transcode_movie(files, job, raw_path):
    """
    Only ran if job is a movie - find the largest file use it as mainfeature\n
    Move everything else to extras folder\n
    If mainfeature is enabled skip moving everything but the main file\n
    :param files: os.listdir(RAW_PATH)
    :param job: Current job
    :param raw_path: RAW_PATH of ripped mkv files (mkvoutpath)
    :return: None
    """
    logging.debug(f"Videotype: {job.video_type}")
    # if video_type is movie, then move the biggest title to media_dir
    # move the rest of the files to the extras' folder
    # find largest filesize
    logging.debug("Finding largest file")
    largest_file_name = utils.find_largest_file(files, raw_path)
    # largest_file_name should be the largest file
    logging.debug(f"Largest file is: {largest_file_name}")
    temp_path = os.path.join(raw_path, largest_file_name)
    if os.stat(temp_path).st_size <= 1:  # sanity check for filesize
        logging.info(f"{raw_path} is empty or very small size. - Folder size: {os.stat(temp_path).st_size}")
    for file in files:
        # move main into main folder
        # move others into extras folder
        if file == largest_file_name:
            # largest movie
            utils.move_files(raw_path, file, job, True)
        else:
            # If mainfeature is enabled - skip to the next file
            if job.config.MAINFEATURE:
                logging.info(f"MAINFEATURE IS {job.config.MAINFEATURE} - Skipping move of {file}")
                continue
            # Other/extras
            if str(job.config.EXTRAS_SUB).lower() != "none":
                utils.move_files(raw_path, file, job, False)
            else:
                logging.info(f"Not moving extra: \"{file}\" - Sub folder is not set or named incorrectly")
