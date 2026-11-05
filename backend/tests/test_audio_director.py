import importlib.util
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location('audio_director', Path(__file__).resolve().parents[1] / 'app' / 'audio_director.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
compile_performance, validate = module.compile_performance, module.validate


class AudioDirectorTests(unittest.TestCase):
    def test_lossless_and_explicit_voices(self):
        source = 'Mara said, "Help!" Ivo replied, "I am here."'
        cue = compile_performance(source, ["Mara", "Ivo"])
        self.assertEqual([s["speaker"] for s in cue["spans"] if s["kind"] == "dialogue"], ["Mara", "Ivo"])
        self.assertTrue(cue["render_ready"])
        validate(cue, source, {"Narrator": {}, "Mara": {}, "Ivo": {}})

    def test_ambiguous_never_defaults_to_narrator(self):
        source = 'Mara looked up. "Who is there?"'
        cue = compile_performance(source, ["Mara"])
        self.assertFalse(cue["render_ready"])
        self.assertIsNone(next(s for s in cue["spans"] if s["kind"] == "dialogue")["speaker"])
        with self.assertRaisesRegex(ValueError, "speaker review"):
            validate(cue, source, {"Narrator": {}, "Mara": {}})

    def test_author_override(self):
        source = 'Mara looked up. "Who is there?"'
        start = source.index('"')
        end = len(source)
        cue = compile_performance(source, ["Mara"], {f"{start}:{end}": "Mara"})
        validate(cue, source, {"Narrator": {}, "Mara": {}})

    def test_conflicting_attribution_requires_review(self):
        source = 'Mara said, "Hello," Ivo replied.'
        cue = compile_performance(source, ["Mara", "Ivo"])
        self.assertFalse(cue["render_ready"])


if __name__ == "__main__":
    unittest.main()
