"""Stage 4 failure-injection: preserve author manuscripts on write failure.

Synthetic temporary project only. These are targeted atomic-write checks,
not a claim that global multi-window concurrency is implemented.
"""
from __future__ import annotations

import errno

import pytest

from app import storage


@pytest.fixture
def author_project(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "PROJECTS_ROOT", tmp_path / "isolated-projects")
    slug = storage.create_project("Synthetic Disk Error QA")
    slug = slug["slug"]
    filename = "manuscript/chapter-001.md"
    original = "# First draft\n\nThis is the untouched baseline.\n"
    storage.save_text(slug, filename, original)
    return slug, filename, original


@pytest.mark.parametrize("failure_point", ["fsync", "replace"])
def test_failed_manuscript_write_preserves_original_and_removes_temp(
    author_project, monkeypatch, failure_point
):
    slug, filename, original = author_project
    source = storage.safe_project_path(slug, filename)
    original_bytes = source.read_bytes()

    def disk_full(*_args, **_kwargs):
        raise OSError(errno.ENOSPC, "Synthetic disk full")

    monkeypatch.setattr(storage.os, failure_point, disk_full)
    with pytest.raises(OSError, match="Synthetic disk full"):
        storage.save_text(slug, filename, "# Invalid replacement\n")

    assert source.read_bytes() == original_bytes
    assert storage.read_text(slug, filename) == original
    assert list(source.parent.glob("*.partial")) == []


def test_failed_metadata_replacement_keeps_previous_project_record(
    author_project, monkeypatch
):
    slug, _, _ = author_project
    project = storage.project_root(slug) / "project.json"
    before = project.read_bytes()

    def fail_replace(*_args, **_kwargs):
        raise OSError(errno.ENOSPC, "Synthetic metadata disk full")

    monkeypatch.setattr(storage.os, "replace", fail_replace)
    with pytest.raises(OSError, match="Synthetic metadata disk full"):
        storage._touch_project(slug)

    assert project.read_bytes() == before
    assert list(project.parent.glob("*.partial")) == []
