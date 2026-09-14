import { mkdir } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'
import { chromium } from 'playwright'

const baseUrl = process.env.EMBER_DEMO_UI || 'http://127.0.0.1:5173'
const outputDir = new URL('../../docs/screenshots/', import.meta.url)
await mkdir(outputDir, { recursive: true })

const browser = await chromium.launch({ headless: true })
const page = await browser.newPage({ viewport: { width: 1600, height: 1000 }, deviceScaleFactor: 1 })

async function shot(name) {
  await page.waitForTimeout(500)
  await page.screenshot({ path: fileURLToPath(new URL(name, outputDir)), fullPage: false })
}

try {
  await page.goto(baseUrl, { waitUntil: 'networkidle' })
  await page.getByRole('button', { name: /The Ashfall Crown/ }).click()
  await page.locator('.prose-editor').waitFor({ state: 'visible' })
  await shot('01-write-workspace.png')

  const nav = page.locator('.workspace-nav')

  await nav.getByRole('button', { name: /World/ }).click()
  await page.getByRole('heading', { name: 'World Studio' }).waitFor({ state: 'visible' })
  await page.locator('.atlas-workspace').waitFor({ state: 'visible' })
  await shot('02-story-atlas.png')

  await page.getByRole('button', { name: /Visual Canon/ }).click()
  await page.locator('.visual-studio').waitFor({ state: 'visible' })
  await shot('03-visual-canon.png')

  await nav.getByRole('button', { name: /Characters/ }).click()
  await page.getByRole('heading', { name: 'Character Studio' }).waitFor({ state: 'visible' })
  await shot('04-character-studio.png')

  await nav.getByRole('button', { name: /Publish/ }).click()
  await page.getByRole('heading', { name: 'Publishing Studio' }).waitFor({ state: 'visible' })
  await shot('05-publishing-studio.png')
} finally {
  await browser.close()
}
