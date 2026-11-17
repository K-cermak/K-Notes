import { useI18n } from 'vue-i18n'
import { attachImages } from '@/db/attachments'
import { ACCEPTED_TYPES, ImageError, processImage, type ProcessedImage } from '@/images/process'
import { useInstanceStore } from '@/stores/instance'
import { useSnackbarStore } from '@/stores/snackbar'
import { useSyncStore } from '@/stores/sync'

/** Asks for image files. Must be called from a user gesture, which the file dialog needs. */
export function pickImages(): Promise<File[]> {
  return new Promise((resolve) => {
    const input = document.createElement('input')
    input.type = 'file'
    input.accept = ACCEPTED_TYPES.join(',')
    input.multiple = true
    input.addEventListener('change', () => resolve([...(input.files ?? [])]))
    input.addEventListener('cancel', () => resolve([]))
    input.click()
  })
}

/** Processes picked files and attaches them to a note, reporting the ones that could not be used. */
export function useImageAttach() {
  const { t } = useI18n()
  const instance = useInstanceStore()
  const snackbar = useSnackbarStore()
  const sync = useSyncStore()

  async function prepare(files: File[]): Promise<ProcessedImage[]> {
    const maxBytes = (instance.config?.max_image_mb ?? 10) * 1024 * 1024
    const ready: ProcessedImage[] = []
    let failed: ImageError['code'] | null = null
    for (const file of files) {
      try {
        ready.push(await processImage(file, maxBytes))
      } catch (e) {
        if (!(e instanceof ImageError)) throw e
        failed = e.code
      }
    }
    if (failed) {
      snackbar.show(t(`images.${failed}`, { mb: instance.config?.max_image_mb ?? 10 }))
    }
    return ready
  }

  /** Picks images and attaches them to the note the target resolves to (a draft is created first). */
  async function pickAndAttach(target: string | (() => Promise<string | null>)): Promise<void> {
    if (!sync.hasRoom()) return
    const files = await pickImages()
    await attachFiles(target, files)
  }

  async function attachFiles(
    target: string | (() => Promise<string | null>),
    files: File[],
  ): Promise<void> {
    if (files.length === 0) return
    const images = await prepare(files)
    if (images.length === 0) return
    const noteId = typeof target === 'string' ? target : await target()
    if (noteId) await attachImages(noteId, images)
  }

  return { pickAndAttach, attachFiles }
}
