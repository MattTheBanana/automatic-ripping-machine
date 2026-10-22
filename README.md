# Automatic Ripping Machine (ARM)
[![CI](https://github.com/automatic-ripping-machine/automatic-ripping-machine/actions/workflows/main.yml/badge.svg)](https://github.com/automatic-ripping-machine/automatic-ripping-machine/actions/workflows/main.yml) [![Publish Docker Image](https://github.com/automatic-ripping-machine/automatic-ripping-machine/actions/workflows/publish-image.yml/badge.svg)](https://github.com/automatic-ripping-machine/automatic-ripping-machine/actions/workflows/publish-image.yml)
[![Docker](https://img.shields.io/docker/pulls/automaticrippingmachine/automatic-ripping-machine.svg)](https://hub.docker.com/r/automaticrippingmachine/automatic-ripping-machine)

[![GitHub forks](https://img.shields.io/github/forks/automatic-ripping-machine/automatic-ripping-machine)](https://github.com/automatic-ripping-machine/automatic-ripping-machine/network)
[![GitHub stars](https://img.shields.io/github/stars/automatic-ripping-machine/automatic-ripping-machine)](https://github.com/automatic-ripping-machine/automatic-ripping-machine/stargazers)
[![GitHub issues](https://img.shields.io/github/issues/automatic-ripping-machine/automatic-ripping-machine)](https://github.com/automatic-ripping-machine/automatic-ripping-machine/issues)
[![GitHub pull requests](https://img.shields.io/github/issues-pr/automatic-ripping-machine/automatic-ripping-machine)](https://github.com/automatic-ripping-machine/automatic-ripping-machine/pulls)
[![GitHub contributors](https://img.shields.io/github/contributors/automatic-ripping-machine/automatic-ripping-machine)](https://github.com/automatic-ripping-machine/automatic-ripping-machine/graphs/contributors)
[![GitHub last commit](https://img.shields.io/github/last-commit/automatic-ripping-machine/automatic-ripping-machine?)](https://github.com/automatic-ripping-machine/automatic-ripping-machine/commits/main)

[![GitHub license](https://img.shields.io/github/license/automatic-ripping-machine/automatic-ripping-machine)](https://github.com/automatic-ripping-machine/automatic-ripping-machine/blob/main/LICENSE)

[![GitHub release (latest by date)](https://img.shields.io/github/v/release/automatic-ripping-machine/automatic-ripping-machine?label=Latest%20Stable%20Version)](https://github.com/automatic-ripping-machine/automatic-ripping-machine/releases)
[![GitHub release Date](https://img.shields.io/github/release-date/automatic-ripping-machine/automatic-ripping-machine?label=Latest%20Stable%20Released)](https://github.com/automatic-ripping-machine/automatic-ripping-machine/releases)
![Python Versions](https://img.shields.io/badge/Python_Versions-3.9_|_3.10_|_3.11_|_3.12-blue?logo=python)



[![Wiki](https://img.shields.io/badge/Wiki-Get%20Help-brightgreen)](https://github.com/automatic-ripping-machine/automatic-ripping-machine/wiki)
[![Discord](https://img.shields.io/discord/576479573886107699)](https://discord.gg/FUSrn8jUcR)



## Overview

Insert an optical disc (Blu-ray, DVD, CD) and checks to see if it's audio, video (Movie or TV), or data, then rips it.

See: https://b3n.org/automatic-ripping-machine


## Features

- Detects insertion of disc using udev
- Determines disc type...
  - If video (Blu-ray or DVD)
    - Retrieve title from disc or [OMDb API](http://www.omdbapi.com/) to name the folder "Movie Title (Year)" so that Plex or Emby can pick it up
    - Determine if video is Movie or TV using [OMDb API](http://www.omdbapi.com/)
    - Rip using MakeMKV or HandBrake (can rip all features or main feature)
    - Eject disc and queue up Handbrake transcoding when done
    - Transcoding jobs are asynchronously batched from ripping
    - Send notifications via IFTTT, Pushbullet, Slack, Discord, and many more!
  - If audio (CD) - rip using abcde (get disc-data and album art from [musicbrainz](https://musicbrainz.org/))
  - If data (Blu-ray, DVD, DVD-Audio or CD) - make an ISO backup
- Headless, designed to be run from a server
- Can rip from multiple-optical drives in parallel
- Python Flask UI to interact with ripping jobs, view logs, update jobs, etc



## Usage

- Insert disc
- Wait for disc to eject
- Repeat


## Requirements

- A system capable of running Docker containers
- One or more optical drives to rip Blu-rays, DVDs, and CDs
- Lots of drive space (I suggest using a NAS) to store your movies


## Install

[For normal installation please see the wiki](https://github.com/automatic-ripping-machine/automatic-ripping-machine/wiki/).

[For docker installation please see here](https://github.com/automatic-ripping-machine/automatic-ripping-machine/wiki/docker).

[For WSL Integration please see here]()

## TrueNAS / custom image

This fork publishes its x86-64 ARM image to GitHub Container Registry (GHCR):

- Recommended moving tag: `ghcr.io/mattthebanana/arm-custom:latest`
- Version-pinned tag: `ghcr.io/mattthebanana/arm-custom:2.24.4` (matches the repository `VERSION` file)
- Compatibility tag: `ghcr.io/mattthebanana/arm-custom:makemkv-2.0.0`

The image is built on `ghcr.io/mattthebanana/arm-dependencies-custom:2.0.0`. The custom image workflow republishes `latest`, the ARM version, and the compatibility tag when changes land on `main`. For TrueNAS to pull the image without credentials, make the GHCR package public; otherwise configure image-pull credentials in TrueNAS.

### Media naming and Jellyfin matching

The `FOLDER_ID_TYPE` setting is available under **Settings → Ripper ARM Settings**:

- `none` (default): keep the normal `Title (Year)` naming.
- `tmdb`: append a Jellyfin-compatible `[tmdbid-123]` identifier.
- `imdb`: append a Jellyfin-compatible `[imdbid-tt1234567]` identifier.

The selected identifier is added to both the output folder and the main movie filename when an ID is available. TMDB IDs are captured when TMDB is the metadata provider; with OMDb selected, set `TMDB_API_KEY` to allow ARM to resolve the TMDB ID from the IMDb ID. The folder-ID option defaults to `none`, and existing media is not renamed retroactively.

ARM also normalizes disc-label underscores and illegal filename characters without converting every space into a hyphen, and it no longer shortens legitimate hyphenated titles during metadata fallback. See the [Jellyfin metadata identifier guide](https://jellyfin.org/docs/general/server/metadata/identifiers/).

## Troubleshooting
 [Please see the wiki for troubleshooting](https://github.com/automatic-ripping-machine/automatic-ripping-machine/wiki/).

## Contributing

Pull requests are welcome.  Please see the [Contributing Guide](https://github.com/automatic-ripping-machine/automatic-ripping-machine/wiki/Contributing-Guide)

If you set ARM up in a different environment (hardware/OS/virtual/etc.), please consider [submitting a howto to the wiki](https://github.com/automatic-ripping-machine/automatic-ripping-machine/wiki).

## License

[MIT License](LICENSE)
