import { useI18n } from 'vue-i18n'
import {
  copyNote,
  emptyTrash,
  purgeNote,
  restoreNotes,
  updateNote,
  updateNotes,
  type NotePatch,
} from '@/db/notes'
import { useConfirmStore } from '@/stores/confirm'
import { useSnackbarStore } from '@/stores/snackbar'
import { useSyncStore } from '@/stores/sync'

/** Note actions shared by cards and the editor; reversible ones offer Undo in the snackbar. */
export function useNoteActions() {
  const { t } = useI18n()
  const snackbar = useSnackbarStore()
  const confirm = useConfirmStore()
  const sync = useSyncStore()

  // Bulk actions on selected notes (SPEC 9); one Undo puts every note back as it was.
  async function updateMany(ids: string[], patch: NotePatch, message?: string): Promise<void> {
    const previous = await updateNotes(ids, patch)
    if (message) {
      snackbar.show(message, { label: t('common.undo'), run: () => restoreNotes(previous) })
    }
  }

  return {
    archive(id: string, archived = true): Promise<void> {
      // Undo puts the pin back too, which archiving takes away.
      return updateMany(
        [id],
        { archived, ...(archived ? { pinned: false } : {}) },
        t(archived ? 'note.archived' : 'note.unarchived'),
      )
    },
    async trash(id: string): Promise<void> {
      await updateNote(id, { trashed_at: Date.now() })
      snackbar.show(t('note.trashed'), {
        label: t('common.undo'),
        run: () => updateNote(id, { trashed_at: null }),
      })
    },
    async restore(id: string): Promise<void> {
      await updateNote(id, { trashed_at: null })
      snackbar.show(t('note.restored'))
    },
    async purge(id: string): Promise<boolean> {
      const sure = await confirm.ask({
        title: t('note.deleteForeverTitle'),
        message: t('note.deleteForeverMessage'),
        confirmLabel: t('note.deleteForever'),
        danger: true,
      })
      if (sure) await purgeNote(id)
      return sure
    },
    async emptyTrash(): Promise<void> {
      const sure = await confirm.ask({
        title: t('trash.emptyTitle'),
        message: t('trash.emptyMessage'),
        confirmLabel: t('trash.empty'),
        danger: true,
      })
      if (sure) await emptyTrash()
    },
    async copy(id: string): Promise<void> {
      if (sync.hasRoom() && (await copyNote(id))) snackbar.show(t('note.copied'))
    },
    pin(id: string, pinned: boolean): Promise<void> {
      return updateNote(id, { pinned })
    },

    updateMany,
    archiveMany(ids: string[], archived = true): Promise<void> {
      const key = archived ? 'selection.archived' : 'selection.unarchived'
      return updateMany(
        ids,
        { archived, ...(archived ? { pinned: false } : {}) },
        t(key, { count: ids.length }, ids.length),
      )
    },
    trashMany(ids: string[]): Promise<void> {
      return updateMany(
        ids,
        // The pin stays, as for a single note: restoring puts the note back where it was.
        { trashed_at: Date.now() },
        t('selection.trashed', { count: ids.length }, ids.length),
      )
    },
    restoreMany(ids: string[]): Promise<void> {
      return updateMany(
        ids,
        { trashed_at: null },
        t('selection.restored', { count: ids.length }, ids.length),
      )
    },
    async purgeMany(ids: string[]): Promise<boolean> {
      const sure = await confirm.ask({
        title: t('selection.deleteForeverTitle', { count: ids.length }, ids.length),
        message: t('note.deleteForeverMessage'),
        confirmLabel: t('note.deleteForever'),
        danger: true,
      })
      if (sure) for (const id of ids) await purgeNote(id)
      return sure
    },
  }
}
