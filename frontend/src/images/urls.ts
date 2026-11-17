/**
 * Object URLs for stored images, shared by everything showing the same image and revoked when
 * the last of them lets go, so a grid with many photos does not keep them all decoded (SPEC 6).
 */
const entries = new Map<string, { url: string; users: number }>()

export function acquireUrl(hash: string, blob: Blob): string {
  const entry = entries.get(hash)
  if (entry) {
    entry.users += 1
    return entry.url
  }
  const url = URL.createObjectURL(blob)
  entries.set(hash, { url, users: 1 })
  return url
}

export function releaseUrl(hash: string): void {
  const entry = entries.get(hash)
  if (!entry) return
  entry.users -= 1
  if (entry.users > 0) return
  URL.revokeObjectURL(entry.url)
  entries.delete(hash)
}
