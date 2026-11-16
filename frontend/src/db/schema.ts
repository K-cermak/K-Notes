import { Dexie, type EntityTable } from 'dexie'
import type { components } from '@/api/schema'

type Schemas = components['schemas']
export type RichDoc = Schemas['RichDoc']
export type Entity = 'note' | 'checklist_item' | 'label' | 'note_label' | 'attachment'

/** A synced row as stored locally: the server row without its bookkeeping, plus the server version. */
type Local<Row extends { seq: number; deleted: boolean }> = Omit<Row, 'seq' | 'deleted'> & {
  /** The row's seq as last seen from the server, sent as base_seq; 0 if it never reached the server. */
  serverSeq: number
}

export type LocalNote = Local<Schemas['NoteRow']>
export type LocalChecklistItem = Local<Schemas['ChecklistItemRow']>
export type LocalLabel = Local<Schemas['LabelRow']>
export type LocalNoteLabel = Local<Schemas['NoteLabelRow']>
export type LocalAttachment = Local<Schemas['AttachmentRow']>

export interface LocalBlob {
  hash: string
  blob: Blob
  uploaded: 0 | 1
}

export interface OutboxEntry {
  /** Auto-incremented; ops are pushed in this order. */
  seq?: number
  opId: string
  entity: Entity
  entityId: string
  kind: 'upsert' | 'purge'
  fields: Record<string, unknown>
  baseSeq: number
  editedAt: number
  /** 1 while a push carrying this op is under way; new edits must not be merged into it. */
  inFlight: 0 | 1
}

export interface MetaEntry {
  key: string
  value: unknown
}

export class NotesDatabase extends Dexie {
  notes!: EntityTable<LocalNote, 'id'>
  checklistItems!: EntityTable<LocalChecklistItem, 'id'>
  labels!: EntityTable<LocalLabel, 'id'>
  noteLabels!: EntityTable<LocalNoteLabel, 'id'>
  attachments!: EntityTable<LocalAttachment, 'id'>
  blobs!: EntityTable<LocalBlob, 'hash'>
  outbox!: EntityTable<OutboxEntry, 'seq'>
  meta!: EntityTable<MetaEntry, 'key'>

  constructor(name = 'notes') {
    super(name)
    this.version(1).stores({
      notes: 'id, position',
      checklistItems: 'id, note_id',
      labels: 'id',
      noteLabels: 'id, note_id, label_id',
      attachments: 'id, note_id, blob_hash',
      blobs: 'hash, uploaded',
      outbox: '++seq, [entity+entityId]',
      meta: 'key',
    })
  }

  syncedTable(entity: Entity) {
    return {
      note: this.notes,
      checklist_item: this.checklistItems,
      label: this.labels,
      note_label: this.noteLabels,
      attachment: this.attachments,
    }[entity]
  }

  get syncedTables() {
    return [this.notes, this.checklistItems, this.labels, this.noteLabels, this.attachments]
  }
}

export const db = new NotesDatabase()
