import { expect, test } from '@playwright/test'
import { newUser, signedIn } from './helpers'

test('a note created in one browser appears in another without reloading', async ({ browser }) => {
  const user = await newUser(browser)
  const a = await signedIn(browser, user)
  const b = await signedIn(browser, user)

  await a.page.getByTestId('new-title').fill('From the laptop')
  await a.page.getByTestId('new-text').fill('Line one\nLine two')
  await a.page.getByTestId('add').click()

  const note = b.page.getByTestId('note')
  await expect(note.getByTestId('note-title')).toHaveValue('From the laptop')
  await expect(note.getByTestId('note-text')).toHaveValue('Line one\nLine two')

  await note.getByTestId('note-title').fill('Edited on the phone')
  await note.getByTestId('note-title').blur()
  await expect(a.page.getByTestId('note-title')).toHaveValue('Edited on the phone')

  await b.page.getByTestId('delete').click()
  await expect(a.page.getByTestId('note')).toHaveCount(0)
})

test('an offline edit syncs after reconnecting', async ({ browser }) => {
  const user = await newUser(browser)
  const a = await signedIn(browser, user)
  const b = await signedIn(browser, user)
  await a.page.getByTestId('new-title').fill('Shopping')
  await a.page.getByTestId('add').click()
  await expect(b.page.getByTestId('note-title')).toHaveValue('Shopping')

  await a.context.setOffline(true)
  await expect(a.page.getByTestId('sync-status')).toHaveAttribute('data-state', 'offline')
  await a.page.getByTestId('note-title').fill('Shopping, edited offline')
  await a.page.getByTestId('note-title').blur()
  await expect(a.page.getByTestId('unsent')).toHaveText('1 unsent change')
  await b.page.waitForTimeout(1500)
  await expect(b.page.getByTestId('note-title')).toHaveValue('Shopping')

  await a.context.setOffline(false)
  await expect(b.page.getByTestId('note-title')).toHaveValue('Shopping, edited offline')
  await expect(a.page.getByTestId('unsent')).toHaveCount(0)
  await expect(a.page.getByTestId('sync-status')).toHaveAttribute('data-state', 'synced')
})

test('concurrent offline edits of the same note leave a conflict copy', async ({ browser }) => {
  const user = await newUser(browser)
  const a = await signedIn(browser, user)
  const b = await signedIn(browser, user)
  await a.page.getByTestId('new-title').fill('Plan')
  await a.page.getByTestId('add').click()
  await expect(b.page.getByTestId('note-title')).toHaveValue('Plan')

  await a.context.setOffline(true)
  await b.context.setOffline(true)
  await a.page.getByTestId('note-title').fill('Plan from A')
  await a.page.getByTestId('note-title').blur()
  await expect(a.page.getByTestId('unsent')).toBeVisible()
  await b.page.getByTestId('note-title').fill('Plan from B')
  await b.page.getByTestId('note-title').blur()
  await expect(b.page.getByTestId('unsent')).toBeVisible()

  await a.context.setOffline(false)
  await expect(a.page.getByTestId('unsent')).toHaveCount(0)
  await b.context.setOffline(false)
  await expect(b.page.getByTestId('unsent')).toHaveCount(0)

  for (const page of [a.page, b.page]) {
    await expect(page.getByTestId('note')).toHaveCount(2)
    const titles = await page
      .getByTestId('note-title')
      .evaluateAll((inputs) => inputs.map((input) => (input as HTMLInputElement).value).sort())
    expect(titles).toEqual(['Plan from A', 'Plan from B'])
    // B edited last, so the original holds B's title and the copy keeps A's.
    const copy = page.getByTestId('note').filter({ has: page.getByTestId('conflict') })
    await expect(copy.getByTestId('note-title')).toHaveValue('Plan from A')
  }

  const copy = a.page.getByTestId('note').filter({ has: a.page.getByTestId('conflict') })
  await copy.getByRole('button', { name: 'Dismiss conflict marker' }).click()
  await expect(b.page.getByTestId('conflict')).toHaveCount(0)
})

test('signing out wipes the notes from this browser', async ({ browser }) => {
  const user = await newUser(browser)
  const a = await signedIn(browser, user)
  await a.page.getByTestId('new-title').fill('Private')
  await a.page.getByTestId('add').click()
  await expect(a.page.getByTestId('note')).toHaveCount(1)
  await expect(a.page.getByTestId('unsent')).toHaveCount(0)
  await a.page.getByRole('button', { name: 'Sign out' }).click()
  await expect(a.page).toHaveURL(/\/login/)
  const left = await a.page.evaluate(
    () =>
      new Promise<number>((resolve) => {
        const open = indexedDB.open('notes')
        open.onsuccess = () => {
          const tx = open.result.transaction('notes', 'readonly')
          const count = tx.objectStore('notes').count()
          count.onsuccess = () => resolve(count.result)
        }
      }),
  )
  expect(left).toBe(0)
})

test('signing out with unsent changes asks first', async ({ browser }) => {
  const user = await newUser(browser)
  const a = await signedIn(browser, user)
  await a.context.setOffline(true)
  await a.page.getByTestId('new-title').fill('Not sent yet')
  await a.page.getByTestId('add').click()
  await expect(a.page.getByTestId('unsent')).toHaveText('1 unsent change')
  // Sync stays blocked when the browser is back online, so the change remains unsent.
  await a.context.route('**/api/v1/sync/**', (route) => route.abort())
  await a.context.setOffline(false)

  await a.page.getByRole('button', { name: 'Sign out' }).click()
  const dialog = a.page.getByRole('alertdialog')
  await expect(dialog).toContainText('1 change that has not reached the server')
  await dialog.getByRole('button', { name: 'Cancel' }).click()
  await expect(a.page).toHaveURL(/\/$/)
  await expect(a.page.getByTestId('note-title')).toHaveValue('Not sent yet')

  await a.page.getByRole('button', { name: 'Sign out' }).click()
  await a.page
    .getByRole('alertdialog')
    .getByRole('button', { name: 'Discard and continue' })
    .click()
  await expect(a.page).toHaveURL(/\/login/)
})
