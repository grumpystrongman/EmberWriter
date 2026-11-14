"""Portable Series Vault backups with strict integrity and no path extraction.

Exports only the author's series configuration, explicitly imported/linked
source snapshots and the canonical graph. Never exports unrelated projects,
credentials, model settings or project databases. Restores as a NEW series.
"""
from __future__ import annotations

import hashlib
import io
import json
import re
import shutil
import tempfile
import zipfile
from pathlib import Path

from . import series_dialogue_reviews as dialogue_reviews
from . import series_epub_index as epub_index
from . import series_event_reviews as event_reviews
from . import series_scene_studio as scene_studio
from .series_vault import (
    MAX_DOCUMENT_CHARS,
    _connect,
    _id,
    _root,
    _snapshot,
    now,
    series_detail,
    source_text,
)

ARCHIVE_VERSION = 1
MAX_ARCHIVE_BYTES = 250 * 1024 * 1024
MAX_ARCHIVE_ITEMS = 2000
MAX_MANIFEST_BYTES = 12 * 1024 * 1024


def backup(series_id: str) -> Path:
    series = series_detail(series_id)
    with _connect() as con:
        entities = [dict(row) for row in con.execute(
            "SELECT * FROM entities WHERE series_id=? ORDER BY name", (series_id,))]
        facts = [dict(row) for row in con.execute(
            "SELECT * FROM assertions WHERE series_id=? ORDER BY created_at", (series_id,))]
        epub_index._table(con)
        event_reviews._ensure(con)
        epub_indexes = [dict(row) for row in con.execute(
            "SELECT * FROM series_epub_structure_indexes WHERE series_id=? ORDER BY source_id",
            (series_id,))]
        reviewed_events = [dict(row) for row in con.execute(
            "SELECT * FROM series_event_reviews WHERE series_id=? ORDER BY book,quote_start",
            (series_id,))]
        dialogue_reviews._ensure(con)
        reviewed_dialogue = [dict(row) for row in con.execute(
            "SELECT * FROM series_dialogue_reviews WHERE series_id=? ORDER BY book,quote_start",
            (series_id,))]
    sources = []
    for volume in series["volumes"]:
        for source in volume["sources"]:
            record, _ = source_text(series_id, source["id"])
            sources.append({
                key: record[key] for key in
                ("id", "volume_id", "title", "source_path", "sequence",
                 "sha256", "bytes", "created_at")
            })
    metadata = {
        "version": ARCHIVE_VERSION,
        "series": {key: series[key] for key in ("title", "description", "created_at")},
        "volumes": [
            {key: volume[key] for key in
             ("id", "title", "ordinal", "kind", "edition_status", "created_at")}
            for volume in series["volumes"]
        ],
        "sources": sources,
        "entities": entities,
        "assertions": facts,
        "verified_epub_indexes": epub_indexes,
        "author_event_reviews": reviewed_events,
        "author_dialogue_reviews": reviewed_dialogue,
        "scene_boards": scene_studio.list_boards(series_id),
        "note": "Restoring this archive creates a new independent series. "
                "Linked writing projects are not moved; their immutable source "
                "snapshots are included instead.",
    }
    body = json.dumps(metadata, ensure_ascii=False).encode("utf-8")
    if len(body) > MAX_MANIFEST_BYTES:
        raise ValueError("Series metadata exceeds the backup manifest limit")
    export_dir = _root() / "temporary-exports"
    export_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=export_dir, suffix=".zip",
                                     prefix="series-", delete=False) as handle:
        destination = Path(handle.name)
    try:
        total = len(body)
        with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED,
                             compresslevel=6, allowZip64=True) as archive:
            archive.writestr("manifest.json", body)
            for entry in sources:
                _, content = source_text(series_id, entry["id"])
                encoded = content.encode("utf-8")
                total += len(encoded)
                if total > MAX_ARCHIVE_BYTES:
                    raise ValueError("This series is too large for the current backup limit")
                archive.writestr("sources/" + entry["id"] + ".txt", encoded)
        return destination
    except Exception:
        destination.unlink(missing_ok=True)
        raise


def _validate_member_names(items: list[zipfile.ZipInfo]) -> None:
    if len(items) > MAX_ARCHIVE_ITEMS:
        raise ValueError("Archive contains too many files")
    names = [item.filename for item in items]
    if len(names) != len(set(names)):
        raise ValueError("Archive contains duplicate filenames")
    for item in items:
        if (item.flag_bits & 0x1 or not re.fullmatch(
            r"(manifest\.json|sources/[0-9a-f]{32}\.txt)", item.filename
        )):
            raise ValueError("Archive has encrypted or unexpected files")
    if sum(item.file_size for item in items) > MAX_ARCHIVE_BYTES:
        raise ValueError("Archive exceeds the extracted-data safety limit")


def restore(data: bytes, rights_confirmed: bool) -> dict:
    if not rights_confirmed:
        raise ValueError("Confirm you have permission to restore these texts")
    if len(data) > MAX_ARCHIVE_BYTES:
        raise ValueError("Series backup exceeds the 250 MB upload limit")
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except (OSError, zipfile.BadZipFile) as exc:
        raise ValueError("The selected file is not a valid Series Vault archive") from exc
    with archive:
        _validate_member_names(archive.infolist())
        if "manifest.json" not in archive.namelist():
            raise ValueError("Archive manifest is missing")
        if archive.getinfo("manifest.json").file_size > MAX_MANIFEST_BYTES:
            raise ValueError("Archive manifest is too large")
        try:
            manifest = json.loads(archive.read("manifest.json"))
        except (ValueError, UnicodeError) as exc:
            raise ValueError("Archive manifest is invalid") from exc
        if not isinstance(manifest, dict) or manifest.get("version") != ARCHIVE_VERSION:
            raise ValueError("Unsupported Series Vault backup format")
        about = manifest.get("series", {})
        volumes = manifest.get("volumes", [])
        sources = manifest.get("sources", [])
        entities = manifest.get("entities", [])
        assertions = manifest.get("assertions", [])
        scene_boards = manifest.get("scene_boards", [])
        indexes = manifest.get("verified_epub_indexes", [])
        events = manifest.get("author_event_reviews", [])
        dialogue_records = manifest.get("author_dialogue_reviews", [])
        if (not isinstance(indexes, list) or not isinstance(events, list)
                or not isinstance(dialogue_records, list)
                or len(indexes) > 1000 or len(events) > 5000
                or len(dialogue_records) > 5000):
            raise ValueError("Archive includes excessive or invalid review metadata")
        if (not isinstance(about, dict) or not isinstance(volumes, list)
                or not isinstance(sources, list) or not isinstance(entities, list)
                or not isinstance(assertions, list)
                or not isinstance(scene_boards, list) or len(scene_boards) > 200
                or len(sources) > 1000 or len(entities) > 10000
                or len(assertions) > 100000):
            raise ValueError("Archive has invalid record counts")
        title = str(about.get("title", ""))
        description = str(about.get("description", ""))
        if not 1 <= len(title.strip()) <= 160 or len(description) > 2000:
            raise ValueError("Archive series information is invalid")
        volume_ids = {v.get("id") for v in volumes if isinstance(v, dict)}
        source_ids = {s.get("id") for s in sources if isinstance(s, dict)}
        entity_ids = {e.get("id") for e in entities if isinstance(e, dict)}
        if (len(volume_ids) != len(volumes) or len(source_ids) != len(sources)
                or len(entity_ids) != len(entities)
                or not all(re.fullmatch(r"[0-9a-f]{32}", v) for v in volume_ids | source_ids | entity_ids)):
            raise ValueError("Archive has invalid or duplicated record identifiers")
        orders = {int(v["ordinal"]) for v in volumes}
        if len(orders) != len(volumes) or any(not 1 <= n <= 9999 for n in orders):
            raise ValueError("Book order is invalid or duplicated")

        # Validate all sources and citations before creating anything.
        contents = {}
        for source in sources:
            if source.get("volume_id") not in volume_ids:
                raise ValueError("Source refers to a missing book")
            name = "sources/" + source["id"] + ".txt"
            if name not in archive.namelist():
                raise ValueError("A referenced manuscript snapshot is missing")
            encoded = archive.read(name)
            if len(encoded) > MAX_DOCUMENT_CHARS * 4:
                raise ValueError("Snapshot exceeds the per-document limit")
            if hashlib.sha256(encoded).hexdigest() != source.get("sha256"):
                raise ValueError("Source checksum mismatch; restore cancelled")
            value = encoded.decode("utf-8")
            if len(value) > MAX_DOCUMENT_CHARS:
                raise ValueError("Source contains too much text")
            contents[source["id"]] = value
        for fact in assertions:
            if not isinstance(fact, dict) or fact.get("subject_id") not in entity_ids:
                raise ValueError("Canon fact refers to a missing subject")
            if fact.get("object_entity_id") and fact["object_entity_id"] not in entity_ids:
                raise ValueError("Canon fact refers to a missing target")
            if fact.get("knower_id") and fact["knower_id"] not in entity_ids:
                raise ValueError("Canon fact refers to a missing knowledge holder")
            original = contents.get(fact.get("source_id"))
            start, end = fact.get("quote_start"), fact.get("quote_end")
            if (original is None or not isinstance(start, int) or not isinstance(end, int)
                    or not 0 <= start < end <= len(original)
                    or original[start:end] != fact.get("quote")):
                raise ValueError("Canon source citation is invalid; restore cancelled")
            if fact.get("status") not in {"proposed", "approved", "rejected"}:
                raise ValueError("Archive canon review state is invalid")
        # Newer archive fields are optional: existing version-one backups without
        # structural metadata must remain importable. All new metadata is checked
        # against the original immutable snapshots before any series is created.
        source_by_id = {item["id"]: item for item in sources}
        indexed_ids = set()
        for record in indexes:
            if not isinstance(record, dict) or record.get("source_id") not in source_ids:
                raise ValueError("EPUB index references an unknown source")
            sid = record["source_id"]
            if sid in indexed_ids or record.get("source_hash") != source_by_id[sid]["sha256"]:
                raise ValueError("EPUB index has an invalid source fingerprint")
            indexed_ids.add(sid)
            try:
                structural = json.loads(record.get("sections_json", ""))
            except (TypeError, ValueError) as exc:
                raise ValueError("EPUB structural index is malformed") from exc
            if not isinstance(structural, list) or len(structural) > epub_index.epub_structure.MAX_SECTIONS:
                raise ValueError("EPUB index includes excessive sections")
            for item in structural:
                if (not isinstance(item, dict)
                        or type(item.get("start")) is not int or type(item.get("end")) is not int
                        or not 0 <= item["start"] < item["end"] <= len(contents[sid])
                        or not isinstance(item.get("title"), str) or len(item["title"]) > 160):
                    raise ValueError("EPUB index coordinates or labels are invalid")
        reviewed_ids = set()
        for event in events:
            if not isinstance(event, dict) or event.get("source_id") not in source_ids:
                raise ValueError("Event review references a missing source")
            source_id = event["source_id"]
            start, end = event.get("quote_start"), event.get("quote_end")
            if (type(start) is not int or type(end) is not int
                    or not 0 <= start < end <= len(contents[source_id])
                    or contents[source_id][start:end] != event.get("quote")
                    or event.get("source_hash") != source_by_id[source_id]["sha256"]
                    or event.get("status") not in ("proposed", "approved", "rejected")
                    or event.get("event_kind") not in event_reviews.VALID_KINDS
                    or event.get("timeline_class") not in event_reviews.VALID_TIME
                    or not isinstance(event.get("title"), str) or len(event["title"]) > 160
                    or not isinstance(event.get("note"), str) or len(event["note"]) > 1000):
                raise ValueError("Event review quote or metadata did not verify")
            identity = (source_id, start, end)
            if identity in reviewed_ids:
                raise ValueError("Duplicate event review coordinates")
            reviewed_ids.add(identity)
        # Dialogue decisions are optional in older archives, but cannot be
        # imported without exact source text or an existing character reference.
        reviewed_dialogue_ids = set()
        character_ids = {entity['id'] for entity in entities
                         if entity.get('kind') == 'character'}
        for record in dialogue_records:
            if not isinstance(record, dict) or record.get('source_id') not in source_ids:
                raise ValueError('Dialogue review references unknown source')
            sid = record['source_id']
            start, end = record.get('quote_start'), record.get('quote_end')
            speaker = record.get('speaker_id')
            if (type(start) is not int or type(end) is not int
                    or not 0 <= start < end <= len(contents[sid])
                    or contents[sid][start:end] != record.get('quote')
                    or record.get('source_hash') != source_by_id[sid]['sha256']
                    or record.get('status') not in dialogue_reviews.STATUS
                    or record.get('pov_class') not in dialogue_reviews.POV
                    or (speaker is not None and speaker not in character_ids)
                    or (record.get('status') == 'approved' and speaker is None)
                    or not isinstance(record.get('note'), str)
                    or len(record['note']) > 1000):
                raise ValueError('Dialogue review source, speaker or POV failed verification')
            identity = (sid, start, end)
            if identity in reviewed_dialogue_ids:
                raise ValueError('Duplicate dialogue attribution evidence')
            reviewed_dialogue_ids.add(identity)
        # Scene boards are noncanonical author drafts. Validate the full record
        # before touching the destination, then remap entity IDs on restore.
        character_ids = {e["id"] for e in entities if e.get("kind") == "character"}
        place_ids = {e["id"] for e in entities if e.get("kind") == "place"}
        for board in scene_boards:
            if not isinstance(board, dict) or not isinstance(board.get("book"), int) or board["book"] not in orders:
                raise ValueError("Archive contains an invalid scene board book")
            if not isinstance(board.get("sequence"), int) or not 0 <= board["sequence"] <= 999999:
                raise ValueError("Archive contains an invalid scene board position")
            participants = board.get("participants")
            if not isinstance(participants, list) or len(participants) > 20 or len(set(participants)) != len(participants) or any(p not in character_ids for p in participants):
                raise ValueError("Archive contains a scene board with missing cast")
            if (board.get("pov_id") and board["pov_id"] not in character_ids) or (board.get("location_id") and board["location_id"] not in place_ids):
                raise ValueError("Archive scene board refers to an unknown location or POV")
            if not 1 <= len(str(board.get("title", "")).strip()) <= 160:
                raise ValueError("Archive contains a scene board with an invalid title")
            for field, maximum in (("objective", 1200), ("conflict", 1200), ("opening", 1600), ("aftermath", 1600), ("voice_notes", 1200)):
                if not isinstance(board.get(field, ""), str) or len(board.get(field, "")) > maximum:
                    raise ValueError("Archive contains a scene board with invalid notes")
            beats = board.get("beats")
            if not isinstance(beats, list) or not 1 <= len(beats) <= 24:
                raise ValueError("Archive contains an invalid dramatic beat board")
            beat_ids = set()
            for beat in beats:
                if not isinstance(beat, dict) or not isinstance(beat.get("id"), str) or not re.fullmatch(r"[a-zA-Z0-9_-]{1,64}", beat["id"]):
                    raise ValueError("Archive contains an invalid beat identifier")
                beat_ids.add(beat["id"])
                if (beat.get("kind") not in scene_studio.BEAT_KINDS
                    or not isinstance(beat.get("title"), str) or not 1 <= len(beat["title"].strip()) <= 120
                    or not isinstance(beat.get("detail"), str) or len(beat["detail"]) > 1200
                    or type(beat.get("pressure")) is not int or not 0 <= beat["pressure"] <= 100):
                    raise ValueError("Archive contains an invalid scene beat")
            if len(beat_ids) != len(beats):
                raise ValueError("Archive contains repeated beat identifiers")
        # All validation has completed. Create only a new ID namespace.
        series_id = _id()
        volume_map = {old: _id() for old in volume_ids}
        source_map = {old: _id() for old in source_ids}
        entity_map = {old: _id() for old in entity_ids}
        created_volumes = []
        try:
            with _connect() as con:
                con.execute(
                    "INSERT INTO series VALUES (?,?,?,?)",
                    (series_id, title.strip(), description.strip(), now()),
                )
                for volume in volumes:
                    con.execute(
                        "INSERT INTO volumes VALUES (?,?,?,?,?,?,?,?)",
                        (volume_map[volume["id"]], series_id, volume["title"],
                         volume["ordinal"], volume["kind"], volume["edition_status"],
                         None, now()),
                    )
                for source in sources:
                    new_id = source_map[source["id"]]
                    new_volume = volume_map[source["volume_id"]]
                    snapshot = _snapshot(new_volume, new_id, contents[source["id"]])
                    created_volumes.append(new_volume)
                    con.execute(
                        "INSERT INTO sources VALUES (?,?,?,?,?,?,?,?,?)",
                        (new_id, new_volume, source["title"], source["source_path"],
                         source["sequence"], snapshot, source["sha256"],
                         source["bytes"], now()),
                    )
                for entity in entities:
                    con.execute(
                        "INSERT INTO entities VALUES (?,?,?,?,?,?,?)",
                        (entity_map[entity["id"]], series_id, entity["name"],
                         entity["kind"], entity["aliases"], entity["description"], now()),
                    )
                for fact in assertions:
                    con.execute("""
                        INSERT INTO assertions (
                            id,series_id,subject_id,predicate,object_text,object_entity_id,
                            scope,knower_id,start_book,start_sequence,end_book,end_sequence,
                            source_id,quote_start,quote_end,quote,status,note,created_at
                        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """, (
                        _id(), series_id, entity_map[fact["subject_id"]],
                        fact["predicate"], fact["object_text"],
                        entity_map.get(fact.get("object_entity_id")),
                        fact["scope"], entity_map.get(fact.get("knower_id")),
                        fact["start_book"], fact["start_sequence"],
                        fact["end_book"], fact["end_sequence"],
                        source_map[fact["source_id"]], fact["quote_start"],
                        fact["quote_end"], fact["quote"], fact["status"],
                        fact["note"], now(),
                    ))
                epub_index._table(con)
                event_reviews._ensure(con)
                dialogue_reviews._ensure(con)
                for record in indexes:
                    con.execute("""
                        INSERT INTO series_epub_structure_indexes
                        (source_id,series_id,source_hash,epub_hash,sections_json,saved_at)
                        VALUES (?,?,?,?,?,?)
                    """, (
                        source_map[record["source_id"]], series_id,
                        record["source_hash"], record["epub_hash"],
                        record["sections_json"], now(),
                    ))
                for event in events:
                    con.execute("""
                        INSERT INTO series_event_reviews (
                            id,series_id,source_id,source_hash,book,
                            quote_start,quote_end,quote,title,event_kind,
                            timeline_class,note,status,created_at,reviewed_at
                        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """, (
                        _id(), series_id, source_map[event["source_id"]],
                        event["source_hash"], event["book"],
                        event["quote_start"], event["quote_end"], event["quote"],
                        event["title"], event["event_kind"],
                        event["timeline_class"], event["note"],event["status"],
                        now(), now() if event["reviewed_at"] else None,
                    ))
                for record in dialogue_records:
                    con.execute('''
                        INSERT INTO series_dialogue_reviews (
                            id,series_id,source_id,source_hash,book,quote_start,
                            quote_end,quote,speaker_id,pov_class,note,status,
                            created_at,reviewed_at
                        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    ''', (
                        _id(),series_id,source_map[record['source_id']],
                        record['source_hash'],record['book'],
                        record['quote_start'],record['quote_end'],record['quote'],
                        entity_map.get(record['speaker_id']),record['pov_class'],
                        record['note'],record['status'],now(),
                        now() if record['reviewed_at'] else None,
                    ))
        except Exception:
            for volume_id in set(created_volumes):
                shutil.rmtree(_root() / "snapshots" / volume_id, ignore_errors=True)
            raise
        try:
            for board in scene_boards:
                scene_studio.create_board(series_id, {
                    **{key: board.get(key, "") for key in ("title", "objective", "conflict", "opening", "aftermath", "voice_notes")},
                    "book": board["book"], "sequence": board["sequence"],
                    "pov_id": entity_map.get(board.get("pov_id")),
                    "location_id": entity_map.get(board.get("location_id")),
                    "participants": [entity_map[p] for p in board["participants"]],
                    "beats": board["beats"],
                })
        except Exception:
            # Do not leave an apparently successful but incomplete restore.
            from .series_vault import delete_series
            delete_series(series_id, title)
            raise
    return series_detail(series_id)
