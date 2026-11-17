import { createHash } from 'node:crypto'
import { expect, test, type Page } from '@playwright/test'
import { addNote, card, newUser, openNote, signedIn } from './helpers'

// 8 × 6 px PNGs in two colours, so tests can tell images apart by their hash.
const RED = Buffer.from(
  'iVBORw0KGgoAAAANSUhEUgAAAAgAAAAGCAIAAABxZ0isAAAAFElEQVR4nGM8YaPBgA0wYRWlkwQAsioBOPy3KEAAAAAASUVORK5CYII=',
  'base64',
)
const BLUE = Buffer.from(
  'iVBORw0KGgoAAAANSUhEUgAAAAgAAAAGCAIAAABxZ0isAAAAFElEQVR4nGPUiFrAgA0wYRWlkwQAq0oBLlm9L/8AAAAASUVORK5CYII=',
  'base64',
)

function file(buffer: Buffer, name = 'photo.png') {
  return { name, mimeType: 'image/png', buffer }
}

function sha(buffer: Buffer): string {
  return createHash('sha256').update(buffer).digest('hex')
}

/** Adds images to a note through its card's "Add image" button. */
async function addImages(page: Page, title: string, ...buffers: Buffer[]): Promise<void> {
  await card(page, title).hover()
  const chooser = page.waitForEvent('filechooser')
  await card(page, title).getByTestId('card-add-image').click()
  await (await chooser).setFiles(buffers.map((buffer, n) => file(buffer, `photo-${n}.png`)))
  await expect(card(page, title).getByTestId('note-image')).toHaveCount(buffers.length)
}

test('an image attached offline reaches the other device after reconnecting', async ({
  browser,
}) => {
  const user = await newUser(browser)
  const a = await signedIn(browser, user)
  const b = await signedIn(browser, user)
  await addNote(a.page, 'Holiday')
  await expect(card(b.page, 'Holiday')).toBeVisible()

  await a.context.setOffline(true)
  await expect(a.page.getByTestId('sync-status')).toHaveAttribute('data-state', 'offline')
  await addImages(a.page, 'Holiday', RED)
  await expect(card(a.page, 'Holiday').getByTestId('note-image')).toHaveAttribute(
    'data-loaded',
    'true',
  )
  await expect(a.page.getByTestId('unsent')).toBeVisible()
  await b.page.waitForTimeout(1000)
  await expect(card(b.page, 'Holiday').getByTestId('note-image')).toHaveCount(0)

  await a.context.setOffline(false)
  await expect(card(b.page, 'Holiday').getByTestId('note-image')).toHaveAttribute(
    'data-loaded',
    'true',
  )
  await expect(a.page.getByTestId('unsent')).toHaveCount(0)
})

test('another user cannot fetch an image by its hash', async ({ browser }) => {
  const owner = await signedIn(browser, await newUser(browser))
  await addNote(owner.page, 'Private photo')
  await addImages(owner.page, 'Private photo', BLUE)
  await expect(owner.page.getByTestId('unsent')).toHaveCount(0)
  const own = await owner.context.request.get(`/api/v1/blobs/${sha(BLUE)}`)
  expect(own.status()).toBe(200)

  const intruder = await signedIn(browser, await newUser(browser))
  const response = await intruder.context.request.get(`/api/v1/blobs/${sha(BLUE)}`)
  expect(response.status()).toBe(404)
  expect(((await response.json()) as { code: string }).code).toBe('not_found')
})

test('the same image attached twice is uploaded and stored once', async ({ browser }) => {
  const { page } = await signedIn(browser, await newUser(browser))
  const uploads: string[] = []
  page.on('request', (request) => {
    if (request.method() === 'PUT' && request.url().includes('/api/v1/blobs/')) {
      uploads.push(request.url())
    }
  })
  await addNote(page, 'First')
  await addNote(page, 'Second')
  await addImages(page, 'First', RED)
  await addImages(page, 'Second', RED)
  await expect(page.getByTestId('unsent')).toHaveCount(0)
  await expect(card(page, 'Second').getByTestId('note-image')).toHaveAttribute(
    'data-loaded',
    'true',
  )
  expect(uploads).toEqual([expect.stringContaining(sha(RED))])
  const stored = await page.evaluate(
    () =>
      new Promise<number>((resolve) => {
        const open = indexedDB.open('notes')
        open.onsuccess = () => {
          const count = open.result.transaction('blobs').objectStore('blobs').count()
          count.onsuccess = () => resolve(count.result)
        }
      }),
  )
  expect(stored).toBe(1)
})

test('images open in a viewer and can be removed', async ({ browser }) => {
  const { page } = await signedIn(browser, await newUser(browser))
  await addNote(page, 'Album')
  await addImages(page, 'Album', RED, BLUE)
  await openNote(page, 'Album')
  const editor = page.getByTestId('editor')
  await editor.getByTestId('note-image').first().click()
  const viewer = page.getByTestId('image-viewer')
  await expect(viewer).toContainText('1 / 2')
  await page.keyboard.press('ArrowRight')
  await expect(viewer).toContainText('2 / 2')
  await page.keyboard.press('Escape')
  await expect(viewer).toHaveCount(0)
  await expect(editor).toBeVisible()

  await editor.getByTestId('note-image').first().hover()
  await editor.getByTestId('remove-image').first().click()
  await expect(editor.getByTestId('note-image')).toHaveCount(1)
  await page.getByTestId('close-note').click()
  await expect(card(page, 'Album').getByTestId('note-image')).toHaveCount(1)
})

test('with images on demand, an image downloads when tapped', async ({ browser }) => {
  const user = await newUser(browser)
  const a = await signedIn(browser, user)
  const b = await signedIn(browser, user)
  await b.page.getByRole('button', { name: 'Display options' }).click()
  await b.page.getByTestId('download-on-demand').click()
  await expect(b.page.getByTestId('download-on-demand')).toHaveAttribute('aria-checked', 'true')
  await b.page.keyboard.press('Escape')

  await addNote(a.page, 'Big photo')
  await addImages(a.page, 'Big photo', BLUE)
  const placeholder = card(b.page, 'Big photo').getByTestId('note-image')
  await expect(placeholder).toHaveAttribute('data-loaded', 'false')
  await b.page.waitForTimeout(1000)
  await expect(placeholder).toHaveAttribute('data-loaded', 'false')
  await placeholder.getByRole('button', { name: 'Download image' }).click()
  await expect(placeholder).toHaveAttribute('data-loaded', 'true')
  await expect(b.page).toHaveURL(/\/$/)
})
