<script setup lang="ts">
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import {
  DialogClose,
  DialogContent,
  DialogOverlay,
  DialogPortal,
  DialogRoot,
  DialogTitle,
} from 'reka-ui'
import { Check, Plus, Tag, Trash2 } from '@lucide/vue'
import {
  byName,
  createLabel,
  deleteLabel,
  MAX_LABEL_LENGTH,
  renameLabel,
  setNoteLabel,
} from '@/db/labels'
import { db } from '@/db/schema'
import { useLiveQuery } from '@/composables/useLiveQuery'
import { useSnackbarStore } from '@/stores/snackbar'
import { iconButton } from '@/components/ui/menu'

const open = defineModel<boolean>('open', { required: true })

const { t } = useI18n()
const snackbar = useSnackbarStore()
const labels = useLiveQuery(async () => (await db.labels.toArray()).sort(byName), [])
const newName = ref('')
const error = ref<string | null>(null)

// Undo in the snackbar sits outside the dialog; using it must not close the dialog.
function keepOpenForSnackbar(event: Event): void {
  if ((event.target as Element | null)?.closest('[data-testid="snackbar"]')) event.preventDefault()
}

async function add(): Promise<void> {
  const name = newName.value.trim()
  if (!name) return
  if (labels.value.some((l) => l.name.toLocaleLowerCase() === name.toLocaleLowerCase())) {
    error.value = t('labels.exists')
    return
  }
  // Cleared before the write, so a name typed while it runs is not wiped.
  newName.value = ''
  error.value = null
  await createLabel(name)
}

async function rename(id: string, event: Event): Promise<void> {
  const input = event.target as HTMLInputElement
  const result = await renameLabel(id, input.value)
  error.value = result === 'exists' ? t('labels.exists') : null
  if (result === 'exists' || result === 'invalid') {
    input.value = labels.value.find((l) => l.id === id)?.name ?? ''
  }
}

async function remove(id: string): Promise<void> {
  const removed = await deleteLabel(id)
  if (!removed) return
  snackbar.show(t('labels.deleted'), {
    label: t('common.undo'),
    run: async () => {
      const restored = await createLabel(removed.name)
      if (!restored) return
      for (const noteId of removed.noteIds) await setNoteLabel(noteId, restored, true)
    },
  })
}
</script>

<template>
  <DialogRoot v-model:open="open">
    <DialogPortal>
      <DialogOverlay class="ui-overlay" />
      <DialogContent
        class="ui-dialog max-h-[80dvh] max-w-[340px] gap-0 p-0"
        :aria-describedby="undefined"
        data-testid="edit-labels"
        @interact-outside="keepOpenForSnackbar"
      >
        <DialogTitle class="ui-dialog__title px-4 pt-4 pb-2">
          {{ $t('labels.edit') }}
        </DialogTitle>
        <form class="flex items-center gap-2 px-2" @submit.prevent="add">
          <span class="grid size-9 place-items-center text-muted"><Plus :size="18" /></span>
          <input
            v-model="newName"
            class="h-10 min-w-0 flex-1 border-b border-line bg-transparent outline-none placeholder:text-faint focus:border-ink"
            :placeholder="$t('labels.new')"
            :aria-label="$t('labels.new')"
            :maxlength="MAX_LABEL_LENGTH"
            data-testid="new-label"
          />
          <button
            type="submit"
            :class="iconButton"
            :aria-label="$t('labels.add')"
            :title="$t('labels.add')"
          >
            <Check :size="18" />
          </button>
        </form>
        <p v-if="error" class="px-4 pt-1 text-label text-danger" role="alert">{{ error }}</p>
        <ul class="mt-2 min-h-0 flex-1 overflow-y-auto px-2 pb-2">
          <li v-for="label in labels" :key="label.id" class="group flex items-center gap-2">
            <span
              class="grid size-9 place-items-center text-muted group-focus-within:hidden group-hover:hidden"
            >
              <Tag :size="18" />
            </span>
            <button
              type="button"
              class="hidden group-focus-within:grid group-hover:grid"
              :class="iconButton"
              :aria-label="$t('labels.delete', { name: label.name })"
              :title="$t('labels.delete', { name: label.name })"
              data-testid="delete-label"
              @click="remove(label.id)"
            >
              <Trash2 :size="18" />
            </button>
            <input
              :value="label.name"
              class="h-10 min-w-0 flex-1 border-b border-transparent bg-transparent outline-none focus:border-ink"
              :aria-label="$t('labels.rename', { name: label.name })"
              :maxlength="MAX_LABEL_LENGTH"
              data-testid="label-name"
              @change="rename(label.id, $event)"
              @keydown.enter.prevent="($event.target as HTMLInputElement).blur()"
            />
          </li>
        </ul>
        <div class="flex justify-end border-t border-line px-2 py-2">
          <DialogClose class="ui-button ui-button--ghost text-ink">
            {{ $t('common.done') }}
          </DialogClose>
        </div>
      </DialogContent>
    </DialogPortal>
  </DialogRoot>
</template>
