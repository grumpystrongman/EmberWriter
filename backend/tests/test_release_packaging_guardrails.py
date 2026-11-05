"""Release packaging must reject unsafe cover assets and colliding ZIP paths."""
from pathlib import Path

import pytest
from PIL import Image
from test_distribution import make_ebook_files, use_temp_data

from app import distribution
from app.release_models import ReleaseEdition, ReleaseProfile


def _profile(interior: str, cover: str, *, edition_id: str = "ebook") -> ReleaseProfile:
    return ReleaseProfile(
        title="The Test Book", author="A. Writer",
        description="An artificial test manuscript.",
        editions=[ReleaseEdition(
            id=edition_id, format="ebook", retailers=["kdp"],
            interior_path=interior, cover_path=cover,
            identifier_mode="none", price=4.99,
        )],
    )


def test_kdp_ebook_rejects_selected_undersized_cover(tmp_path: Path):
    slug = use_temp_data(tmp_path)
    interior, cover = make_ebook_files(slug)
    image = distribution.project_root(slug) / cover
    Image.new("RGB", (400, 650), "white").save(image, "JPEG")
    result = distribution.validate_release(slug, _profile(interior, cover))
    assert not result.valid
    assert "ebook-cover-too-small" in {issue.code for issue in result.issues}
    with pytest.raises(ValueError, match="cover"):
        distribution.build_release_package(slug, _profile(interior, cover))


def test_retailer_cover_ratio_warning_uses_actual_file(tmp_path: Path):
    slug = use_temp_data(tmp_path)
    interior, cover = make_ebook_files(slug)
    image = distribution.project_root(slug) / cover
    Image.new("RGB", (1800, 1800), "white").save(image, "JPEG")
    result = distribution.validate_release(slug, _profile(interior, cover))
    assert result.valid
    assert "kdp-ebook-cover-ratio" in {issue.code for issue in result.issues}


def test_package_path_collision_rejected_before_zip_creation(tmp_path: Path):
    slug = use_temp_data(tmp_path)
    interior, cover = make_ebook_files(slug)
    profile = _profile(interior, cover, edition_id="ebook/one")
    twin = profile.editions[0].model_copy(update={"id": "ebook-one"})
    profile = profile.model_copy(update={"editions": [*profile.editions, twin]})
    result = distribution.validate_release(slug, profile)
    assert not result.valid
    assert "package-edition-collision" in {issue.code for issue in result.issues}
    with pytest.raises(ValueError, match="overwrite"):
        distribution.build_release_package(slug, profile)
