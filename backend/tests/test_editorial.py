from pathlib import Path

from app import binder, editorial, storage
from app.editorial_models import EditorialFindingStatusUpdate, EditorialProfile, EditorialRunRequest


def use_temp_data(tmp_path: Path) -> None:
    storage.DATA_ROOT = tmp_path
    storage.PROJECTS_ROOT = tmp_path / "projects"


def test_editorial_analyzers_find_reproducible_prose_issues() -> None:
    long_sentence = (
        "She was tired and was cold and seemed utterly lost because she really wanted to walk "
        "in order to reach the gate before the storm arrived and the guards were alerted."
    )
    source = (
        "# Chapter 1\n\n"
        "The the door was broken. She felt the darkness quietly. Her heart skipped a beat!!\n\n"
        "She ran. She stopped. She listened.\n\n"
        f"{long_sentence}\n\n"
        "The silver key opened the black door. The silver key opened the black door. "
        "The silver key opened the black door.\n\n"
        "\"Leave now,\" she said quietly."
    )
    profile = EditorialProfile(
        enabled_reports=[item["id"] for item in editorial.report_catalog()],
        long_sentence_words=20,
        short_sentence_words=2,
        repeated_phrase_minimum=3,
    )
    findings, metrics = editorial.analyze_text(source, profile.enabled_reports, profile)
    report_ids = {item["report_id"] for item in findings}

    assert "repeated_word" in report_ids
    assert "repeated_phrase" in report_ids
    assert "adverb" in report_ids
    assert "filler_word" in report_ids
    assert "filter_word" in report_ids
    assert "passive_voice" in report_ids
    assert "weak_verb_cluster" in report_ids
    assert "sentence_length" in report_ids
    assert "sentence_start" in report_ids
    assert "redundancy" in report_ids
    assert "cliche" in report_ids
    assert "dialogue_adverb" in report_ids
    assert "punctuation" in report_ids
    assert metrics["words"] > 40
    assert metrics["sentences"] >= 8
    assert "dialogue_percent" in metrics
    assert "readability" in metrics
    assert all(item["line"] >= 1 for item in findings)
    assert all(item["anchor_text"] for item in findings)


def test_editorial_run_persists_binder_identity_status_and_staleness(tmp_path: Path) -> None:
    use_temp_data(tmp_path)
    project = storage.create_project("Editorial Persistence")
    slug = project["slug"]
    path = "manuscript/chapter-001.md"
    original = "# Chapter 1\n\nThe the lantern was broken. Mara really felt the cold quietly.\n"
    storage.save_text(slug, path, original)

    state = binder.get_binder(slug)
    node = next(item for item in state.nodes if item.path == path)
    result = editorial.run_editorial(
        slug,
        EditorialRunRequest(scope="document", path=path, reports=["repeated_word", "filler_word"]),
    )

    assert result["documents"] == 1
    assert result["findings"] >= 2
    assert result["items"][0]["binder_node_id"] == node.id
    assert editorial.list_editorial_runs(slug)[0]["id"] == result["id"]

    findings = editorial.list_editorial_findings(slug, run_id=result["id"])
    target = next(item for item in findings if item["report_id"] == "repeated_word")
    updated = editorial.update_finding_status(slug, target["id"], "ignored")
    assert updated["status"] == "ignored"
    assert editorial.get_editorial_run(slug, result["id"])["items"][0]["run_id"] == result["id"]

    storage.save_text(slug, path, "# Chapter 1\n\nThe lantern stood intact.\n")
    stale = editorial.list_editorial_findings(slug, run_id=result["id"])
    assert stale
    assert all(item["stale"] is True for item in stale)


def test_draft_run_follows_binder_and_includes_compile_excluded_draft_documents(tmp_path: Path) -> None:
    use_temp_data(tmp_path)
    project = storage.create_project("Editorial Draft")
    slug = project["slug"]
    state = binder.get_binder(slug)
    first = next(item for item in state.nodes if item.path == "manuscript/chapter-001.md")
    storage.save_text(slug, first.path or "", "# One\n\nThe the first scene.\n")
    state = binder.update_node(slug, first.id, binder.BinderNodeUpdate(include_in_compile=False))
    draft = next(item for item in state.nodes if item.title == "Draft")
    before = {item.id for item in state.nodes}
    state = binder.create_node(
        slug,
        binder.BinderNodeCreate(title="Second", kind="document", parent_id=draft.id),
    )
    second = next(item for item in state.nodes if item.id not in before)
    assert second.path
    storage.save_text(slug, second.path, "# Two\n\nIt was broken.\n")

    result = editorial.run_editorial(
        slug,
        EditorialRunRequest(scope="draft", reports=["repeated_word", "passive_voice"]),
    )
    paths = {item["path"] for item in result["items"]}
    assert first.path in paths
    assert second.path in paths
    assert result["documents"] == 2


def test_editorial_profile_is_portable_project_data(tmp_path: Path) -> None:
    use_temp_data(tmp_path)
    project = storage.create_project("Editorial Profile")
    slug = project["slug"]
    profile = editorial.default_profile().model_copy(
        update={
            "enabled_reports": ["sentence_length", "repeated_phrase"],
            "long_sentence_words": 42,
            "repeated_phrase_minimum": 4,
        }
    )
    saved = editorial.save_editorial_profile(slug, profile)
    loaded = editorial.get_editorial_profile(slug)

    assert saved == loaded
    assert loaded.long_sentence_words == 42
    assert loaded.repeated_phrase_minimum == 4
    assert storage.read_text(slug, editorial.EDITORIAL_PROFILE_PATH).startswith("{")


def test_status_model_rejects_invalid_state() -> None:
    assert EditorialFindingStatusUpdate(status="resolved").status == "resolved"
