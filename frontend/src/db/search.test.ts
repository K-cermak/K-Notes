import { describe, expect, it } from 'vitest'
import { applyChanges } from './apply'
import { createLabel, renameLabel, setNoteLabel } from './labels'
import { createNote, updateNote } from './notes'
import { fromPlainText } from './richtext'
import { fold, matches } from './search'
import { testDatabase } from './testing'

describe('search folding', () => {
  it('ignores case and diacritics', () => {
    expect(fold('Černý KŮŇ Žluťoučký')).toBe('cerny kun zlutoucky')
    expect(matches(fold('Pan Černý'), 'cerny')).toBe(true)
    expect(matches(fold('Pan Černý'), 'ČERNÝ pan')).toBe(true)
    expect(matches(fold('Pan Černý'), 'cerny bily')).toBe(false)
    expect(matches(fold('anything'), '   ')).toBe(false)
  })
})

describe('derived search text', () => {
  it('covers title, text and label names, and follows edits', async () => {
    const db = testDatabase()
    const id = await createNote({ title: 'Nákup', content: fromPlainText('mléko') }, db)
    const label = (await createLabel('Domácnost', db))!
    await setNoteLabel(id, label, true, db)
    let note = await db.notes.get(id)
    expect(matches(note!.searchText, 'nakup mleko domacnost')).toBe(true)

    await updateNote(id, { title: 'Seznam' }, db)
    await renameLabel(label, 'Rodina', db)
    note = await db.notes.get(id)
    expect(matches(note!.searchText, 'seznam rodina')).toBe(true)
    expect(matches(note!.searchText, 'domacnost')).toBe(false)
  })

  it('is refreshed when a label is renamed on another device', async () => {
    const db = testDatabase()
    const id = await createNote({ title: 'Plan' }, db)
    const label = (await createLabel('Work', db))!
    await setNoteLabel(id, label, true, db)
    // Everything has reached the server; a pending rename here would rightly win over the pulled name.
    await db.outbox.clear()
    await applyChanges(
      db,
      {
        notes: [],
        checklist_items: [],
        labels: [{ id: label, seq: 5, deleted: false, name: 'Práce' }],
        note_labels: [],
        attachments: [],
      },
      5,
    )
    expect(matches((await db.notes.get(id))!.searchText, 'prace')).toBe(true)
  })

  it('is never sent to the server', async () => {
    const db = testDatabase()
    await createNote({ title: 'Secret' }, db)
    const [entry] = await db.outbox.toArray()
    expect(entry!.fields).not.toHaveProperty('searchText')
  })
})
