import { describe, expect, it } from 'vitest'
import { addItems, convertNote, MAX_ITEMS, noteItems, removeItem, updateItem } from './checklist'
import { createNote, isNoteEmpty } from './notes'
import { insertKeys } from './positions'
import { fromPlainText, plainText } from './richtext'
import { testDatabase } from './testing'

describe('positions', () => {
  it('inserts between neighbours, at either end and between equal keys', () => {
    const [middle] = insertKeys(['a0', 'a2'], 1)
    expect(middle! > 'a0' && middle! < 'a2').toBe(true)
    expect(insertKeys(['a0'], 0)[0]! < 'a0').toBe(true)
    expect(insertKeys(['a0'], 1)[0]! > 'a0').toBe(true)
    const [tied] = insertKeys(['a0', 'a1', 'a1', 'a3'], 2)
    expect(tied! > 'a1' && tied! < 'a3').toBe(true)
    const keys = insertKeys([], 0, 3)
    expect([...keys].sort()).toEqual(keys)
  })
})

describe('checklist repository', () => {
  it('adds items in order after a given item', async () => {
    const db = testDatabase()
    const id = await createNote({ type: 'checklist' }, db)
    const [milk] = await addItems(id, ['Milk'], null, db)
    await addItems(id, ['Bread'], milk!, db)
    await addItems(id, ['Eggs', 'Butter'], milk!, db)
    expect((await noteItems(id, db)).map((i) => i.text)).toEqual([
      'Milk',
      'Eggs',
      'Butter',
      'Bread',
    ])
    const note = await db.notes.get(id)
    expect(note!.searchText).toContain('butter')
  })

  it('records item ops and touches the note on edits, not on moves', async () => {
    const db = testDatabase()
    const id = await createNote({ type: 'checklist' }, db)
    const [item] = await addItems(id, ['Milk'], null, db)
    await db.notes.update(id, { updated_at: 1 })
    await db.outbox.clear()

    await updateItem(item!, { position: 'Zz' }, db)
    expect((await db.notes.get(id))!.updated_at).toBe(1)
    await updateItem(item!, { checked: true, text: 'Oat milk' }, db)
    expect((await db.notes.get(id))!.updated_at).toBeGreaterThan(1)
    const ops = await db.outbox.toArray()
    expect(ops).toHaveLength(1)
    expect(ops[0]!.fields).toEqual({ position: 'Zz', checked: true, text: 'Oat milk' })
  })

  it('forgets a removed item the server never saw', async () => {
    const db = testDatabase()
    const id = await createNote({ type: 'checklist' }, db)
    const [item] = await addItems(id, ['Milk'], null, db)
    await removeItem(item!, db)
    expect(await noteItems(id, db)).toEqual([])
    expect((await db.outbox.toArray()).map((e) => e.entity)).toEqual(['note'])
  })

  it('stops at the item limit', async () => {
    const db = testDatabase()
    const id = await createNote({ type: 'checklist' }, db)
    await addItems(
      id,
      Array.from({ length: MAX_ITEMS - 1 }, (_, n) => `#${n}`),
      null,
      db,
    )
    expect(await addItems(id, ['last', 'too many'], null, db)).toHaveLength(1)
    expect(await addItems(id, ['more'], null, db)).toEqual([])
  })

  it('converts text to a checklist and back', async () => {
    const db = testDatabase()
    const id = await createNote({ content: fromPlainText('Milk\n\n  \nBread\nEggs') }, db)
    await convertNote(id, 'checklist', db)
    const note = await db.notes.get(id)
    expect(note).toMatchObject({ type: 'checklist', content: { type: 'doc', content: [] } })
    const items = await noteItems(id, db)
    expect(items.map((i) => i.text)).toEqual(['Milk', 'Bread', 'Eggs'])

    await updateItem(items[0]!.id, { checked: true }, db)
    await convertNote(id, 'text', db)
    const text = await db.notes.get(id)
    expect(text!.type).toBe('text')
    // Checked items come last, as they were shown.
    expect(plainText(text!.content)).toBe('Bread\nEggs\nMilk')
    expect(await noteItems(id, db)).toEqual([])
  })

  it('treats a checklist with only blank items as empty', async () => {
    const db = testDatabase()
    const id = await createNote({ type: 'checklist' }, db)
    const [item] = await addItems(id, [''], null, db)
    expect(await isNoteEmpty(id, db)).toBe(true)
    await updateItem(item!, { text: 'Milk' }, db)
    expect(await isNoteEmpty(id, db)).toBe(false)
  })
})
