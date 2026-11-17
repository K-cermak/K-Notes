import { expect, test, type Locator, type Page } from '@playwright/test'
import { card, newUser, openNote, signedIn } from './helpers'

/** Writes a checklist through the composer's "New list" button, one Enter per item. */
async function addChecklist(page: Page, title: string, items: string[]): Promise<void> {
  await page.getByTestId('composer-list').click()
  const form = page.getByTestId('note-form')
  await expect(form.getByTestId('add-item')).toBeFocused()
  await page.keyboard.type(items.join('\n'))
  await form.getByTestId('editor-title').fill(title)
  await expect(form.getByTestId('item-text')).toHaveCount(items.length)
  await form.getByTestId('close-note').click()
  await expect(page.getByTestId('note-form')).toHaveCount(0)
  await expect(card(page, title).getByTestId('card-items')).toContainText(items.at(-1)!)
}

function itemTexts(scope: Locator) {
  return scope
    .getByTestId('item-text')
    .evaluateAll((fields) => fields.map((f) => (f as HTMLTextAreaElement).value))
}

function item(scope: Locator, text: string) {
  return scope
    .getByTestId('checklist-item')
    .filter({ has: scope.page().getByRole('checkbox', { name: text, exact: true }) })
}

test('a checklist is written, checked, edited and reordered', async ({ browser }) => {
  const user = await newUser(browser)
  const { page } = await signedIn(browser, user)
  await addChecklist(page, 'Groceries', ['Milk', 'Bread', 'Eggs'])

  await openNote(page, 'Groceries')
  const editor = page.getByTestId('editor')
  await item(editor, 'Bread').getByTestId('item-checkbox').click()
  await expect(editor.getByTestId('checked-toggle')).toHaveText('1 checked item')
  await expect.poll(() => itemTexts(editor)).toEqual(['Milk', 'Eggs', 'Bread'])

  // Enter in the middle splits an item; Backspace in an empty item removes it.
  await item(editor, 'Eggs').getByTestId('item-text').click()
  await page.keyboard.press('End')
  await page.keyboard.press('ArrowLeft')
  await page.keyboard.press('Enter')
  await expect.poll(() => itemTexts(editor)).toEqual(['Milk', 'Egg', 's', 'Bread'])
  await page.keyboard.press('Delete')
  await page.keyboard.press('Backspace')
  await expect.poll(() => itemTexts(editor)).toEqual(['Milk', 'Egg', 'Bread'])
  await expect(item(editor, 'Egg').getByTestId('item-text')).toBeFocused()

  // Several pasted lines become several items.
  await editor.getByTestId('add-item').evaluate((field) => {
    const data = new DataTransfer()
    data.setData('text/plain', 'Apples\n\nPears\r\nPlums')
    field.dispatchEvent(new ClipboardEvent('paste', { clipboardData: data, cancelable: true }))
  })
  await expect
    .poll(() => itemTexts(editor))
    .toEqual(['Milk', 'Egg', 'Apples', 'Pears', 'Plums', 'Bread'])

  // Dragging the handle of Plums to the top.
  const plums = item(editor, 'Plums')
  await plums.hover()
  const handle = (await plums.locator('.drag-handle').boundingBox())!
  const top = (await item(editor, 'Milk').boundingBox())!
  await page.mouse.move(handle.x + handle.width / 2, handle.y + handle.height / 2)
  await page.mouse.down()
  for (let step = 1; step <= 10; step++) {
    await page.mouse.move(
      handle.x + handle.width / 2,
      handle.y + handle.height / 2 + ((top.y + 4 - handle.y) * step) / 10,
    )
  }
  await page.mouse.up()
  await expect
    .poll(() => itemTexts(editor))
    .toEqual(['Plums', 'Milk', 'Egg', 'Apples', 'Pears', 'Bread'])

  await page.getByTestId('close-note').click()
  await expect(card(page, 'Groceries').getByTestId('card-checked')).toHaveText('+ 1 checked item')
  await expect(page.getByTestId('unsent')).toHaveCount(0)
  await page.reload()
  await openNote(page, 'Groceries')
  await expect
    .poll(() => itemTexts(page.getByTestId('editor')))
    .toEqual(['Plums', 'Milk', 'Egg', 'Apples', 'Pears', 'Bread'])
})

test('a text note converts to a checklist and back', async ({ browser }) => {
  const user = await newUser(browser)
  const { page } = await signedIn(browser, user)
  await page.getByTestId('composer').click()
  await page.getByTestId('editor-title').fill('Packing')
  await page.getByTestId('editor-body').click()
  await page.keyboard.type('Passport\n\nCharger')
  await page.getByTestId('close-note').click()
  await expect(card(page, 'Packing').getByTestId('card-body')).toContainText('Charger')

  await card(page, 'Packing').hover()
  await card(page, 'Packing').getByRole('button', { name: 'More' }).click()
  await page.getByRole('menuitem', { name: 'Show checkboxes' }).click()
  const items = card(page, 'Packing').getByTestId('card-items')
  await expect(items).toContainText('Passport')
  await card(page, 'Packing').getByRole('checkbox', { name: 'Charger' }).click()
  await expect(card(page, 'Packing').getByTestId('card-checked')).toHaveText('+ 1 checked item')

  await openNote(page, 'Packing')
  await page.getByTestId('editor').getByRole('button', { name: 'More' }).click()
  await page.getByRole('menuitem', { name: 'Hide checkboxes' }).click()
  await expect(page.getByTestId('editor-body')).toHaveText(/^Passport\s*Charger$/)
  await page.getByTestId('close-note').click()
  await expect(card(page, 'Packing').getByTestId('card-items')).toHaveCount(0)
})

test('the l key starts a checklist', async ({ browser }) => {
  const user = await newUser(browser)
  const { page } = await signedIn(browser, user)
  await page.keyboard.press('l')
  await expect(page.getByTestId('add-item')).toBeFocused()
  await page.keyboard.type('First')
  await page.keyboard.press('Escape')
  await expect(page.getByTestId('note-card').getByTestId('card-items')).toHaveText('First')
})

test('two offline clients checking different items both keep their changes', async ({
  browser,
}) => {
  const user = await newUser(browser)
  const a = await signedIn(browser, user)
  const b = await signedIn(browser, user)
  await addChecklist(a.page, 'Trip', ['Tickets', 'Tent', 'Torch'])
  await expect(card(b.page, 'Trip').getByTestId('card-items')).toContainText('Torch')

  await a.context.setOffline(true)
  await b.context.setOffline(true)
  await card(a.page, 'Trip').getByRole('checkbox', { name: 'Tickets' }).click()
  await card(b.page, 'Trip').getByRole('checkbox', { name: 'Torch' }).click()
  await expect(a.page.getByTestId('unsent')).toBeVisible()
  await expect(b.page.getByTestId('unsent')).toBeVisible()

  await a.context.setOffline(false)
  await expect(a.page.getByTestId('unsent')).toHaveCount(0)
  await b.context.setOffline(false)
  await expect(b.page.getByTestId('unsent')).toHaveCount(0)

  for (const page of [a.page, b.page]) {
    await expect(card(page, 'Trip').getByTestId('card-items')).toContainText('Tent')
    await expect(card(page, 'Trip').getByTestId('card-checked')).toHaveText('+ 2 checked items')
    await expect(card(page, 'Trip').getByTestId('card-items')).not.toContainText('Tickets')
  }
  await expect(a.page.getByTestId('note-card')).toHaveCount(1)
})
