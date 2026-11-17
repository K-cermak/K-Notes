/** Client-side image processing before an image is stored (SPEC 6). */

export const ACCEPTED_TYPES = ['image/jpeg', 'image/png', 'image/webp', 'image/gif']
export const MAX_EDGE = 2560
export const REENCODE_ABOVE_BYTES = 1_000_000
const JPEG_QUALITY = 0.85

export interface ProcessedImage {
  blob: Blob
  hash: string
  mime: string
  width: number
  height: number
  size: number
}

export class ImageError extends Error {
  constructor(readonly code: 'unsupported' | 'unreadable' | 'too_large') {
    super(code)
  }
}

export interface ImagePlan {
  width: number
  height: number
  reencode: boolean
}

/**
 * Scale down past 2560 px on the longer edge, re-encode as JPEG when resized or larger than 1 MB,
 * otherwise keep the original bytes. GIFs are kept as they are, since re-encoding drops animation.
 */
export function planImage(mime: string, size: number, width: number, height: number): ImagePlan {
  if (mime === 'image/gif') return { width, height, reencode: false }
  const longest = Math.max(width, height)
  if (longest > MAX_EDGE) {
    const scale = MAX_EDGE / longest
    return {
      width: Math.max(1, Math.round(width * scale)),
      height: Math.max(1, Math.round(height * scale)),
      reencode: true,
    }
  }
  return { width, height, reencode: size > REENCODE_ABOVE_BYTES }
}

export async function hashBlob(blob: Blob): Promise<string> {
  const digest = await crypto.subtle.digest('SHA-256', await blob.arrayBuffer())
  return Array.from(new Uint8Array(digest), (byte) => byte.toString(16).padStart(2, '0')).join('')
}

async function encodeJpeg(bitmap: ImageBitmap, width: number, height: number): Promise<Blob> {
  const canvas = new OffscreenCanvas(width, height)
  const context = canvas.getContext('2d')
  if (!context) throw new ImageError('unreadable')
  // JPEG has no transparency; without a background, transparent areas of a PNG turn black.
  context.fillStyle = '#ffffff'
  context.fillRect(0, 0, width, height)
  context.imageSmoothingQuality = 'high'
  context.drawImage(bitmap, 0, 0, width, height)
  return canvas.convertToBlob({ type: 'image/jpeg', quality: JPEG_QUALITY })
}

export async function processImage(file: Blob, maxBytes: number): Promise<ProcessedImage> {
  if (!ACCEPTED_TYPES.includes(file.type)) throw new ImageError('unsupported')
  let bitmap: ImageBitmap
  try {
    // Applies the EXIF orientation, so width and height are as the image is shown.
    bitmap = await createImageBitmap(file)
  } catch {
    throw new ImageError('unreadable')
  }
  const plan = planImage(file.type, file.size, bitmap.width, bitmap.height)
  try {
    const blob = plan.reencode
      ? await encodeJpeg(bitmap, plan.width, plan.height)
      : new Blob([file], { type: file.type })
    if (blob.size > maxBytes) throw new ImageError('too_large')
    return {
      blob,
      hash: await hashBlob(blob),
      mime: blob.type,
      width: plan.width,
      height: plan.height,
      size: blob.size,
    }
  } finally {
    bitmap.close()
  }
}
