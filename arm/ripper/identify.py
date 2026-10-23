#!/usr/bin/env python3
"""Identification of dvd/bluray"""

import os
import logging
import urllib
import re
import datetime
import unicodedata
import json
from ast import literal_eval

import pydvdid
import xmltodict
import xml.parsers.expat
import arm.config.config as cfg
from arm.models import Job

from arm.ripper import utils
from arm.ripper.ProcessHandler import arm_subprocess
from arm.ui import db
from arm.media_metadata import parse_media_label, select_best_media_result

# flake8: noqa: W605
from arm.ui import utils as ui_utils


def find_mount(devpath: str) -> str | None:
    """
    Find existing, readable mountpoint for ``devpath`` by calling ``findmnt``

    :return: Absolute path of mountpoint as ``str`` if any, else ``None``
    """
    if output := arm_subprocess(["findmnt", "--json", devpath]):
        mountpoints = json.loads(output)
        for mountpoint in mountpoints["filesystems"]:
            if os.access(mountpoint["target"], os.R_OK):
                return mountpoint["target"]
    return None


def check_mount(job: Job) -> bool:
    """
    Check if there is a suitable mount for ``job``, if not, try to mount

    :return: ``True`` if mount exists now, ``False`` otherwise
    """
    if mountpoint := find_mount(job.devpath):
        logging.info(f"Found disc {job.devpath} mounted at {mountpoint}")
        job.mountpoint = mountpoint
    else:
        logging.info(f"Trying to mount disc at {job.devpath}...")
        arm_subprocess(["mount", "--source", job.devpath])
        if mountpoint := find_mount(job.devpath):
            logging.info(f"Successfully mounted disc to {mountpoint}")
            job.mountpoint = mountpoint
        else:
            logging.error("Disc was not and could not be mounted. Rip might fail.")
            return False
    return True


def identify(job):
    """Identify disc attributes"""
    logging.debug("Identify Entry point --- job ----")

    mounted = check_mount(job)

    # get_disc_type() checks local files, no need to run unless we can mount
    if mounted:
        # Check with the job class to get the correct disc type
        job.get_disc_type(utils.find_file("HVDVD_TS", job.mountpoint))

    if job.disctype in ["dvd", "bluray"]:

        logging.info("Disc identified as video")

        if cfg.arm_config["GET_VIDEO_TITLE"]:
            res = False
            if job.disctype == "dvd":
                res = identify_dvd(job)
            if job.disctype == "bluray":
                res = identify_bluray(job)
            if res:
                get_video_details(job)
            else:
                job.hasnicetitle = False
                db.session.commit()

            logging.info(f"Disc title Post ident -  title:{job.title} "
                         f"year:{job.year} video_type:{job.video_type} "
                         f"disctype: {job.disctype}")
            logging.debug(f"identify.job.end ---- \n\r{job.pretty_table()}")
    # No need to warn if we cant unmount
    arm_subprocess(["umount", job.devpath])


def _apply_disc_label_metadata(job):
    """Copy only explicitly provided title/year/season/disc/episode values from the label."""
    parsed = parse_media_label(getattr(job, "label", None))
    for field in ("season_number", "disc_number", "episode_start", "episode_end"):
        if parsed.get(field) is not None and getattr(job, field, None) is None:
            setattr(job, field, parsed[field])
    raw_label = str(getattr(job, "label", "") or "")
    current_title = str(getattr(job, "title", "") or "")
    if parsed.get("title") and (
            not current_title or current_title == raw_label
            or current_title.strip().lower() in ("none", "not identified")):
        job.title = job.title_auto = parsed["title"]
    if parsed.get("year") and not getattr(job, "year", None):
        job.year = job.year_auto = parsed["year"]
    return parsed


def identify_bluray(job):
    """Get Blu-ray title and metadata from XML or the disc label."""
    parsed_label = _apply_disc_label_metadata(job)

    try:
        with open(job.mountpoint + '/BDMV/META/DL/bdmt_eng.xml', "rb") as xml_file:
            xml_data = xml_file.read()

            try:
                doc = xmltodict.parse(xml_data)
            except xml.parsers.expat.ExpatError as error:
                lines = xml_data.decode("utf-8", errors="replace").splitlines()

                offending = ""
                if 1 <= error.lineno <= len(lines):
                    offending = lines[error.lineno - 1].strip()

                logging.warning(
                    "Malformed Blu-ray metadata XML at line %d column %d: %s\n"
                    "Offending line: %s\n"
                    "Attempting automatic repair.",
                    error.lineno,
                    error.offset,
                    error,
                    offending,
                )

                repaired = repair_bluray_xml(xml_data)
                try:
                    doc = xmltodict.parse(repaired)
                    logging.info("Successfully repaired malformed Blu-ray metadata XML.")
                except xml.parsers.expat.ExpatError as error:
                    logging.exception(
                        "Blu-ray metadata XML remains malformed at line %d column %d: %s. "
                        "Using disc label '%s'.",
                        error.lineno,
                        error.offset,
                        error,
                        job.label,
                    )
                    doc = None
    except OSError as error:
        logging.error("Disc is a bluray, but bdmt_eng.xml could not be found. "
                      "Disc cannot be identified.  Error "
                      f"number is: {error.errno}")
        # Maybe call OMdb with label when we can't find any ident on disc ?
        # Attempt to parse label
        if str(job.label) == "":
            job.title = str(job.label)
            job.year = ""
            db.session.commit()
            return False
        else:
            bluray_title = parsed_label.get('title') or str(job.label).replace('_', ' ')
            # Preserve the disc label's original casing (e.g. iRobot, eXistenZ).
            job.title = job.title_auto = utils.clean_for_filename(bluray_title)
            job.year = parsed_label.get('year') or ""
            db.session.commit()
            return True

    if doc is None:
        bluray_title = str(job.label)
    else:
        try:
            bluray_title = doc['disclib']['di:discinfo']['di:title']['di:name']
            if not bluray_title:
                bluray_title = str(job.label)
        except KeyError:
            bluray_title = str(job.label)
            logging.error(
                "Could not parse title from bdmt_eng.xml file. "
                "Using disc label '%s'.",
                job.label,
            )

    bluray_modified_timestamp = os.path.getmtime(job.mountpoint + '/BDMV/META/DL/bdmt_eng.xml')
    bluray_year = parsed_label.get('year') or datetime.datetime.fromtimestamp(bluray_modified_timestamp).strftime('%Y')

    bluray_title = unicodedata.normalize('NFKD', str(bluray_title)).encode('ascii', 'ignore').decode()

    bluray_title = bluray_title.replace(' - Blu-rayTM', '')
    bluray_title = bluray_title.replace(' Blu-rayTM', '')
    bluray_title = bluray_title.replace(' - BLU-RAYTM', '')
    bluray_title = bluray_title.replace(' - BLU-RAY', '')
    bluray_title = bluray_title.replace(' - Blu-ray', '')

    bluray_title = utils.clean_for_filename(bluray_title)

    job.title = job.title_auto = bluray_title
    job.year = job.year_auto = bluray_year
    db.session.commit()

    return True


def identify_dvd(job):
    """Identify DVDs using disc label parsing and metadata providers."""
    parsed_label = _apply_disc_label_metadata(job)
    logging.debug(f"\n\r{job.pretty_table()}")
    # Some older DVDs aren't actually labelled
    if not job.label or job.label == "":
        job.label = "not identified"
    try:
        crc64 = pydvdid.compute(str(job.mountpoint))
        dvd_title = f"{job.label}_{crc64}"
        logging.info(f"DVD CRC64 hash is: {crc64}")
        job.crc_id = str(crc64)
        urlstring = f"https://1337server.pythonanywhere.com/api/v1/?mode=s&crc64={crc64}"
        logging.debug(urlstring)
        dvd_info_xml = urllib.request.urlopen(urlstring).read()
        arm_api_json = json.loads(dvd_info_xml)
        logging.debug(f"dvd xml - {arm_api_json}")
        logging.debug(f"results = {arm_api_json['results']}")
        if arm_api_json['success']:
            logging.info("Found crc64 id from online API")
            logging.info(f"title is {arm_api_json['results']['0']['title']}")
            args = {
                'title': arm_api_json['results']['0']['title'],
                'title_auto': arm_api_json['results']['0']['title'],
                'year': arm_api_json['results']['0']['year'],
                'year_auto': arm_api_json['results']['0']['year'],
                'imdb_id': arm_api_json['results']['0']['imdb_id'],
                'imdb_id_auto': arm_api_json['results']['0']['imdb_id'],
                'video_type': arm_api_json['results']['0']['video_type'],
                'video_type_auto': arm_api_json['results']['0']['video_type'],
                'poster_url': arm_api_json['results']['0']['poster_img'],
                'poster_url_auto': arm_api_json['results']['0']['poster_img'],
                'hasnicetitle': True
            }
            utils.database_updater(args, job)
    except Exception as error:
        logging.error(f"Pydvdid failed with the error: {error}")
        dvd_title = str(job.label)

    logging.debug(f"dvd_title_label: {dvd_title}")
    # in this block we want to strip out any chars that might be bad
    # strip all non-numeric chars and use that for year
    year = parsed_label.get('year') or (re.sub(r"\D", "", str(job.year)) if job.year else None)
    # Remove explicit year and disc tokens before making a metadata query.
    dvd_title = (parsed_label.get('title') or job.label).replace("16x9", "")
    logging.debug(f"dvd_title ^a-z _-: {dvd_title}")
    # rip out any SKU's at the end of the line
    dvd_title = re.sub(r"SKU\b", "", dvd_title)
    logging.debug(f"dvd_title SKU$: {dvd_title}")

    # Do we really need metaselector if we have got from ARM online db?
    try:
        dvd_info_xml = metadata_selector(job, dvd_title, year)
        logging.debug(f"DVD_INFO_XML: {dvd_info_xml}")
        identify_loop(job, dvd_info_xml, dvd_title, year)
    except Exception:
        dvd_info_xml = None
        logging.debug("Cant connect to online service!")
    # Failsafe so that we always have a title.
    if job.title is None or job.title == "None":
        job.title = str(job.label)
        job.year = None

    # Track 99 detection
    # -Oy means output a python dict
    output = arm_subprocess(["lsdvd", "-Oy", job.devpath])
    if output:
        try:
            # literal_eval only accepts literals so we have to adjust the output slightly
            tracks = literal_eval(re.sub(r"^.*\{", "{", output)).get("track", [])
            logging.debug(f"Detected {len(tracks)} tracks")
            if len(tracks) == 99:
                job.has_track_99 = True
                if cfg.arm_config["PREVENT_99"]:
                    raise utils.RipperException("Track 99 found and PREVENT_99 is enabled")
        except (SyntaxError, AttributeError) as e:
            logging.error("Failed to parse lsdvd output", exc_info=e)

    return True


def get_video_details(job):
    """ Clean up title and year.  Get video_type, imdb_id, poster_url from
    omdbapi.com webservice.\n

    job = Instance of Job class\n
    """
    title = job.title

    # Set out title from the job.label
    # return if not identified
    logging.debug(f"Title = {title}")
    if title == "not identified" or title is None or title == "":
        logging.info("Disc couldn't be identified")
        return
    title = re.sub('[_ ]', "+", title.strip())

    # strip all non-numeric chars and use that for year
    if job.year is None:
        year = ""
    else:
        year = re.sub(r"\D", "", str(job.year))

    logging.debug(f"Title: {title} | Year: {year}")
    logging.debug(f"Calling webservice with title: {title} and year: {year}")

    try:
        identify_loop(job, None, title, year)
    except Exception as error:
        logging.info(f"Identification failed with the error: {error}. Continuing...")


def update_job(job, search_results):
    """Update a job from the best metadata result, preferring TV for explicit episodes."""
    if not search_results or "Search" not in search_results or not search_results["Search"]:
        return None

    parsed_label = parse_media_label(getattr(job, "label", None))
    selected = select_best_media_result(
        search_results["Search"],
        title=parsed_label.get("title") or job.title,
        year=parsed_label.get("year") or job.year,
        prefer_series=bool(getattr(job, "season_number", None) or getattr(job, "episode_start", None)),
    )
    if selected is None:
        return None
    result = selected
    new_year = result.get("Year", "")
    title = utils.clean_for_filename(result.get("Title", ""))
    imdb_id = result.get("imdbID")
    tmdb_id = result.get("id") or result.get("tmdbID")

    if (not tmdb_id
            and str(cfg.arm_config.get("FOLDER_ID_TYPE", "none")).lower() == "tmdb"
            and imdb_id
            and cfg.arm_config.get("TMDB_API_KEY")):
        try:
            tmdb_details = ui_utils.tmdb_find(imdb_id)
            if tmdb_details:
                tmdb_id = tmdb_details.get("tmdbID")
                if not tmdb_id and tmdb_details.get("results"):
                    tmdb_id = tmdb_details["results"][0].get("id")
        except Exception as error:
            logging.warning("Could not resolve TMDB ID for %s: %s", imdb_id, error)

    logging.debug("Webservice successful. New title is %s. New year is: %s", title, new_year)
    args = {
        "year_auto": str(new_year),
        "year": str(new_year),
        "title_auto": title,
        "title": title,
        "video_type_auto": result.get("Type"),
        "video_type": result.get("Type"),
        "imdb_id_auto": imdb_id,
        "imdb_id": imdb_id,
        "tmdb_id": str(tmdb_id) if tmdb_id else None,
        "poster_url_auto": result.get("Poster"),
        "poster_url": result.get("Poster"),
        "hasnicetitle": True,
    }
    return utils.database_updater(args, job)

def metadata_selector(job, title=None, year=None):
    """
    Used to switch between OMDB or TMDB as the metadata provider\n
    - TMDB returned queries are converted into the OMDB format

    :param job: The job class
    :param title: this can either be a search string or movie/show title
    :param year: the year of movie/show release

    :return: json/dict object or None
    """
    # Normalize label separators before checking the placeholder. Some unreadable
    # discs report "not_identified" or "not+identified", which must not be searched.
    if title is not None:
        title = " ".join(str(title).replace("_", " ").replace("+", " ").split())
    if title is None or str(title).strip().lower() in ("", "not identified"):
        logging.info(f"Not searching for placeholder title: {title!r}")
        return None

    search_results = None
    if cfg.arm_config['METADATA_PROVIDER'].lower() == "tmdb":
        logging.debug("provider tmdb")
        search_results = ui_utils.tmdb_search(title, year)
        if search_results is not None:
            update_job(job, search_results)
    elif cfg.arm_config['METADATA_PROVIDER'].lower() == "omdb":
        logging.debug("provider omdb")
        search_results = ui_utils.call_omdb_api(str(title), str(year))
        if search_results is not None:
            update_job(job, search_results)
    else:
        logging.debug(cfg.arm_config['METADATA_PROVIDER'])
        logging.debug("unknown provider - doing nothing, saying nothing. Getting Kryten")
    return search_results


def identify_loop(job, response, title, year):
    """
    Try metadata lookup without destructively chopping up the detected title.

    The previous fallback removed everything after any hyphen and then shortened
    titles word-by-word, which could break hyphenated names and silently select an
    unrelated movie. Only known disc/format suffixes are removed as a last resort.
    """
    logging.debug("Response = %s", response)
    title = str(title or "").replace("_", "+").replace(" ", "+")
    while "++" in title:
        title = title.replace("++", "+")

    if response is None:
        response = try_with_year(job, response, title, year)
        response = try_without_year(job, response, title)

    if response is not None:
        return

    # Normalize separator patterns like "Movie+-+DVD", but do not rewrite
    # a genuine title hyphen, e.g. "Spider-Man".
    candidate = title.replace("+-+", "+").replace("-+-", "+")
    suffixes = (
        "+disc+1", "+disc+2", "+disc+3", "+disk+1", "+disk+2", "+disk+3",
        "+dvd", "+blu-ray", "+bluray", "+bdrip", "+brrip", "+hdtv", "+ntsc",
        "+pal", "+720p", "+1080p", "+2160p", "+x264", "+x265",
        "-dvd", "-blu-ray", "-bluray", "-bdrip", "-brrip", "-hdtv",
    )
    lowered = candidate.lower()
    for suffix in suffixes:
        if lowered.endswith(suffix):
            candidate = candidate[:-len(suffix)].rstrip("+- ")
            break

    if candidate and candidate != title:
        logging.debug("Retrying metadata lookup after removing disc/format suffix: %s", candidate)
        response = try_with_year(job, None, candidate, year)
        response = try_without_year(job, response, candidate)


def try_without_year(job, response, title):
    """

    :param job:
    :param response:
    :param title:
    :return:
    """
    if response is None:
        logging.debug("Removing year...")
        response = metadata_selector(job, title)
        logging.debug(f"response: {response}")
    return response


def try_with_year(job, response, title, year):
    """

    :param job:
    :param response:
    :param title:
    :param year:
    :return:
    """
    # If we have a response don't overwrite it
    if response is not None:
        return response
    if year:
        response = metadata_selector(job, title, str(year))
        logging.debug(f"response: {response}")
    # If we still don't have a response try removing a year off
    if response is None and year:
        # This accounts for when
        # the dvd release date is the year following the movie release date
        logging.debug("Subtracting 1 year...")
        response = metadata_selector(job, title, str(int(year) - 1))
    return response


def repair_bluray_xml(xml_data):
    # some Sunrise discs have malformed XML where href=foo instead of href="foo"
    xml_data = re.sub(
        rb'(?<!")href=([^"\s>][^\s>]*)',
        rb'href="\1"',
        xml_data,
    )
    return xml_data
