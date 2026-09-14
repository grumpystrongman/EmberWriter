# Historical EmberWriter data recovery

This document records the storage history relevant to recovering projects created by early Windows builds.

## What changed over time

EmberWriter's first local project storage used a relative default data path:

```python
DATA_ROOT = Path(os.getenv("EMBER_DATA_DIR", "data")).expanduser().resolve()
```

The original Windows `start.ps1` launched the backend with `Start-Process` but did not set `-WorkingDirectory`. As a result, when `EMBER_DATA_DIR` was not set, the backend inherited the PowerShell launcher's current working directory and created projects beneath:

```text
<launch working directory>\data\projects\...
```

This was corrected on 2026-09-14 by commit `20b961d981d84afcf50711b420590dce031ed491`, which stabilized the data root and set the backend/frontend working directory explicitly.

Because the earlier current working directory was not persisted, old data can legitimately exist outside the EmberWriter repository. Plausible roots include the user's home or development directories, drive roots, Windows/PowerShell launch directories, and directories visible in PowerShell location history.

## Recovery sources

The current recovery pass therefore uses multiple independent signals:

1. normal project folders containing `project.json` and manuscript/history;
2. pre-fix `<historical CWD>\data\projects` locations;
3. mounted-drive searches for EmberWriter project signatures;
4. explicitly probed Windows/PowerShell launch locations that generic scans normally prune;
5. available Recycle Bin trees on mounted drives;
6. `.ember/snapshots` copies made by the original save implementation;
7. `document_revisions` stored in `.ember/story.db`;
8. project checkpoint content stored in `.ember/story.db`.

Recovery copies the source to the active library and never edits the evidence source. If the manuscript file itself is missing but a revision/checkpoint/snapshot remains, the copy reconstructs only the missing manuscript file from the newest available historical content.

## Import compatibility

There are two historically separate import paths:

- manuscript ingest for DOCX/PDF/EPUB/RTF/Markdown/TXT/HTML;
- local project-folder import.

The older local project-folder importer deliberately skipped `.ember`, which made it inappropriate for disaster recovery because `.ember` contains revision/checkpoint/snapshot history. Recognizable EmberWriter project folders now use the preservation restore path instead.

The Recovery & Import panel also exposes a browser folder picker. It uploads relative paths (`File.webkitRelativePath`) so a project folder can be restored without typing a server-side filesystem path. Normal manuscript import is also available from that panel even when the library is empty.

## Non-destructive rule

Recovery must not overwrite or delete source evidence. Recovered projects receive a new local identity/slug when needed, and source project IDs are retained only as provenance metadata.