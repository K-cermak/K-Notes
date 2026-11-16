import { describe, expect, it } from 'vitest'
import { copyNote, createNote, emptyTrash, isNoteEmpty, updateNote } from './notes'
import { fromPlainText } from './richtext'
import { testDatabase } from './testing'

describe('note repository', () => {
  it('copies a note with its items, labels and images, unpinned at the top', async () => {
    const db = testDatabase()
    const id = await createNote({ title: 'Trip', pinned: true, color: 'sage' }, db)
    await db.checklistItems.add({
      id: 'i1',
      note_id: id,
      text: 'Passport',
      checked: false,
      position: 'a0',
      serverSeq: 3,
    })
    await db.noteLabels.add({ id: `${id}:l1`, note_id: id, label_id: 'l1', serverSeq: 3 })
    await db.attachments.add({
      id: 'a1',
      note_id: id,
      blob_hash: 'f'.repeat(64),
      mime: 'image/png',
      width: 1,
      height: 1,
      size: 1,
      position: 'a0',
      serverSeq: 3,
    })
    await db.outbox.clear()

    const copyId = (await copyNote(id, db))!
    const copy = await db.notes.get(copyId)
    expect(copy).toMatchObject({ title: 'Trip', color: 'sage', pinned: false, serverSeq: 0 })
    expect(copy!.position < (await db.notes.get(id))!.position).toBe(true)
    expect(await db.checklistItems.where('note_id').equals(copyId).toArray()).toEqual([
      expect.objectContaining({ text: 'Passport', serverSeq: 0 }),
    ])
    expect(await db.noteLabels.get(`${copyId}:l1`)).toBeDefined()
    expect((await db.attachments.where('note_id').equals(copyId).first())?.blob_hash).toBe(
      'f'.repeat(64),
    )
    expect((await db.outbox.toArray()).map((e) => e.entity).sort()).toEqual([
      'attachment',
      'checklist_item',
      'note',
      'note_label',
    ])
  })

  it('empties the trash and nothing else', async () => {
    const db = testDatabase()
    const kept = await createNote({ title: 'Keep' }, db)
    const trashed = await createNote({ title: 'Gone' }, db)
    await updateNote(trashed, { trashed_at: 1 }, db)
    await emptyTrash(db)
    expect((await db.notes.toArray()).map((n) => n.id)).toEqual([kept])
  })

  it('treats a note without title, text, items or images as empty', async () => {
    const db = testDatabase()
    const id = await createNote({ content: fromPlainText('  ') }, db)
    expect(await isNoteEmpty(id, db)).toBe(true)
    await updateNote(id, { title: 'x' }, db)
    expect(await isNoteEmpty(id, db)).toBe(false)
  })
})
