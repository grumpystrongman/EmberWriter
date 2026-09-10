# EmberWriter Release & Distribution Acceptance Gate

A release handoff is not accepted because EmberWriter created a ZIP. Publication metadata and distributor requirements are externally controlled and can change. This gate verifies the generated files, metadata consistency, identifier strategy, package integrity, and the target retailer's own current preview/preflight before a book is considered ready to publish.

Rules below were reviewed on **2026-09-10**. Recheck the linked authority before a real release.

## Authority set

### Amazon Kindle Direct Publishing

- Metadata guidelines: https://kdp.amazon.com/en_US/help/topic/G201097560
- Keywords: https://kdp.amazon.com/en_US/help/topic/G201743260
- ISBN and imprint: https://kdp.amazon.com/en_US/help/topic/G201834170
- Distribution rights: https://kdp.amazon.com/en_US/help/topic/G201834280

Current release checks encoded in EmberWriter include:

- up to seven keyword phrases;
- up to three KDP categories;
- title/subtitle/author metadata must agree with the saved cover project when cover text exists;
- print editions need an ISBN strategy unless a specific KDP exception applies;
- a KDP-assigned ISBN is retailer-specific and must not be treated as a portable identifier for another distributor;
- title/subtitle/author/keyword fields are checked for stray HTML tags.

### IngramSpark

- ISBN overview: https://www.ingramspark.com/free-isbns
- Print file requirements: https://www.ingramspark.com/blog/file-requirements-for-print-books
- Cover template generator: https://myaccount.ingramspark.com/Portal/Tools/CoverTemplateGenerator

Current release checks encoded in EmberWriter include:

- every distributed format needs an ISBN strategy;
- owned ISBNs must be valid ISBN-13 values and cannot be reused across enabled editions;
- retailer-assigned ISBNs are not considered portable across distributors;
- print page count must be even;
- BISAC and/or Thema subject metadata is surfaced as a readiness warning when missing;
- the exact Ingram product template remains authoritative for physical cover geometry.

### Apple Books

- Publish from the web: https://authors.apple.com/support/4574-publish-book-from-web
- Product page / metadata guidance: https://authors.apple.com/support/3969-craft-great-product-page-apple-books
- Asset guide: https://help.apple.com/itc/booksassetguide/en.lproj/static.html

Current release checks encoded in EmberWriter include:

- direct Apple handoff is currently limited to the eBook edition;
- Publisher Description is required;
- at least one category is required;
- publisher/self-publisher identity is retained;
- explicit-content disclosure is carried in the master metadata;
- the selected EPUB must still pass the latest Apple-required EPUBCheck outside EmberWriter before publication.

### Kobo Writing Life

- Metadata guidelines: https://kobowritinglife.zendesk.com/hc/en-us/articles/360058975792-Metadata-Guidelines
- New eBook setup: https://kobowritinglife.zendesk.com/hc/en-us/articles/360058975732-Setting-up-a-New-eBook
- ISBN guidance: https://kobowritinglife.zendesk.com/hc/en-us/articles/360059386031-ISBNs-and-Kobo-Writing-Life

Current release checks encoded in EmberWriter include:

- direct Kobo handoff is currently limited to the eBook edition;
- store metadata should match the actual book/cover rather than contain keyword stuffing or extraneous tagging;
- website/contact redirects in store metadata are blocked by preflight;
- Kobo can issue its own identifier, but partner distribution may still require a valid ISBN, so no-ISBN eBooks receive an informational warning.

## 1. Master metadata

Use a real book and complete:

- exact title;
- subtitle if applicable;
- primary author / pen name;
- publisher and imprint;
- series name and series number in separate fields;
- long store description;
- short description where useful;
- author biography;
- language;
- publication, original-publication, and release dates where applicable;
- public-domain state;
- explicit-content state;
- reading age where applicable;
- rights scope and territory list when rights are not worldwide;
- keywords;
- KDP categories;
- Apple Books categories;
- Kobo categories;
- BISAC and Thema subject codes.

Save the project, restart EmberWriter, and verify `publishing/release-profile.json` remains readable and reloads identically.

## 2. Edition identity

For every enabled format:

- verify the edition ID is unique;
- verify ebook, paperback, and hardcover identifiers are not reused;
- validate owned ISBN-13 check digits;
- verify any retailer-assigned identifier is restricted to that retailer's handoff;
- confirm list price and three-letter currency code;
- confirm final page count and trim size for print;
- confirm the chosen retailer targets are intentional.

Test at least one negative case where the same retailer-assigned print identifier strategy is selected for KDP and IngramSpark. Ember must block the package rather than imply portability.

## 3. Artifact binding

Build fresh publishing outputs before the final release package.

For each enabled edition:

- select the exact generated interior file;
- select the exact generated cover file;
- confirm ebook interior is EPUB;
- confirm print interior is PDF;
- confirm print cover is the correct full-wrap PDF;
- confirm KDP ebook cover is JPEG or TIFF;
- reopen every selected artifact independently before packaging;
- confirm old/stale exports are not accidentally selected merely because they exist.

Release paths must be confined beneath the project's `exports/` directory. Attempted path traversal or use of manuscript/source files as release artifacts must fail preflight.

## 4. Metadata-to-cover consistency

When a saved Cover Studio project exists:

- compare title exactly;
- compare subtitle exactly;
- compare primary author/pen name exactly;
- verify the edition ISBN/barcode treatment matches the intended distributor workflow;
- verify series text is placed only where the target retailer permits it.

A title/subtitle/author mismatch between the release metadata and saved cover project must block the handoff package.

## 5. Retailer-specific checks

### KDP

- seven or fewer keyword phrases;
- three or fewer selected categories;
- current rights selection reviewed in KDP;
- print identifier mode reviewed;
- final interior and cover loaded into KDP Previewer;
- cover/interior metadata match the title setup;
- proof copy ordered for a commercial print release where appropriate.

### IngramSpark

- ISBN strategy confirmed for every distributed format;
- print page count even;
- exact product-specific cover template used;
- BISAC/Thema metadata reviewed;
- final interior and cover pass Ingram's current ingestion/preflight;
- publisher/imprint shown by the ISBN strategy is acceptable.

### Apple Books

- EPUB passes the latest EPUBCheck;
- Publisher Description reviewed;
- at least one accurate category chosen;
- explicit-content flag reviewed;
- cover, title, subtitle, and author metadata agree;
- rights and pricing are completed in Apple's current portal.

### Kobo

- title, subtitle, series, author, and synopsis are in their correct fields;
- metadata contains no website/contact redirect material;
- category selection is valid in Kobo's current dropdowns;
- ISBN/identifier choice is appropriate for any desired Kobo partner distribution;
- preview the live product metadata before publication.

## 6. Handoff package integrity

Build the EmberWriter release handoff package and inspect the generated ZIP.

It must contain:

- `metadata/release-profile.json`;
- `metadata/release-manifest.json`;
- `metadata/retailer-metadata.csv`;
- one `retailers/<retailer>.json` for each selected retailer;
- selected interior/cover files grouped by edition;
- `README.txt` stating that the package is a handoff, not proof of distributor approval.

For every packaged file:

- compare its SHA-256 against `release-manifest.json`;
- compare byte size against the manifest;
- reopen the packaged copy, not only the source export;
- confirm the intended edition/file role.

## 7. Final publication gate

Do not call a real book "ready to publish" until:

1. Ember release preflight has no blocking errors.
2. All warnings have been consciously accepted or fixed.
3. The handoff ZIP and manifest have been archived with the release.
4. The exact packaged EPUB/PDF/cover files have been reopened successfully.
5. The target retailer's own current validation/preview accepts the files.
6. Store metadata has been visually reviewed in the retailer portal.
7. Rights, pricing, identifiers, publication date, and territories have been rechecked immediately before submission.

EmberWriter should make the final handoff repeatable and auditable. It should not pretend that retailer-controlled publication rules are static or that a locally generated package bypasses the distributor's own acceptance process.
