import { execFileSync } from 'node:child_process'
import { expect, test, type Page } from '@playwright/test'
import { addNote, card, newUser, signedIn } from './helpers'

const PNG = Buffer.from(
  'iVBORw0KGgoAAAANSUhEUgAAAAgAAAAGCAIAAABxZ0isAAAAFElEQVR4nGM8YaPBgA0wYRWlkwQAsioBOPy3KEAAAAAASUVORK5CYII=',
  'base64',
)

/** Waits until the service worker has installed and controls the page. */
async function controlled(page: Page): Promise<void> {
  await page.evaluate(() => navigator.serviceWorker.ready)
  // The first visit is not controlled until the worker claims it or the page reloads.
  if (!(await page.evaluate(() => !!navigator.serviceWorker.controller))) await page.reload()
  await expect.poll(() => page.evaluate(() => !!navigator.serviceWorker.controller)).toBe(true)
}

test('after one online visit the app starts offline with its notes and images', async ({
  browser,
}) => {
  const { page, context } = await signedIn(browser, await newUser(browser))
  await addNote(page, 'Offline trip', 'Tickets in the drawer')
  await card(page, 'Offline trip').hover()
  const chooser = page.waitForEvent('filechooser')
  await card(page, 'Offline trip').getByTestId('card-add-image').click()
  await (await chooser).setFiles({ name: 'map.png', mimeType: 'image/png', buffer: PNG })
  await expect(page.getByTestId('unsent')).toHaveCount(0)
  await controlled(page)

  await context.setOffline(true)
  await page.reload()
  await expect(card(page, 'Offline trip').getByTestId('card-body')).toHaveText(
    'Tickets in the drawer',
  )
  await expect(card(page, 'Offline trip').getByTestId('note-image')).toHaveAttribute(
    'data-loaded',
    'true',
  )
  await expect(page.getByTestId('sync-status')).toHaveAttribute('data-state', 'offline')

  // A route opened for the first time offline also comes from the cache.
  await page.goto('/archive')
  await expect(page.getByTestId('empty-state')).toBeVisible()
})

test('the browser considers the app installable', async ({ browser }) => {
  const { page, context } = await signedIn(browser, await newUser(browser))
  await controlled(page)
  const cdp = await context.newCDPSession(page)
  const { installabilityErrors } = await cdp.send('Page.getInstallabilityErrors')
  expect(installabilityErrors).toEqual([])
  const manifest = await cdp.send('Page.getAppManifest')
  expect(manifest.errors).toEqual([])
})

test('a new version shows "Update available" and reloads only when asked', async ({ browser }) => {
  // The browser fetches sw.js on its own, out of reach of request routing, so the test changes
  // the file in the running container instead. Needs the container `just e2e` starts.
  const container = process.env.E2E_CONTAINER
  test.skip(!container, 'needs E2E_CONTAINER')
  const swPath = '/app/frontend/dist/sw.js'
  const shell = (script: string) =>
    execFileSync('docker', ['exec', '-u', '0', container!, 'sh', '-c', script])

  const { page } = await signedIn(browser, await newUser(browser))
  await controlled(page)
  await page.evaluate(() => {
    ;(window as unknown as { untouched: boolean }).untouched = true
  })

  shell(`cp ${swPath} /tmp/sw.js.orig && echo '// next build' >> ${swPath}`)
  try {
    await page.evaluate(async () => {
      const registration = await navigator.serviceWorker.getRegistration()
      await registration?.update()
    })
    const snackbar = page.getByTestId('snackbar')
    await expect(snackbar).toContainText('Update available')
    await page.waitForTimeout(1000)
    expect(
      await page.evaluate(() => (window as unknown as { untouched?: boolean }).untouched),
    ).toBe(true)

    const reloaded = page.waitForEvent('load')
    await snackbar.getByRole('button', { name: 'Reload' }).click()
    await reloaded
    expect(
      await page.evaluate(() => (window as unknown as { untouched?: boolean }).untouched),
    ).toBeUndefined()
    await expect(page.getByTestId('snackbar')).toHaveCount(0)
  } finally {
    shell(`cp /tmp/sw.js.orig ${swPath}`)
  }
})

test.describe('in Safari on an iPhone', () => {
  test.use({
    userAgent:
      'Mozilla/5.0 (iPhone; CPU iPhone OS 26_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/26.0 Mobile/15E148 Safari/604.1',
    viewport: { width: 390, height: 760 },
  })

  test('a hint explains how to add the app to the home screen', async ({ browser }) => {
    const { page } = await signedIn(browser, await newUser(browser))
    const hint = page.getByTestId('install-hint')
    await expect(hint).toContainText('Add to Home Screen')
    await hint.getByRole('button', { name: 'Got it' }).click()
    await expect(hint).toHaveCount(0)
    await page.reload()
    await expect(page.getByTestId('sync-status')).toBeVisible()
    await expect(hint).toHaveCount(0)
  })
})
