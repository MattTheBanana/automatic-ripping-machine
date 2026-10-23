"""Main file for interacting with omdb and tmdb"""
import urllib
import json
import re
import requests

from arm.media_metadata import title_search_variants
from flask.logging import default_handler  # noqa: F401

from arm.ui import app
import arm.config.config as cfg

TMDB_YEAR_REGEX = r"-\d{0,2}-\d{0,2}"


def call_omdb_api(title=None, year=None, imdb_id=None, plot="short"):
    """Search OMDb for a movie/show while retrying normalized title variants."""
    omdb_api_key = cfg.arm_config["OMDB_API_KEY"]
    if imdb_id:
        urls = [f"https://www.omdbapi.com/?i={urllib.parse.quote(str(imdb_id))}&plot={plot}&r=json&apikey={omdb_api_key}"]
    elif title:
        urls = []
        for variant in title_search_variants(title):
            encoded = urllib.parse.quote(variant)
            if year:
                urls.append(f"https://www.omdbapi.com/?s={encoded}&y={urllib.parse.quote(str(year))}&plot={plot}&r=json&apikey={omdb_api_key}")
            urls.append(f"https://www.omdbapi.com/?s={encoded}&plot={plot}&r=json&apikey={omdb_api_key}")
    else:
        app.logger.debug("no params")
        return None
    for url in urls:
        try:
            payload = urllib.request.urlopen(url).read()
            info = json.loads(payload.decode())
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as error:
            app.logger.error("OMDb call failed: %s", error)
            continue
        info["background_url"] = None
        if info.get("Response") != "False" and "Error" not in info:
            return info
    return None

def get_omdb_poster(title=None, year=None, imdb_id=None, plot="short"):
    """
    Queries OMDbapi.org for the poster for movie/show
    :param title: title of movie/show
    :param year: year of release
    :param imdb_id: imdb id of movie/show
    :param plot: short or full plot
    :return: [poster_link, imdb_id]
    """
    omdb_api_key = cfg.arm_config['OMDB_API_KEY']
    if imdb_id:
        str_url = f"https://www.omdbapi.com/?i={imdb_id}&plot={plot}&r=json&apikey={omdb_api_key}"
        str_url_2 = ""
    elif title:
        str_url = f"https://www.omdbapi.com/?s={title}&y={year}&plot={plot}&r=json&apikey={omdb_api_key}"
        str_url_2 = f"https://www.omdbapi.com/?t={title}&y={year}&plot={plot}&r=json&apikey={omdb_api_key}"
    else:
        app.logger.debug("no params")
        return None, None
    try:
        title_info_json = urllib.request.urlopen(requests.utils.requote_uri(str_url)).read()
    except Exception as error:
        app.logger.debug(f"Failed to reach OMdb - {error}")
    else:
        title_info = json.loads(title_info_json.decode())
        # app.logger.debug("omdb - " + str(title_info))
        if 'Error' not in title_info:
            return title_info['Search'][0]['Poster'], title_info['Search'][0]['imdbID']

        try:
            title_info_json2 = urllib.request.urlopen(requests.utils.requote_uri(str_url_2)).read()
            title_info2 = json.loads(title_info_json2.decode())
            # app.logger.debug("omdb - " + str(title_info2))
            if 'Error' not in title_info2:
                return title_info2['Poster'], title_info2['imdbID']
        except Exception as error:
            app.logger.error(f"Failed to reach OMdb - {error}")

    return None, None


def get_tmdb_poster(search_query=None, year=None):
    """
    Queries api.themoviedb.org for the poster and backdrop for movie
    :param search_query: title of movie/show
    :param year: year of movie/show
    :return: dict of search results
    """
    tmdb_api_key = cfg.arm_config['TMDB_API_KEY']
    search_results, poster_base, response = tmdb_fetch_results(search_query, year, tmdb_api_key)

    # if status_code is in search_results we know there was an error
    if 'status_code' in search_results:
        app.logger.debug(f"get_tmdb_poster failed with error -  {search_results['status_message']}")
        return None

    # If movies are found return those after processing
    if search_results['total_results'] > 0:
        app.logger.debug(search_results['total_results'])
        return tmdb_process_poster(search_results, poster_base)

    # Search tmdb for tv series
    url = f"https://api.themoviedb.org/3/search/tv?api_key={tmdb_api_key}&query={search_query}"
    response = requests.get(url)
    search_results = json.loads(response.text)
    # app.logger.debug(json.dumps(response.json(), indent=4, sort_keys=True))
    if search_results['total_results'] > 0:
        app.logger.debug(search_results['total_results'])
        return tmdb_process_poster(search_results, poster_base)
    app.logger.debug("No results found")
    return None


def tmdb_process_poster(search_results, poster_base):
    """Return one movie or series detail object when a date is available."""
    for item in search_results.get("results", []):
        is_series = "first_air_date" in item or "name" in item
        date_value = item.get("first_air_date") if is_series else item.get("release_date")
        if not date_value:
            continue
        item["poster_url"] = f"{poster_base}{item['poster_path']}" if item.get("poster_path") else ""
        item["Plot"] = item.get("overview") or ""
        item["background_url"] = f"{poster_base}{item['backdrop_path']}" if item.get("backdrop_path") else None
        item["Type"] = "series" if is_series else "movie"
        item["Year"] = re.sub(TMDB_YEAR_REGEX, "", date_value)
        item["Title"] = item.get("name") if is_series else item.get("title")
        item["tmdbID"] = str(item.get("id") or "")
        return item
    return None

def tmdb_search(search_query=None, year=None):
    """Search movies and TV series, retrying joined-word/compact label variants."""
    key = cfg.arm_config["TMDB_API_KEY"]
    poster_base = "https://image.tmdb.org/t/p/original"
    for query in title_search_variants(search_query):
        movie_data, _, _ = tmdb_fetch_results(query, year, key)
        movie_results = (movie_data.get("results") or [])[:5] if "status_code" not in movie_data else []
        tv_params = {"api_key": key, "query": query}
        if year:
            tv_params["first_air_date_year"] = year
        try:
            tv_response = requests.get("https://api.themoviedb.org/3/search/tv", params=tv_params)
            tv_data = json.loads(tv_response.text)
            tv_results = (tv_data.get("results") or [])[:5] if "status_code" not in tv_data else []
        except (requests.RequestException, ValueError, TypeError) as error:
            app.logger.warning("TMDB TV search failed: %s", error)
            tv_results = []
        if movie_results or tv_results:
            movies, series = {}, {}
            if movie_results:
                tmdb_process_results(poster_base, movies, {"results": movie_results}, "movie")
            if tv_results:
                tmdb_process_results(poster_base, series, {"results": tv_results}, "series")
            combined = (movies.get("Search") or []) + (series.get("Search") or [])
            unique, seen = [], set()
            for item in combined:
                identity = (str(item.get("Type", "")).lower(), str(item.get("tmdbID") or item.get("id") or ""))
                if identity not in seen:
                    seen.add(identity)
                    unique.append(item)
            return {"Search": unique}
    return None

def tmdb_process_results(poster_base, return_results, search_results, media_type="movie"):
    """Convert TMDB movie/TV results to the common OMDb-like result shape."""
    processed = []
    for result in search_results.get("results", []):
        date_value = result.get("first_air_date") if media_type == "series" else result.get("release_date")
        result["Year"] = re.sub(TMDB_YEAR_REGEX, "", date_value) if date_value else ""
        result["imdbID"] = tmdb_get_imdb(result.get("id"))
        result["tmdbID"] = str(result.get("id") or "")
        result["Title"] = result.get("title") or result.get("name") or ""
        result["Type"] = media_type
        result["Poster"] = f"{poster_base}{result['poster_path']}" if result.get("poster_path") else ""
        result["background_url"] = f"{poster_base}{result['backdrop_path']}" if result.get("backdrop_path") else None
        result["Plot"] = result.get("overview") or ""
        processed.append(result)
    return_results["Search"] = processed
    return return_results

def tmdb_get_imdb(tmdb_id):
    """
    Queries api.themoviedb.org for imdb_id by TMDB id\n
    :param tmdb_id: tmdb id of media
    :return: str of imdb_id
    """
    # https://api.themoviedb.org/3/movie/78?api_key=
    # &append_to_response=alternative_titles,changes,credits,images,keywords,lists,releases,reviews,similar,videos
    tmdb_api_key = cfg.arm_config['TMDB_API_KEY']
    url = f"https://api.themoviedb.org/3/movie/{tmdb_id}?api_key={tmdb_api_key}&" \
          f"append_to_response=alternative_titles,credits,images,keywords,releases,reviews,similar,videos,external_ids"
    url_tv = f"https://api.themoviedb.org/3/tv/{tmdb_id}/external_ids?api_key={tmdb_api_key}"
    # Making a get request
    response = requests.get(url)
    search_results = json.loads(response.text)
    # 'status_code' means id wasn't found
    if 'status_code' in search_results:
        # Try tv series
        response = requests.get(url_tv)
        tv_json = json.loads(response.text)
        app.logger.debug(tv_json)
        if 'status_code' not in tv_json:
            return tv_json['imdb_id']
        return None
    return search_results['external_ids']['imdb_id']


def tmdb_details(tmdb_id, media_type="movie"):
    """Fetch the exact movie/show selected by TMDB ID."""
    if not tmdb_id:
        return None
    kind = "tv" if str(media_type).lower() in ("series", "tv") else "movie"
    try:
        response = requests.get(
            f"https://api.themoviedb.org/3/{kind}/{urllib.parse.quote(str(tmdb_id))}",
            params={"api_key": cfg.arm_config["TMDB_API_KEY"], "append_to_response": "external_ids"}
        )
        item = json.loads(response.text)
    except (requests.RequestException, ValueError, TypeError):
        return None
    if "status_code" in item:
        return None
    is_series = kind == "tv"
    date_value = item.get("first_air_date") if is_series else item.get("release_date")
    poster_base = "https://image.tmdb.org/t/p/original"
    poster = f"{poster_base}{item['poster_path']}" if item.get("poster_path") else ""
    background = f"{poster_base}{item['backdrop_path']}" if item.get("backdrop_path") else None
    external = item.get("external_ids") or {}
    return {"results": [item], "Title": (item.get("name") if is_series else item.get("title")) or "",
            "Year": re.sub(TMDB_YEAR_REGEX, "", date_value) if date_value else "",
            "Type": "series" if is_series else "movie", "imdbID": external.get("imdb_id"),
            "tmdbID": str(item.get("id") or tmdb_id), "Poster": poster, "poster_url": poster,
            "background_url": background, "Plot": item.get("overview") or ""}


def tmdb_find(imdb_id):
    """Find a movie or TV series in TMDB by IMDb ID."""
    key = cfg.arm_config["TMDB_API_KEY"]
    response = requests.get(
        f"https://api.themoviedb.org/3/find/{urllib.parse.quote(str(imdb_id))}",
        params={"api_key": key, "external_source": "imdb_id"}
    )
    try:
        found = json.loads(response.text)
    except (ValueError, TypeError):
        return None
    if found.get("movie_results"):
        item, media_type = found["movie_results"][0], "movie"
        title, date_value = item.get("title") or "", item.get("release_date")
    elif found.get("tv_results"):
        item, media_type = found["tv_results"][0], "series"
        title, date_value = item.get("name") or "", item.get("first_air_date")
    else:
        return None
    poster_base = "https://image.tmdb.org/t/p/original"
    poster = f"{poster_base}{item['poster_path']}" if item.get("poster_path") else ""
    background = f"{poster_base}{item['backdrop_path']}" if item.get("backdrop_path") else None
    return {"results": [item], "poster_url": poster, "Plot": item.get("overview") or "",
            "background_url": background, "Type": media_type, "imdbID": imdb_id,
            "Poster": poster, "Year": re.sub(TMDB_YEAR_REGEX, "", date_value) if date_value else "",
            "Title": title, "tmdbID": str(item.get("id") or "")}

def validate_imdb(imdb_id):
    """
    Validate that the imdb id we got
    :param str imdb_id:
    :return:
    """
    # ['tt', 'nm', 'co', 'ev', 'ch' or 'ni'] - 123456789
    # /ev\d{7}\/\d{4}(-\d)?|(ch|co|ev|nm|tt)\d{7}/
    # /^ev\d{7}\/\d{4}(-\d)?$|^(ch|co|ev|nm|tt)\d{7}$/
    app.logger.debug(imdb_id)


def tmdb_fetch_results(search_query, year, tmdb_api_key):
    """
    Main function for fetching movie results from TMDB\n
    :param str search_query: search query from ARMui
    :param str year: the year of the movie/tv-show
    :param str tmdb_api_key: tmdb API key
    :return: [search_results dict, poster_img string, requests Response]
    """
    # https://api.themoviedb.org/3/movie/78?api_key= # base url
    # Additional
    # &append_to_response=alternative_titles,changes,credits,images,keywords,lists,releases,reviews,similar,videos
    if year:
        url = f"https://api.themoviedb.org/3/search/movie?api_key={tmdb_api_key}&query={search_query}&year={year}"
    else:
        url = f"https://api.themoviedb.org/3/search/movie?api_key={tmdb_api_key}&query={search_query}"
    # Valid poster sizes
    # "w92", "w154", "w185", "w342", "w500", "w780", "original"
    poster_size = "original"
    poster_base = f"https://image.tmdb.org/t/p/{poster_size}"
    response = requests.get(url)
    return_json = json.loads(response.text)
    return return_json, poster_base, response
