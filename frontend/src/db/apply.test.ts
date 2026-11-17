import { describe, expect, it } from 'vitest'
import type { components } from '@/api/schema'
import { applyChanges } from './apply'
import { addItems } from './checklist'
import { createLabel, setNoteLabel } from './labels'
import { getMeta } from './meta'
import { createNote, updateNote } from './notes'
import { fromPlainText } from './richtext'
import { testDatabase } from './testing'

type Changes = components['schemas']['Changes']
type NoteRow = components['schemas']['NoteRow']

function noteRow(overrides: Partial<NoteRow> & { id: string }): NoteRow {
  return {
    seq: 1,
    deleted: false,
    type: 'text',
    title: '',
    content: { type: 'doc', content: [] },
    color: 'default',
    pinned: false,
    archived: false,
    trashed_at: null,
    position: 'a0',
    conflict_of: null,
    created_at: 1,
    updated_at: 1,
    ...overrides,
  }
}

function changes(partial: Partial<Changes>): Changes {
  return {
    notes: [],
    checklist_items: [],
    labels: [],
    note_labels: [],
    attachments: [],
    ...partial,
  }
}

describe('applying pulled rows', () => {
  it('stores rows with their server version and moves the cursor', async () => {
    const db = testDatabase()
    await applyChanges(db, changes({ notes: [noteRow({ id: 'n1', seq: 5, title: 'Pulled' })] }), 5)
    expect(await db.notes.get('n1')).toMatchObject({ title: 'Pulled', serverSeq: 5 })
    expect(await getMeta(db, 'cursor')).toBe(5)
  })

  it('keeps local values of fields with pending ops', async () => {
    const db = testDatabase()
    const id = await createNote({ title: 'Mine' }, db)
    await db.outbox.clear()
    await db.notes.update(id, { serverSeq: 2 })
    await updateNote(id, { title: 'Typing…' }, db)

    await applyChanges(
      db,
      changes({
        notes: [
          noteRow({ id, seq: 9, title: 'Theirs', color: 'coral', content: fromPlainText('x') }),
        ],
      }),
      9,
    )
    const note = await db.notes.get(id)
    expect(note).toMatchObject({
      title: 'Typing…',
      color: 'coral',
      content: fromPlainText('x'),
      serverSeq: 9,
    })
    // The pending op still carries the base it was made on.
    expect((await db.outbox.toArray())[0]!.baseSeq).toBe(2)
  })

  it('removes a row on a tombstone and drops its pending ops', async () => {
    const db = testDatabase()
    const id = await createNote({ title: 'Doomed' }, db)
    await updateNote(id, { title: 'Edited offline' }, db)
    await applyChanges(db, changes({ notes: [noteRow({ id, seq: 4, deleted: true })] }), 4)
    expect(await db.notes.get(id)).toBeUndefined()
    expect(await db.outbox.count()).toBe(0)
  })

  it('takes rows the server never saw along with their deleted note', async () => {
    const db = testDatabase()
    await applyChanges(db, changes({ notes: [noteRow({ id: 'n1', seq: 1 })] }), 1)
    const labelId = (await createLabel('Home', db))!
    await addItems('n1', ['offline item'], null, db)
    await setNoteLabel('n1', labelId, true, db)

    await applyChanges(db, changes({ notes: [noteRow({ id: 'n1', seq: 2, deleted: true })] }), 2)
    expect(await db.checklistItems.count()).toBe(0)
    expect(await db.noteLabels.count()).toBe(0)
    expect((await db.outbox.toArray()).map((e) => e.entity)).toEqual(['label'])
  })

  it('takes memberships the server never saw along with their deleted label', async () => {
    const db = testDatabase()
    await applyChanges(
      db,
      changes({
        notes: [noteRow({ id: 'n1', seq: 1 })],
        labels: [{ id: 'l1', seq: 2, deleted: false, name: 'Work' }],
      }),
      2,
    )
    await setNoteLabel('n1', 'l1', true, db)
    expect((await db.notes.get('n1'))!.searchText).toContain('work')

    await applyChanges(db, changes({ labels: [{ id: 'l1', seq: 3, deleted: true, name: '' }] }), 3)
    expect(await db.noteLabels.count()).toBe(0)
    expect(await db.outbox.count()).toBe(0)
    expect((await db.notes.get('n1'))!.searchText).not.toContain('work')
  })

  it('does not bring back a row with a pending purge', async () => {
    const db = testDatabase()
    await applyChanges(db, changes({ notes: [noteRow({ id: 'n1', seq: 1 })] }), 1)
    const { purgeNote } = await import('./notes')
    await purgeNote('n1', db)
    await applyChanges(
      db,
      changes({ notes: [noteRow({ id: 'n1', seq: 2, title: 'Edited elsewhere' })] }),
      2,
    )
    expect(await db.notes.get('n1')).toBeUndefined()
  })
})
