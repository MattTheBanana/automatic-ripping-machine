"""Blu-ray playlist analysis and a conservative local incremental-rip inventory."""
import hashlib
import json
import logging
import os
import re
import tempfile


_MAIN_FEATURE_RE = re.compile(r"main[\\W_]*feature", re.IGNORECASE)
_GENERIC_LABELS = {"", "none", "unknown", "not identified", "unidentified", "video", "bluray", "blu-ray"}


def parse_segment_map(value):
    """Normalize MakeMKV's TINFO attribute 26 into an ordered tuple of segment IDs."""
    if isinstance(value, (tuple, list)):
        parts = value
    else:
        parts = str(value or "").split(",")
    segments = []
    for part in parts:
        match = re.fullmatch(r"\\s*(\\d+)\\s*", str(part))
        if match:
            segments.append(int(match.group(1)))
    return tuple(segments)


def _number(value, default=0):
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return default


def track_data(track):
    """Return stable MakeMKV metadata used for comparisons and local fingerprints."""
    return {
        "track_number": str(getattr(track, "track_number", "") or ""),
        "filename": os.path.basename(str(getattr(track, "filename", "") or "")),
        "playlist": str(getattr(track, "playlist", "") or "").strip(),
        "segment_map": list(parse_segment_map(getattr(track, "segment_map", ""))),
        "length": _number(getattr(track, "length", 0)),
        "filesize": _number(getattr(track, "filesize", 0)),
        "chapters": _number(getattr(track, "chapters", 0)),
    }


def track_fingerprint(track):
    """Fingerprint a title using the playlist, ordered segments, and MakeMKV metadata."""
    payload = json.dumps(track_data(track), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _filename_is_main_feature(track):
    names = (
        str(getattr(track, "filename", "") or ""),
        str(getattr(track, "playlist", "") or ""),
    )
    return any(_MAIN_FEATURE_RE.search(name) for name in names)


def rank_main_feature_candidates(tracks):
    """Rank likely feature candidates without silently declaring any title genuine.

    A MakeMKV MainFeature label is prioritized only for titles within 1.5% of the
    longest duration. Duration, expected size, chapters, and numeric title ID are
    tie-breakers. The result is a recommendation, not proof that the title is genuine.
    """
    candidates = list(tracks)
    if not candidates:
        return []
    longest = max(_number(getattr(track, "length", 0)) for track in candidates)
    tolerance = max(2, int(longest * 0.015))

    def key(track):
        length = _number(getattr(track, "length", 0))
        labelled = _filename_is_main_feature(track) and longest - length <= tolerance
        track_number = str(getattr(track, "track_number", "") or "")
        try:
            numeric_track_number = int(track_number)
        except (TypeError, ValueError):
            numeric_track_number = 2**31 - 1
        return (
            0 if labelled else 1,
            -length,
            -_number(getattr(track, "filesize", 0)),
            -_number(getattr(track, "chapters", 0)),
            numeric_track_number,
            track_number,
        )

    return sorted(candidates, key=key)


def analyze_title_candidates(tracks, duration_tolerance=3, size_tolerance=0.03):
    """Find close-sized titles and compare their ordered segment maps.

    Duration and size are a screening heuristic, not evidence a playlist is fake.
    Different segment order is highlighted when two such candidates exist; ARM
    never discards a candidate automatically.
    """
    candidates = []
    for track in tracks:
        data = track_data(track)
        if data["length"] > 0 and data["filesize"] > 0:
            candidates.append((track, data))

    warnings = []
    for index, (left, a) in enumerate(candidates):
        for right, b in candidates[index + 1:]:
            if a["track_number"] == b["track_number"]:
                continue
            if abs(a["length"] - b["length"]) > duration_tolerance:
                continue
            if a["chapters"] and b["chapters"] and a["chapters"] != b["chapters"]:
                continue
            size_delta = abs(a["filesize"] - b["filesize"]) / max(a["filesize"], b["filesize"])
            if size_delta > size_tolerance:
                continue

            left_map, right_map = tuple(a["segment_map"]), tuple(b["segment_map"])
            if left_map and right_map:
                if left_map == right_map:
                    kind = "same_segment_map"
                    message = "matching ordered segment maps; titles may be equivalent variants"
                else:
                    kind = "different_segment_maps"
                    first_difference = next(
                        (i for i, pair in enumerate(zip(left_map, right_map)) if pair[0] != pair[1]),
                        min(len(left_map), len(right_map)),
                    )
                    message = (
                        "near-identical runtime/size but different ordered segment maps "
                        f"(first difference at position {first_difference + 1})"
                    )
            else:
                kind = "metadata_only"
                message = "near-identical runtime/size but complete segment-map data is unavailable"

            warnings.append({
                "kind": kind,
                "left": a,
                "right": b,
                "message": message,
            })
    return warnings


def disc_fingerprint(label, title, disc_type, tracks, makemkv_disc_title=None):
    """Build a stable inventory ID from disc labels plus the full MakeMKV title layout."""
    safe_label = str(label or "").strip().casefold()
    safe_title = str(title or "").strip().casefold()
    safe_makemkv_title = str(makemkv_disc_title or "").strip().casefold()
    if safe_label in _GENERIC_LABELS:
        safe_label = safe_title or safe_makemkv_title
    identity = {
        "label_or_title": safe_label,
        "disc_type": str(disc_type or "").strip().casefold(),
        "makemkv_disc_title": safe_makemkv_title,
        "titles": sorted(
            (track_data(track) for track in tracks),
            key=lambda item: (item["track_number"], item["playlist"], item["filename"]),
        ),
    }
    payload = json.dumps(identity, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class DiscRipInventory:
    """Local manifest of successful title rips, only skipping a verified present output.

    The manifest lives in LOGPATH, outside temporary rip folders. It has a separate
    JSON file per disc fingerprint and is saved atomically. Failed reads and empty
    source files are never marked as complete. A later run skips a title only while
    an expected filename is still present and non-empty under COMPLETED_PATH.
    """

    def __init__(
        self, inventory_root, completed_root, label, title, disc_type, tracks, makemkv_disc_title=None
    ):
        self.inventory_root = os.path.abspath(inventory_root) if inventory_root else None
        self.completed_root = os.path.abspath(completed_root) if completed_root else None
        self.fingerprint = disc_fingerprint(
            label, title, disc_type, tracks, makemkv_disc_title=makemkv_disc_title
        )
        self.path = (
            os.path.join(self.inventory_root, f"{self.fingerprint}.json")
            if self.inventory_root else None
        )
        self.data = {"version": 1, "disc_fingerprint": self.fingerprint, "tracks": {}}
        self._existing_names = set()
        self._existing_stems = set()
        self._load()
        self._index_completed_files()

    def _load(self):
        if not self.path:
            return
        try:
            with open(self.path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
            if (
                isinstance(data, dict)
                and data.get("version") == 1
                and data.get("disc_fingerprint") == self.fingerprint
                and isinstance(data.get("tracks"), dict)
            ):
                self.data = data
        except FileNotFoundError:
            return
        except (OSError, ValueError, TypeError) as error:
            logging.warning("Ignoring invalid ARM disc inventory %s: %s", self.path, error)

    def _index_completed_files(self):
        if not self.completed_root or not os.path.isdir(self.completed_root):
            return
        for root, _directories, filenames in os.walk(self.completed_root):
            for filename in filenames:
                if filename.startswith("."):
                    continue
                full_path = os.path.join(root, filename)
                try:
                    if not os.path.isfile(full_path) or os.path.getsize(full_path) <= 0:
                        continue
                except OSError:
                    continue
                folded = filename.casefold()
                self._existing_names.add(folded)
                self._existing_stems.add(os.path.splitext(folded)[0])

    def has_successful_output(self, track):
        """Return true only when a prior success record and its output still exist."""
        record = self.data["tracks"].get(track_fingerprint(track))
        if not record:
            return False
        for alias in record.get("aliases", []):
            basename = os.path.basename(str(alias)).casefold()
            if basename and (
                basename in self._existing_names
                or os.path.splitext(basename)[0] in self._existing_stems
            ):
                return True
        return False

    def record_success(self, track, source_path, aliases=()):
        """Record a title only if MakeMKV succeeded and its source file is non-empty."""
        if not self.path or not source_path:
            return False
        try:
            if not os.path.isfile(source_path) or os.path.getsize(source_path) <= 0:
                return False
        except OSError:
            return False

        names = {os.path.basename(str(getattr(track, "filename", "") or ""))}
        names.update(os.path.basename(str(alias)) for alias in aliases if alias)
        names.discard("")
        self.data["tracks"][track_fingerprint(track)] = {
            "track_number": str(getattr(track, "track_number", "") or ""),
            "playlist": str(getattr(track, "playlist", "") or ""),
            "segment_map": list(parse_segment_map(getattr(track, "segment_map", ""))),
            "aliases": sorted(names),
        }
        try:
            os.makedirs(self.inventory_root, exist_ok=True)
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", dir=self.inventory_root,
                prefix=".arm-disc-inventory-", suffix=".tmp", delete=False
            ) as handle:
                temporary_path = handle.name
                json.dump(self.data, handle, indent=2, sort_keys=True)
                handle.write("\\n")
            os.replace(temporary_path, self.path)
        except OSError as error:
            logging.warning("Could not save ARM disc inventory %s: %s", self.path, error)
            try:
                if "temporary_path" in locals() and os.path.exists(temporary_path):
                    os.unlink(temporary_path)
            except OSError:
                pass
            return False
        return True
