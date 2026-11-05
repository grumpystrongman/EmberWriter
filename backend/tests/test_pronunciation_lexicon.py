"""Phoneme dictionary applies author chosen IPA, never homophone-wide changes."""
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app import audio_production, kokoro_book, storage
from app.main import app
from app.pronunciation_lexicon import phonemize_author_text, validate_rule


class TestTokenizer:
    def phonemize(self, text, lang):
        return text.replace("boys", "boys-default").replace("buoys", "boyz-default")
    def known(self, chars):
        return chars


def test_custom_ipa_touches_buoys_but_not_boys():
    tokenizer = TestTokenizer()
    result = phonemize_author_text("The buoys were near the boys.",
                                   [{"written": "buoys", "ipa": "bˈuːiz"}],
                                   tokenizer, "en-us")
    assert "bˈuːiz" in result
    assert "boys-default" in result
    assert "boyz-default" not in result
    assert validate_rule("buoys", "bˈuːiz") == ("buoys", "bˈuːiz")


def test_ipa_settings_persist_and_override_old_english_respellings(tmp_path: Path):
    with patch.object(storage, "PROJECTS_ROOT", tmp_path / "projects"):
        slug = storage.create_project("IPA author library")["slug"]
        path = "manuscript/ch1.md"
        storage.save_text(slug, path, "# Chapter One\n\nThe buoys were beside the boys.")
        audio_production.save_pronunciation(slug, "buoys", "boo-eez")
        result = audio_production.save_ipa_pronunciation(slug, "buoys", "bˈuːiz")
        assert result["ipa_pronunciations"] == [{"written": "buoys", "ipa": "bˈuːiz"}]
        assert audio_production.load(slug)["ipa_pronunciations"] == result["ipa_pronunciations"]
        planned = kokoro_book._chapter_chunks(
            "The buoys were beside the boys.", [],
            {"Narrator": {"voice_id": "af_heart", "speed": 1.0}},
            path, audio_production.load(slug)["pronunciations"],
            audio_production.load(slug)["ipa_pronunciations"],
        )
        assert "buoys" in planned[0]["text"]
        assert planned[0]["ipa_rules"][0]["ipa"] == "bˈuːiz"
        assert "boys" in planned[0]["text"]
        with TestClient(app) as client:
            response = client.get(f"/api/projects/{slug}/audiobook-production/pronunciation-reference")
            assert response.status_code == 200, response.text
            assert response.json()["examples"][1]["written"] == "buoys"
            response = client.put(f"/api/projects/{slug}/audiobook-production/ipa-pronunciations",
                                  json={"written": "buoy", "ipa": "bˈuːi"})
            assert response.status_code == 200, response.text
            assert len(response.json()["ipa_pronunciations"]) == 2
            response = client.delete(f"/api/projects/{slug}/audiobook-production/ipa-pronunciations/buoy")
            assert response.status_code == 200, response.text
        assert len(audio_production.load(slug)["ipa_pronunciations"]) == 1


def test_invalid_ipa_and_unknown_characters_fail_closed():
    for wrong in ("", "boo ee", "<script>", "b/oi", "b\niz"):
        try:
            validate_rule("buoys", wrong)
        except ValueError:
            continue
        raise AssertionError("Invalid phoneme accepted: " + wrong)

    class NarrowTokenizer(TestTokenizer):
        def known(self, chars):
            return chars.replace("☃", "")

    try:
        phonemize_author_text("buoys", [{"written": "buoys", "ipa": "b☃u"}],
                              NarrowTokenizer(), "en-us")
    except ValueError as exc:
        assert "unsupported" in str(exc)
    else:
        raise AssertionError("Unsupported phoneme was silently dropped")


def test_bundled_cmu_dictionary_buoys_is_requested_american_pronunciation():
    from app.pronunciation_lexicon import dictionary_lookup

    singular = dictionary_lookup("buoy")
    plural = dictionary_lookup("buoys")
    assert any(row["arpa"] == "B UW1 IY0" for row in singular["variants"])
    assert any(row["arpa"] == "B UW1 IY0 Z" for row in plural["variants"])
    assert any(row["ipa"] == "bˈuːi" for row in singular["variants"])
    assert any(row["ipa"] == "bˈuːiz" for row in plural["variants"])
    with TestClient(app) as client:
        response = client.get("/api/projects/any/audiobook-production/pronunciation-dictionary",
                              params={"word": "buoys"})
        assert response.status_code == 200
        assert any(row["ipa"] == "bˈuːiz" for row in response.json()["variants"])
