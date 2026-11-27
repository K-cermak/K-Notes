import { expect, test } from '@playwright/test'
import { accountMenu, addNote, card, newUser, openNote, retitle, signedIn } from './helpers'

test('a note created in one browser appears in another without reloading', async ({ browser }) => {
  const user = await newUser(browser)
  const a = await signedIn(browser, user)
  const b = await signedIn(browser, user)

  await addNote(a.page, 'From the laptop', 'Line one')
  await expect(card(b.page, 'From the laptop')).toContainText('Line one')

  await retitle(b.page, 'From the laptop', 'Edited on the phone')
  await expect(card(a.page, 'Edited on the phone')).toBeVisible()

  await card(b.page, 'Edited on the phone').hover()
  await card(b.page, 'Edited on the phone').getByRole('button', { name: 'More' }).click()
  await b.page.getByRole('menuitem', { name: 'Delete note' }).click()
  await expect(a.page.getByTestId('note-card')).toHaveCount(0)
})

test('an offline edit syncs after reconnecting', async ({ browser }) => {
  const user = await newUser(browser)
  const a = await signedIn(browser, user)
  const b = await signedIn(browser, user)
  await addNote(a.page, 'Shopping')
  await expect(card(b.page, 'Shopping')).toBeVisible()

  await a.context.setOffline(true)
  await expect(a.page.getByTestId('sync-status')).toHaveAttribute('data-state', 'offline')
  await retitle(a.page, 'Shopping', 'Shopping, edited offline')
  await expect(a.page.getByTestId('unsent')).toHaveText('1')
  await b.page.waitForTimeout(1500)
  await expect(card(b.page, 'Shopping')).toBeVisible()

  await a.context.setOffline(false)
  await expect(card(b.page, 'Shopping, edited offline')).toBeVisible()
  await expect(a.page.getByTestId('unsent')).toHaveCount(0)
  await expect(a.page.getByTestId('sync-status')).toHaveAttribute('data-state', 'synced')
})

test('concurrent offline edits of the same note leave a conflict copy', async ({ browser }) => {
  const user = await newUser(browser)
  const a = await signedIn(browser, user)
  const b = await signedIn(browser, user)
  await addNote(a.page, 'Plan')
  await expect(card(b.page, 'Plan')).toBeVisible()

  await a.context.setOffline(true)
  await b.context.setOffline(true)
  await retitle(a.page, 'Plan', 'Plan from A')
  await expect(a.page.getByTestId('unsent')).toBeVisible()
  await retitle(b.page, 'Plan', 'Plan from B')
  await expect(b.page.getByTestId('unsent')).toBeVisible()

  await a.context.setOffline(false)
  await expect(a.page.getByTestId('unsent')).toHaveCount(0)
  await b.context.setOffline(false)
  await expect(b.page.getByTestId('unsent')).toHaveCount(0)

  for (const page of [a.page, b.page]) {
    await expect(page.getByTestId('note-card')).toHaveCount(2)
    // B edited last, so the original holds B's title and the copy keeps A's.
    await expect(card(page, 'Plan from B').getByTestId('card-conflict')).toHaveCount(0)
    await expect(card(page, 'Plan from A').getByTestId('card-conflict')).toBeVisible()
  }

  await openNote(a.page, 'Plan from A')
  await a.page.getByTestId('conflict').getByRole('button', { name: 'Dismiss' }).click()
  await a.page.getByTestId('close-note').click()
  await expect(b.page.getByTestId('card-conflict')).toHaveCount(0)
})

test('signing out wipes the notes from this browser', async ({ browser }) => {
  const user = await newUser(browser)
  const a = await signedIn(browser, user)
  await addNote(a.page, 'Private')
  await expect(a.page.getByTestId('unsent')).toHaveCount(0)
  await accountMenu(a.page, 'Sign out')
  await expect(a.page).toHaveURL(/\/login/)
  const left = await a.page.evaluate(
    () =>
      new Promise<number>((resolve) => {
        const open = indexedDB.open('notes')
        open.onsuccess = () => {
          const count = open.result.transaction('notes', 'readonly').objectStore('notes').count()
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
  await addNote(a.page, 'Not sent yet')
  await expect(a.page.getByTestId('unsent')).toHaveText('1')
  // Sync stays blocked when the browser is back online, so the change remains unsent.
  await a.context.route('**/api/v1/sync/**', (route) => route.abort())
  await a.context.setOffline(false)

  await accountMenu(a.page, 'Sign out')
  const dialog = a.page.getByRole('alertdialog')
  await expect(dialog).toContainText('1 change that has not reached the server')
  await dialog.getByRole('button', { name: 'Cancel' }).click()
  await expect(a.page).toHaveURL(/\/$/)
  await expect(card(a.page, 'Not sent yet')).toBeVisible()

  await accountMenu(a.page, 'Sign out')
  await a.page
    .getByRole('alertdialog')
    .getByRole('button', { name: 'Discard and continue' })
    .click()
  await expect(a.page).toHaveURL(/\/login/)
})

test('the sync status opens details with the unsent changes and a sync button', async ({
  browser,
}) => {
  const user = await newUser(browser)
  const a = await signedIn(browser, user)
  await addNote(a.page, 'Errands')

  const details = a.page.getByTestId('sync-details')
  await a.page.getByTestId('sync-status').getByRole('button').click()
  await expect(details).toContainText('Synced')
  await expect(details.getByTestId('sync-details-last')).not.toHaveText('Never')
  await a.page.keyboard.press('Escape')

  await a.context.setOffline(true)
  await expect(a.page.getByTestId('sync-status')).toHaveAttribute('data-state', 'offline')
  await retitle(a.page, 'Errands', 'Errands, offline')
  await a.page.getByTestId('sync-status').getByRole('button').click()
  await expect(details).toContainText('Offline')
  await expect(details.getByTestId('sync-details-unsent')).toHaveText('1')

  await a.context.setOffline(false)
  await details.getByTestId('sync-now').click()
  await expect(details.getByTestId('sync-details-unsent')).toHaveText('0')
  await expect(details).toContainText('Synced')
})
