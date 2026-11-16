import { describe, expect, it } from 'vitest'
import { createNote, purgeNote, updateNote } from './notes'
import { fromPlainText } from './richtext'
import { testDatabase } from './testing'

describe('outbox coalescing', () => {
  it('merges edits into the unsent op and keeps its base_seq', async () => {
    const db = testDatabase()
    const id = await createNote({ title: 'One' }, db)
    await db.notes.update(id, { serverSeq: 7 })
    await db.outbox.clear()

    await updateNote(id, { title: 'Two' }, db)
    const [first] = await db.outbox.toArray()
    await updateNote(id, { content: fromPlainText('body'), color: 'mint' }, db)
    await updateNote(id, { title: 'Three' }, db)

    const entries = await db.outbox.toArray()
    expect(entries).toHaveLength(1)
    expect(entries[0]!.baseSeq).toBe(7)
    expect(entries[0]!.fields).toEqual({
      title: 'Three',
      content: fromPlainText('body'),
      color: 'mint',
    })
    expect(entries[0]!.opId).not.toBe(first!.opId)
  })

  it('does not merge into an op that is being pushed', async () => {
    const db = testDatabase()
    const id = await createNote({}, db)
    await db.outbox.toCollection().modify({ inFlight: 1 })
    await updateNote(id, { title: 'Later' }, db)
    const entries = await db.outbox.orderBy('seq').toArray()
    expect(entries.map((e) => [e.inFlight, e.fields.title])).toEqual([
      [1, ''],
      [0, 'Later'],
    ])
  })

  it('ignores writes that change nothing', async () => {
    const db = testDatabase()
    const id = await createNote({ title: 'Same' }, db)
    await db.outbox.clear()
    await updateNote(id, { title: 'Same' }, db)
    expect(await db.outbox.count()).toBe(0)
  })

  it('forgets a note that never reached the server', async () => {
    const db = testDatabase()
    const id = await createNote({ title: 'Oops' }, db)
    await purgeNote(id, db)
    expect(await db.outbox.count()).toBe(0)
    expect(await db.notes.count()).toBe(0)
  })

  it('replaces pending edits with a purge once the server has the note', async () => {
    const db = testDatabase()
    const id = await createNote({}, db)
    await db.outbox.clear()
    await db.notes.update(id, { serverSeq: 3 })
    await updateNote(id, { title: 'Edit' }, db)
    await purgeNote(id, db)
    const entries = await db.outbox.toArray()
    expect(entries.map((e) => [e.kind, e.baseSeq])).toEqual([['purge', 3]])
  })

  it('sends a purge when the create is already in flight', async () => {
    const db = testDatabase()
    const id = await createNote({}, db)
    await db.outbox.toCollection().modify({ inFlight: 1 })
    await purgeNote(id, db)
    expect((await db.outbox.toArray()).map((e) => e.kind)).toEqual(['upsert', 'purge'])
  })

  it('drops pending ops of the children of a purged note', async () => {
    const db = testDatabase()
    const id = await createNote({}, db)
    await db.notes.update(id, { serverSeq: 1 })
    await db.outbox.clear()
    await db.checklistItems.add({
      id: 'item',
      note_id: id,
      text: 'x',
      checked: false,
      position: 'a0',
      serverSeq: 0,
    })
    await db.outbox.add({
      opId: 'op',
      entity: 'checklist_item',
      entityId: 'item',
      kind: 'upsert',
      fields: { text: 'x' },
      baseSeq: 0,
      editedAt: 1,
      inFlight: 0,
    })
    await purgeNote(id, db)
    expect(await db.checklistItems.count()).toBe(0)
    expect((await db.outbox.toArray()).map((e) => e.entity)).toEqual(['note'])
  })

  it('puts a new note before the current first one', async () => {
    const db = testDatabase()
    const older = await createNote({}, db)
    const newer = await createNote({}, db)
    const [a, b] = await Promise.all([db.notes.get(older), db.notes.get(newer)])
    expect(b!.position < a!.position).toBe(true)
  })
})
