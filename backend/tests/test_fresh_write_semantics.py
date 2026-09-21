from pathlib import Path

from app import binder, routes_generation, storage, studio_context
from app.models import CraftControls, GenerateRequest, ProviderConfig


def use_temp_data(tmp_path: Path) -> None:
    storage.DATA_ROOT = tmp_path
    storage.PROJECTS_ROOT = tmp_path / "projects"


def test_write_request_discards_active_prose_and_selection() -> None:
    payload = GenerateRequest(
        prompt="Write a brand-new scene between Rowan and Avery.",
        mode="write",
        active_file="manuscript/chapter-014.md",
        selected_text="OLD PROSE THAT MUST NOT BECOME AN ANCHOR",
        provider=ProviderConfig(model="test-model"),
    )

    assert payload.active_file is None
    assert payload.selected_text == studio_context.STUDIO_CONTEXT_SENTINEL


def test_continue_request_preserves_explicit_continuation_anchor() -> None:
    payload = GenerateRequest(
        prompt="Continue this scene.",
        mode="continue",
        active_file="manuscript/chapter-014.md",
        selected_text="current selection",
        provider=ProviderConfig(model="test-model"),
    )

    assert payload.active_file == "manuscript/chapter-014.md"
    assert payload.selected_text == "current selection"


def test_fresh_write_uses_binder_knowledge_without_old_manuscript_prose(tmp_path: Path) -> None:
    use_temp_data(tmp_path)
    project = storage.create_project("Fresh Binder Context")
    slug = project["slug"]

    storage.save_text(
        slug,
        "manuscript/chapter-001.md",
        "OLD_JAX_BATTLE_CONTAMINATION " + ("Rowan academy gym Tamsin fight " * 300),
    )
    storage.save_text(
        slug,
        "characters/rowan-thorne.md",
        "# Rowan Thorne\n\nAdult protagonist. Attentive, protective, empathic, and responsive.\n",
    )
    storage.save_text(
        slug,
        "characters/avery.md",
        "# Avery\n\nAdult witch. Warm, playful, musical, laughing, tactile, and joyful.\n",
    )
    storage.save_text(
        slug,
        "world/northgate-academy.md",
        "# Northgate Academy\n\nThe academy gym has a cedar sauna beside the training baths.\n",
    )
    storage.save_text(
        slug,
        "notes/avery-sauna-beat.md",
        "# Avery Sauna Beat\n\nAvery uses humor and rhythm when nervous; steam makes amber resonance bead across her skin.\n",
    )
    storage.save_text(
        slug,
        "research/academy-sauna-customs.md",
        "# Academy Sauna Customs\n\nThe sauna is quiet after evening training and students leave towels on the outer hooks.\n",
    )
    binder.sync_binder(slug)

    payload = GenerateRequest(
        prompt=(
            "Write a new scene with Rowan Thorne and Avery in the Northgate Academy sauna after gym training. "
            "Keep Avery playful and musical."
        ),
        mode="write",
        active_file="manuscript/chapter-001.md",
        selected_text="OLD_JAX_BATTLE_CONTAMINATION",
        provider=ProviderConfig(model="test-model"),
        craft=CraftControls(heat_level="inferno"),
    )

    context, files, _ = routes_generation._prepare_generation_context(slug, payload)

    assert "Fresh generation boundary" in context
    assert "OLD_JAX_BATTLE_CONTAMINATION" not in context
    assert not any(path.startswith("manuscript/") for path in files)
    assert "Rowan Thorne" in context
    assert "Avery" in context
    assert "cedar sauna" in context
    assert "humor and rhythm" in context
    assert "Academy Sauna Customs" in context
    assert any(path.startswith("world/") for path in files)
    assert any(path.startswith("notes/") for path in files)
    assert any(path.startswith("research/") for path in files)


def test_explicit_continue_still_uses_latest_active_manuscript_tail(tmp_path: Path) -> None:
    use_temp_data(tmp_path)
    project = storage.create_project("Explicit Continue")
    slug = project["slug"]
    beginning = "OLD_OPENING " + ("history " * 5000)
    ending = "CURRENT_CONTINUATION_POINT " + ("latest " * 800) + " FINAL_LINE_TO_CONTINUE"
    storage.save_text(slug, "manuscript/chapter-001.md", beginning + ending)

    payload = GenerateRequest(
        prompt="Continue from the current ending.",
        mode="continue",
        active_file="manuscript/chapter-001.md",
        provider=ProviderConfig(model="test-model"),
    )

    context, files, _ = routes_generation._prepare_generation_context(slug, payload)

    assert "HIGH-PRIORITY ACTIVE CONTINUATION ANCHOR" in context
    assert "CURRENT_CONTINUATION_POINT" in context
    assert "FINAL_LINE_TO_CONTINUE" in context
    assert "manuscript/chapter-001.md" in files
