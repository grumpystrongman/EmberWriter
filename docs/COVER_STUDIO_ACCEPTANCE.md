# EmberWriter Cover Studio Acceptance Gate

Cover Studio is not accepted merely because a PDF or JPEG exists. The final author-facing gate uses real high-resolution cover art, the final formatted interior page count, and the target distributor's own current preview/preflight tools.

## Evidence to record

For each test record the project, platform, trim/binding/paper choice, final page count, artwork pixel dimensions, expected result, generated artifact path, observed result, and PASS/FAIL. Preserve screenshots or distributor-preflight notes outside the repository when they contain unpublished artwork or account information.

## 1. Portable cover project

- Create and save a cover profile.
- Restart EmberWriter and confirm all cover metadata/layout settings return.
- Confirm `publishing/cover-profile.json` is readable without EmberWriter.
- Confirm original uploaded artwork remains an ordinary file under `assets/covers/`.
- Back up the project directory and confirm the cover profile plus assets can be restored from that filesystem copy.
- Do not assume the current text-only named checkpoint store duplicates binary artwork; verify ordinary project backup separately.

## 2. KDP paperback geometry

Using a real intended KDP paperback configuration:

- Enter the final formatted page count, not the manuscript word-processor page count.
- Select the actual KDP interior/paper type.
- Confirm trim size matches the intended KDP book.
- Compare Ember's calculated spine and full-wrap dimensions against the current official KDP cover calculator/template.
- Verify 0.125-inch outside bleed behavior.
- Verify front/back type-safe guide behavior.
- Verify spine text is blocked below Ember's conservative 80-page threshold.
- If spine text is used, compare its placement against the official template.

Any geometry mismatch against the current KDP template is a release blocker.

## 3. IngramSpark geometry

Using the exact intended IngramSpark print product:

- Generate the official IngramSpark cover template.
- Enter the template's exact spine width in EmberWriter.
- Confirm EmberWriter does not substitute a generic calculated spine.
- Compare full-wrap dimensions, bleed, and spine boundaries with the official template.
- Verify the type-safe guide uses Ember's conservative Ingram minimum.

Any mismatch against the product-specific Ingram template is a release blocker.

## 4. Artwork ingest and live preview

Use real cover artwork at final-production resolution:

- Upload PNG.
- Upload JPEG.
- Where relevant, exercise TIFF/WebP ingest.
- Confirm corrupt/non-image files are rejected.
- Confirm the live preview shows the actual project artwork rather than a placeholder.
- Exercise front-only artwork.
- Exercise full-wrap artwork.
- Change artwork opacity and confirm preview and exported artifact change consistently.
- Confirm full-wrap art remains visible across back, spine, and front and is not hidden by opaque panel fills.
- Confirm front-only art does not unintentionally replace the back/spine design.

## 5. Typography and metadata

Using a real title/subtitle/pen name/back blurb:

- Verify title wrapping on short and long titles.
- Verify subtitle placement.
- Verify author/pen-name placement.
- Verify back-blurb wrapping and identify any clipping/crowding.
- Verify imprint placement.
- Verify left/center/right title alignment.
- Exercise each currently supported font family.
- Exercise text and panel colors.
- Exercise spine text at both narrow and wide spine sizes.

The generated artifact must be reopened and visually inspected; browser preview alone is insufficient.

## 6. Barcode behavior

- Platform barcode mode leaves a visible reserved clearance area on the back cover.
- Custom barcode mode requires an image before export.
- Upload a real test barcode image and confirm it appears entirely inside the reserved box.
- No-barcode mode removes the reserved box.
- Confirm the final distributor preview does not place a platform barcode over critical text/art.

The reserved box is an Ember layout aid, not a claim that its default dimensions replace the distributor's current barcode rules.

## 7. Print PDF artifact inspection

For KDP, IngramSpark, and one custom print profile:

- Open the generated PDF in an independent PDF viewer.
- Confirm it contains exactly one full-wrap page.
- Confirm physical MediaBox dimensions match the expected full-wrap dimensions.
- Confirm back/spine/front order and orientation.
- Confirm title, author, blurb, and spine text are readable and not clipped.
- Confirm artwork reaches intended bleed edges.
- Confirm no unexpected panel fill covers full-wrap artwork.
- Confirm barcode clearance/custom barcode position.
- Inspect font embedding, transparency handling, and output color space with an appropriate preflight tool.

The current Ember geometry preflight does not replace professional PDF/prepress validation.

## 8. KDP eBook cover

- Test the default 1600 × 2560 pixel profile.
- Test the minimum 625 × 1000 pixel profile.
- Verify invalid dimensions are blocked where required and non-ideal dimensions produce guidance.
- Confirm generated JPEG opens independently and has the exact configured pixel dimensions.
- Confirm the PNG proof opens independently and matches layout/content.
- Confirm artwork crop and opacity behavior.
- Upload the JPEG in the current KDP cover workflow and inspect the KDP preview.

## 9. Distributor preflight

Before treating a real cover as publishable:

- KDP: upload/test with the current KDP Previewer/template workflow.
- IngramSpark: compare against the current generated template and run the account's file validation/proof workflow.
- Resolve platform-reported font, transparency, color, bleed, spine, barcode, or safe-zone errors before release/publishing.
- Re-check the linked official authority if Ember's stored guidance and distributor UI disagree; distributor current rules win.

## 10. Regression gate

Before merging a Cover Studio code release:

- all backend tests pass;
- Ruff passes;
- frontend TypeScript/Vite production build passes;
- KDP geometry regression tests pass;
- artwork layering/opacity regression tests pass;
- PDF MediaBox/output inspection tests pass;
- eBook raster-dimension tests pass;
- exact PR head SHA is the SHA that passed CI.

A later code change after the green run invalidates the merge signal until CI passes again on the new exact head.
