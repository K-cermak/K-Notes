import { useI18n } from 'vue-i18n'
import { copyNote, emptyTrash, purgeNote, updateNote } from '@/db/notes'
import { useConfirmStore } from '@/stores/confirm'
import { useSnackbarStore } from '@/stores/snackbar'

/** Note actions shared by cards and the editor; reversible ones offer Undo in the snackbar. */
export function useNoteActions() {
  const { t } = useI18n()
  const snackbar = useSnackbarStore()
  const confirm = useConfirmStore()

  return {
    async archive(id: string, archived = true): Promise<void> {
      await updateNote(id, { archived, ...(archived ? { pinned: false } : {}) })
      snackbar.show(t(archived ? 'note.archived' : 'note.unarchived'), {
        label: t('common.undo'),
        run: () => updateNote(id, { archived: !archived }),
      })
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
      if (await copyNote(id)) snackbar.show(t('note.copied'))
    },
    pin(id: string, pinned: boolean): Promise<void> {
      return updateNote(id, { pinned })
    },
  }
}
