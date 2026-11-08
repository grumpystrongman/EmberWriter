# EmberWriter Recovery Vault — Author Trust Contract

**Feature:** `feature/continuity-consequence-professional-ember` (stacked on draft Series Canon PR #125). This document records what the recovery system actually guarantees and what remains outside its protection.

## The promise

An author must not have to trust a single mutable book file, project folder, machine or opaque AI history. EmberWriter's recovery system protects the **entire local author-data library**, not merely the text currently visible in the editor. It keeps dated content-addressed versions, verifies backups, and restores a selected version into a **new and separate** directory. The author decides when to use the recovered material.

It is **not** a claim of zero data-loss risk, complete offsite resilience or built-in encrypted cloud backup. Those require additional storage, configuration and verified operational procedures.

## What's backed up

Every regular file under the configured `EMBER_DATA_DIR` / application data directory, including:

- Original manuscripts and drafts, story notes, characters, worldbuilding, timelines, planning material and editorial approval metadata
- Local SQLite project databases (snapshots, memory, provenance, run states)
- Series Vault SQLite data, imported source snapshots, citations, canon graph, author explanations and pending review notes
- User-supplied visual inspiration, media assets, generated audio, covers and supported output files stored within that data directory
- Relevant local configuration stored alongside these files

Files **outside the application data directory**—external Scrivener/Word manuscripts not imported or linked into EmberWriter, author data on other drives, external Ollama models or a separate media directory—are not automatically included. Filesystem links/junctions that escape the data root are refused rather than silently followed.

## How generations work

- On app startup, a nonblocking recovery loop begins; a first snapshot is scheduled shortly after startup and then approximately every **15 minutes while EmberWriter is running**. The app must remain running, the machine must be awake, and destination media must be accessible.
- A manual **Create verified backup now** action is available from **Protect work / Recovery Center** on every workspace.
- New contents are stored by **SHA-256 content identifier**, and unchanged files are reused on later generations. Original content objects are not overwritten. Snapshot manifests are published **only after** all referenced objects are stored; interrupted backups do not appear as completed generations.
- Existing SQLite files are backed up with the SQLite transactional backup API and checked with `PRAGMA integrity_check`; their live `-wal` and `-shm` runtime sidecars are omitted.
- Manuscript writes and project metadata replacement use same-directory, uniquely named temporary files, `fsync`, and atomic `os.replace`. Previous manuscript edits are separately protected by the app's project version snapshots.
- Whole-library backups are a **per-file consistency snapshot**, not a single atomic freeze of every non-database file across a running process. Files that change during their copy are detected and the generation is not published. SQLite files are transactionally consistent *individually*; there is no cross-database global transaction.
- If storage is low on free space, source/backup checks fail without deleting prior generations. Backup archives are not pruned automatically: this preserves older copies but requires storage capacity management. Version history and media copies can become large.

## Redundancy, encryption and disaster protection

By default, backup copies live in a **different folder** alongside the application data directory. That is useful for accidental deletion, ransomware *not capable of modifying the backup store*, or a corrupted single file. **It does not protect against failure, fire, theft, encryption or loss of the entire physical disk.**

Recovery Center lets authors choose:
1. A dedicated primary recovery folder outside the data directory.
2. An optional **second independent mirror folder**, preferably on a separate encrypted external drive or independently replicated storage. All content objects are copied and checked before a mirrored manifest is published; failed mirroring is shown in the UI, and synchronization can be retried.
3. Automatic backup on/off.

**Important: EmberWriter does not encrypt recovery objects itself.** Backup stores contain confidential manuscript text, and whoever can access the storage can read them. Use BitLocker, FileVault, LUKS or another appropriately managed encrypted storage system; do not place plaintext backups in an untrusted cloud-synced folder. The application does not upload to a cloud service or train a model on backup contents.

For serious commercial authors, implement a **3-2-1 storage policy** with at least one independently recoverable, access-restricted location. Verify mirror health and maintain a separate recovery-key/drive-unlock plan.

## Fail-closed destructive operations

Deleting an EmberWriter manuscript file, project, or Series Vault requires a **fresh, complete, successfully published generation** and checksum verification of the particular author material about to be deleted. If backup creation fails or a configured mirror cannot be validated, the delete operation fails and the original work stays in place.

The backup system does not currently intercept every destructive operation in external tools, manual filesystem operations, or the operating system. The Recovery Vault should therefore supplement—not replace—normal version history and off-device backups.

## Verification and recovery

- **Verify** reads every object referenced by a chosen generation and compares its SHA-256 hash and size with the manifest.
- **Restore** verifies the generation before copying, rechecks every copied file, and publishes the restored folder only after all files succeed. Invalid source hashes, missing objects, path traversal, duplicate manifest entries and an existing restore destination all block restoration.
- The restore always creates a **new** library. It never overwrites the running library, silently changes the active data directory or deletes the existing books.
- A user may inspect the recovered folder, then launch EmberWriter with the `-DataDir` option pointing at that recovered directory. Changing the active library should be an explicit action, preferably after closing the running editor, with a separate backup of both copies.
- If the primary backup store is unavailable but a verified independent mirrored store survives, an author can select that mirrored store as the Recovery Center's primary directory to inspect and restore generations.

## Verified scenarios and outstanding gates

Tests use synthetic authors/projects only:
- Live manuscript and audio/reference assets survive a complete backup/restore roundtrip.
- SQLite data is usable in restored copies.
- A corrupt object fails verification and restore without damaging the current manuscript.
- Interrupted backup creation leaves no published generation.
- Symlink/path-traversal attempts and restore-to-existing-folder requests are blocked.
- Deletion fails if the recovery destination is unavailable.
- Separate mirror can recover a library without consulting the original primary.
- A failed mirror blocks protected deletion but does not silently replace the existing backup.
- Explicit recovery HTTP API flow creates, previews, verifies and restores.

**Release work that remains:** performance tests on 50–500GB author libraries and long audio files; independent drive unplug/replug and power-loss exercises; Windows-specific directory junction/reparse-point adversarial testing; accessibility and professional author usability; periodic real restore drills; review of encryption-at-rest and dedicated recovery-key management; network-drive failure handling; full-metadata and asset reconciliation; and a clean-device disaster recovery rehearsal.

This is a stronger backup foundation, not an infallibility claim. Show authors the actual last snapshot date, mirror status and health warnings rather than an unsupported green “your data is safe” label.
