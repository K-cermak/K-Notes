// Renders the README screenshots in Images from a fresh instance filled with sample notes.
// Run with `just screenshots`, which starts that instance; the base URL is the first argument.
import { mkdirSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { chromium, type Page } from '@playwright/test'

const base = process.argv[2] ?? 'http://127.0.0.1:18200'
const outDir = fileURLToPath(new URL('../../Images/', import.meta.url))
mkdirSync(outDir, { recursive: true })

const account = { display_name: 'Alex', email: 'alex@example.com', password: 'sample-password' }

// Created oldest first, as each new note goes to the top.
const notes = [
  {
    title: 'Wi-Fi at the cabin',
    text: 'Network: Birchwood\nPassword is on the fridge.',
    color: 'fog',
    labels: ['Travel'],
  },
  {
    title: 'Books to read',
    items: ['The Left Hand of Darkness', 'Piranesi', 'A Psalm for the Wild-Built'],
    labels: ['Reading'],
  },
  {
    title: 'Garden',
    text: 'Tomatoes need staking before the weekend.',
    color: 'mint',
    labels: ['Home'],
  },
  {
    title: 'Ideas for the blog',
    text: 'Offline-first apps\nWhy SQLite is enough\nNotes on note apps',
    color: 'dusk',
  },
  {
    title: 'Packing',
    items: ['Passport', 'Charger', 'Rain jacket', 'Walking shoes'],
    color: 'coral',
    labels: ['Travel'],
  },
  {
    title: 'Groceries',
    items: ['Coffee', 'Milk', 'Eggs', 'Rye bread', 'Apples'],
    color: 'sand',
    labels: ['Home'],
  },
  {
    title: 'Weekend in Prague',
    text: 'Train at 8:40 from platform 3. Lunch at the market, then the castle.',
    color: 'sage',
    pinned: true,
    labels: ['Travel'],
  },
]

function card(page: Page, title: string) {
  return page
    .getByTestId('note-card')
    .filter({ has: page.getByTestId('card-title').getByText(title, { exact: true }) })
}

/** A soft gradient PNG drawn in the page, so no image file has to live in the repository. */
async function sampleImage(page: Page): Promise<Buffer> {
  const dataUrl = await page.evaluate(() => {
    const canvas = document.createElement('canvas')
    canvas.width = 960
    canvas.height = 600
    const context = canvas.getContext('2d')!
    const sky = context.createLinearGradient(0, 0, 0, 600)
    sky.addColorStop(0, '#cfe3d4')
    sky.addColorStop(1, '#6f9a74')
    context.fillStyle = sky
    context.fillRect(0, 0, 960, 600)
    context.fillStyle = '#4e7a55'
    for (let x = 0; x < 960; x += 80) context.fillRect(x + 20, 360, 40, 240)
    return canvas.toDataURL('image/png')
  })
  return Buffer.from(dataUrl.split(',')[1], 'base64')
}

const browser = await chromium.launch()
const context = await browser.newContext({ baseURL: base, viewport: { width: 1280, height: 800 } })
const setup = await context.request.post('/api/v1/auth/setup', { data: account })
if (!setup.ok()) throw new Error(`Setup failed: ${setup.status()} ${await setup.text()}`)
for (const note of notes) {
  const created = await context.request.post('/api/v1/notes', { data: note })
  if (!created.ok()) throw new Error(`Creating ${note.title} failed: ${await created.text()}`)
}

const page = await context.newPage()
await page.goto('/')
await card(page, 'Weekend in Prague').waitFor()
await card(page, 'Groceries').getByRole('checkbox', { name: 'Coffee' }).click()
await card(page, 'Garden').hover()
const chooser = page.waitForEvent('filechooser')
await card(page, 'Garden').getByTestId('card-add-image').click()
await (
  await chooser
).setFiles({ name: 'garden.png', mimeType: 'image/png', buffer: await sampleImage(page) })
await card(page, 'Garden')
  .getByTestId('note-image')
  .and(page.locator('[data-loaded=true]'))
  .waitFor()
await page.getByTestId('sync-status').and(page.locator('[data-state=synced]')).waitFor()

async function shoot(file: string): Promise<void> {
  // Clicking the cards above scrolled them into view, and a pointer over the rail expands it.
  await page.evaluate(() => document.querySelectorAll('*').forEach((el) => el.scrollTo(0, 0)))
  await page.mouse.move(page.viewportSize()!.width / 2, 32)
  // A card shows its toolbar while it holds the focus, as the Add image button left it.
  if (!(await page.getByTestId('editor').count())) {
    await page.evaluate(() => (document.activeElement as HTMLElement | null)?.blur())
  }
  // Let fades and the masonry settle, so nothing is caught mid-way.
  await page.waitForTimeout(600)
  await page.screenshot({ path: `${outDir}github-${file}` })
  console.log(`Wrote Images/github-${file}`)
}

await shoot('notes-light.png')
await page.emulateMedia({ colorScheme: 'dark' })
await shoot('notes-dark.png')
await page.emulateMedia({ colorScheme: 'light' })
await card(page, 'Weekend in Prague').getByTestId('card-title').click()
await page.getByTestId('editor').waitFor()
await shoot('editor.png')
await page.keyboard.press('Escape')

await page.setViewportSize({ width: 390, height: 844 })
await page.goto('/')
await card(page, 'Groceries').waitFor()
await shoot('phone.png')

await browser.close()
