# Author-Controlled Pronunciation Dictionary

The question raised by the first RC1 audiobook was concrete: *buoys* came out like “boys,” when the author wanted the American “BOO-eez” pronunciation. An English respelling such as `boo-eez` is only a workaround. EmberWriter now has an **offline, real pronunciation dictionary plus a phoneme-specific override** for this case and for fictional names.

## Pronunciation sources

- **Carnegie Mellon Pronouncing Dictionary**, bundled at `backend/app/resources/cmudict.dict`. It provides American-English word-to-ARPAbet pronunciations. A local lookup converts dictionary phonemes to the IPA-like alphabet used by Kokoro. Original CMU dictionary entries: `buoy B UW1 IY0`, `buoys B UW1 IY0 Z`. Converted: `buoy → bˈuːi`, `buoys → bˈuːiz`. CMU's BSD license is preserved in `CMUDICT-LICENSE`; the original is https://github.com/cmusphinx/cmudict .
- **Cambridge English Pronouncing Dictionary** documents `buoy` as /bɔɪ/ in British usage and both /bɔɪ/ and /ˈbuː.i/ as American variants: https://dictionary.cambridge.org/pronunciation/english/buoy . This is an explanatory reference, **not bundled copyrighted data**.
- **eSpeak/phonemizer**, already used by Kokoro ONNX, handles ordinary unmodified prose, including punctuation. The author-selected IPA takes precedence only where a written word is explicitly selected in the project's glossary.

## How to use in EmberWriter

Open **Audiobook Workshop → Advanced: pronunciation and chapter narrator direction → Precise phoneme pronunciation**. Enter one word, choose **Look up in CMU pronunciation dictionary**, select a dictionary variant, and choose **Save IPA override**. For `buoy` and `buoys`, buttons prefill the desired American forms. If the word is an invented name or isn't in CMU, the author can enter IPA manually. The dictionary contains many pronunciations but cannot determine an invented character's intent or a contextual heteronym automatically.

The saved overrides live in the project's existing `.ember/audiobook-production.json` as `ipa_pronunciations`. They are applied at the **phoneme** stage during *local Kokoro* synthesis with `is_phonemes=True`. They do not rewrite the manuscript. Homophones such as `boys` are unaffected when only `buoys` is overridden. Legacy plain-text spoken substitutions continue to work; a saved IPA rule takes priority over a conflicting plain-text rule for the same word. Changing a pronunciation invalidates any old neural production batch and requires a fresh recording and full proof listen.

## Audio QA

BarnesPC test files are in:

`C:\Users\grump\Repo\EmberWriter-Release-Candidates\RC1-Final-Acceptance\Pronunciation-Comparison`

- `default.wav`: Kokoro's default G2P of the test sentence.
- `cmu-author.wav`: the **same narrator** with explicit CMU `buoy` and `buoys` phonemes.
- `phoneme-audit.json`: exact model inputs for both runs.

These are actual neural synthesizer outputs, not a pronunciation score or a substitute for listening. The complete three-chapter test has also been regenerated in a separate, unapproved **CMU IPA Pronunciation Edition**. No prior manuscript, ebook, or approved audio was overwritten.

## Remaining limitations

CMU is mainly **American English**, so a British performer may need a manually selected UK variant. Automatic dialect matching across every named voice is not promised. A dictionary's symbols can be correct while a voice still renders consonants, stress, or transitions poorly; audition and retake remain essential. Multi-word proper names currently use the existing spoken-spelling field, not the single-word IPA dictionary picker. A future pass can add multi-token phoneme glossaries, automatic unknown-name detection, and side-by-side author audition directly in the UI.
