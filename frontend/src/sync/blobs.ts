import { Failure } from '@/api/client'
import { discardBlob, pruneBlobs } from '@/db/attachments'
import type { NotesDatabase, OutboxEntry } from '@/db/schema'
import type { BlobTransfer } from './engine'

export interface BlobApi {
  exists(hash: string): Promise<boolean>
  upload(hash: string, blob: Blob): Promise<void>
  /** Null when the server does not have it for this user. */
  download(hash: string): Promise<Blob | null>
}

// Answers that will not change on a retry: the image is too large, not an image, or corrupted.
const REFUSED = new Set([400, 413, 415, 422])

/** Moves image bytes in the first and last step of a sync cycle (SPEC 5.6 and 6). */
export class BlobSync implements BlobTransfer {
  constructor(
    private readonly db: NotesDatabase,
    private readonly api: BlobApi,
    private readonly options: {
      /** "Download images on demand": the cycle then leaves images on the server. */
      onDemand?: () => Promise<boolean>
      /** Images the server refused, after their attachments were removed here. */
      onRefused?: (count: number) => void
    } = {},
  ) {}

  async upload(): Promise<void> {
    for (const { hash, blob } of await this.db.blobs.where('uploaded').equals(0).toArray()) {
      try {
        if (!(await this.api.exists(hash))) await this.api.upload(hash, blob)
      } catch (e) {
        if (e instanceof Failure && e.status !== null && REFUSED.has(e.status)) {
          console.warn('Image refused by the server', hash, e.code)
          this.options.onRefused?.(await discardBlob(hash, this.db))
          continue
        }
        throw e
      }
      await this.db.blobs.update(hash, { uploaded: 1 })
    }
  }

  async holdsBack(entry: OutboxEntry): Promise<boolean> {
    const hash = entry.entity === 'attachment' ? entry.fields.blob_hash : undefined
    if (entry.kind !== 'upsert' || typeof hash !== 'string') return false
    return (await this.db.blobs.get(hash))?.uploaded === 0
  }

  /**
   * The server no longer has an image this device marked as uploaded, as when it was cleaned up
   * after its last note was deleted elsewhere. Uploading it again lets the op through.
   */
  async missing(entry: OutboxEntry): Promise<boolean> {
    const hash = entry.fields.blob_hash
    if (typeof hash !== 'string' || !(await this.db.blobs.get(hash))) return false
    await this.db.blobs.update(hash, { uploaded: 0 })
    return true
  }

  async download(): Promise<void> {
    await pruneBlobs(this.db)
    if (await this.options.onDemand?.()) return
    await this.fetch(await this.db.attachments.orderBy('blob_hash').uniqueKeys())
  }

  /** Downloads one note's images, for a device that downloads images on demand. */
  async downloadNote(noteId: string): Promise<void> {
    const rows = await this.db.attachments.where('note_id').equals(noteId).toArray()
    await this.fetch(rows.map((row) => row.blob_hash))
  }

  private async fetch(hashes: Iterable<unknown>): Promise<void> {
    for (const hash of new Set(hashes)) {
      if (typeof hash !== 'string' || !hash || (await this.db.blobs.get(hash))) continue
      const blob = await this.api.download(hash)
      // Missing for now, for example while another device has not uploaded it yet.
      if (!blob) continue
      await this.db.blobs.put({ hash, blob, uploaded: 1 })
    }
  }
}
