# Configuring audio/dub and subtitle languages

ARM exposes two fields under **Settings → Ripper Settings**:

- `RIP_AUDIO_LANGUAGES`: languages to retain for audio and dubbed audio tracks.
- `RIP_SUBTITLE_LANGUAGES`: languages to retain for subtitle tracks.

Set either field to `all` to preserve every language, or enter a comma-separated list of ISO 639-2 three-letter language codes, such as `eng,spa,fra`. These settings are independent, so audio can be kept in all languages while subtitles are limited to English and Spanish, or vice versa. The default for both fields is `all`.

ARM applies these settings to MakeMKV's `app_DefaultSelectionString` in `/home/arm/.MakeMKV/settings.conf` and to HandBrake's track-selection arguments. ARM updates only that MakeMKV preference and preserves the registration key and other settings. The settings are applied when a rip starts; no MakeMKV graphical interface is required.

HandBrake's language-selection flags in `HB_ARGS_DVD` and `HB_ARGS_BD` are superseded by these explicit settings. Other HandBrake arguments remain in effect. In particular, ARM removes the default forced-only/scan subtitle selection flags so they do not conflict with keeping all subtitle tracks.

When using MakeMKV's full-disc backup mode, MakeMKV copies the disc structure; track-language selection takes effect when HandBrake selects tracks for the transcoded output. If transcoding is skipped, MakeMKV's selection rule governs audio and subtitle streams included in the output files.

All-language mode may retain commentary tracks, alternate dubs, and extra subtitle tracks, increasing the final file size. HandBrake can only pass through subtitle formats supported by the selected output workflow; the intermediate MakeMKV files retain tracks that MakeMKV successfully extracts.
