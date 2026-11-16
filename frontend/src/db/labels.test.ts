import { describe, expect, it } from 'vitest'
import { createLabel, deleteLabel, membershipId, renameLabel, setNoteLabel } from './labels'
import { createNote } from './notes'
import { testDatabase } from './testing'

describe('labels', () => {
  it('does not create a second label with the same name', async () => {
    const db = testDatabase()
    const first = await createLabel(' Work ', db)
    expect(await createLabel('work', db)).toBe(first)
    expect(await createLabel('   ', db)).toBeNull()
    expect(await createLabel('x'.repeat(51), db)).toBeNull()
    expect(await db.labels.count()).toBe(1)
  })

  it('refuses a rename to a name in use', async () => {
    const db = testDatabase()
    await createLabel('Home', db)
    const work = (await createLabel('Work', db))!
    expect(await renameLabel(work, 'HOME', db)).toBe('exists')
    expect(await renameLabel(work, 'Office', db)).toBe('renamed')
    expect((await db.labels.get(work))!.name).toBe('Office')
  })

  it('deleting a label removes it from notes, keeps the notes and reports them for Undo', async () => {
    const db = testDatabase()
    const note = await createNote({ title: 'Kept' }, db)
    const label = (await createLabel('Old', db))!
    await setNoteLabel(note, label, true, db)
    await db.labels.update(label, { serverSeq: 4 })
    await db.outbox.clear()

    expect(await deleteLabel(label, db)).toEqual({ name: 'Old', noteIds: [note] })
    expect(await db.noteLabels.count()).toBe(0)
    expect(await db.notes.get(note)).toBeDefined()
    expect((await db.outbox.toArray()).map((e) => [e.entity, e.kind, e.baseSeq])).toEqual([
      ['label', 'purge', 4],
    ])
  })

  it('adding and removing a label before it syncs leaves nothing to send', async () => {
    const db = testDatabase()
    const note = await createNote({}, db)
    const label = (await createLabel('Temp', db))!
    await db.outbox.clear()
    await setNoteLabel(note, label, true, db)
    expect(await db.noteLabels.get(membershipId(note, label))).toBeDefined()
    await setNoteLabel(note, label, false, db)
    expect(await db.outbox.count()).toBe(0)
  })
})
