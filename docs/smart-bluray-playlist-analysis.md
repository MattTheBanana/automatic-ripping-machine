# Smart Blu-ray playlist analysis and incremental ripping

ARM stores the playlist ID (MakeMKV TINFO attribute 16) and ordered segment map (TINFO attribute 26) for each title.

## Candidate warnings and Main Feature selection

When SMART_DISC_ANALYSIS is enabled, ARM compares titles with nearly identical duration, expected size and chapter count. When both have segment maps, it reports whether they have the same ordered map or diverge (including the first differing position). This compares titles such as 00778.mpls and 00795.mpls using actual segment order instead of title number alone.

MAINFEATURE selection prioritizes titles MakeMKV labels MainFeature only when their runtime is close to the longest title. Duration, expected size, chapter count and numeric title ID break ties. ARM logs each candidate's playlist and segment sequence where present. This remains a heuristic: the user-visible runtime from a physical player and checking the segments against the actual movie are still the decisive validation. ARM never suppresses a candidate solely because its metadata resembles another title.

## Incremental rip mode

Set INCREMENTAL_RIPPING: true to rip one title at a time and skip titles recorded as successful whose expected output file is still present and non-empty under the completed-media directory. ARM stores one JSON inventory per detected disc layout below LOGPATH/disc-inventory/; records include title fingerprints, playlists and segment maps.

A title is added to the inventory only after MakeMKV returns successfully and a non-empty source file exists. Failed titles and titles without a verified output are retried. The feature defaults off. The inventory is local to ARM and does not upload disc labels, titles, playlists, segments, or other media information.

This implementation does not include a hosted crowd-sourced database or any automatic submission. Such a service needs a real endpoint, a clear privacy contract, versioned data, and an explicit opt-in before ARM should submit disc fingerprints or reports.
