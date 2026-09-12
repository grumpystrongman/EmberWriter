from pathlib import Path

from app import storage
from app.voice_fingerprint import MAX_FILES, build_manuscript_voice_sample


def use_temp_data(tmp_path: Path) -> None:
    storage.DATA_ROOT = tmp_path
    storage.PROJECTS_ROOT = tmp_path / "projects"


def test_voice_fingerprint_samples_across_manuscript(tmp_path: Path) -> None:
    use_temp_data(tmp_path)
    project = storage.create_project("Voice Fingerprint Test")
    slug = project["slug"]

    for index in range(1, 17):
        storage.save_text(
            slug,
            f"manuscript/chapter-{index:02d}.md",
            f"# Chapter {index}\n\n" + (f"Distinctive prose from chapter {index}. " * 120),
        )

    sample, sources = build_manuscript_voice_sample(slug)

    assert 2 <= len(sources) <= MAX_FILES
    assert sources[0] == "manuscript/chapter-01.md"
    assert sources[-1] == "manuscript/chapter-16.md"
    assert "SOURCE: manuscript/chapter-01.md" in sample
    assert "SOURCE: manuscript/chapter-16.md" in sample
    assert len(sample) <= 52000


def test_voice_fingerprint_rejects_empty_manuscript(tmp_path: Path) -> None:
    use_temp_data(tmp_path)
    project = storage.create_project("Empty Voice Test")

    try:
        build_manuscript_voice_sample(project["slug"])
    except ValueError as exc:
        assert "No manuscript prose" in str(exc)
    else:
        raise AssertionError("Expected empty manuscript to be rejected")
