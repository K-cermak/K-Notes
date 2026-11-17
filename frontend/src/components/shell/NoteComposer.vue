<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { ImagePlus, ListChecks } from '@lucide/vue'
import type { LocalNote } from '@/db/schema'
import NoteForm from '@/components/notes/NoteForm.vue'
import { pickImages } from '@/composables/useImageAttach'
import { useSyncStore } from '@/stores/sync'
import { iconButton } from '@/components/ui/menu'

// The desktop "Take a note…" bar; it expands in place and saves when it loses focus (SPEC 9).
defineProps<{ labelIds?: string[] }>()

const open = ref(false)
const sync = useSyncStore()
const type = ref<LocalNote['type']>('text')
const files = ref<File[]>([])
const root = ref<HTMLElement | null>(null)
const form = ref<{ finish: () => Promise<void> } | null>(null)

async function close(): Promise<void> {
  if (!open.value) return
  await form.value?.finish()
  open.value = false
}

// Menus and popovers of the form render in portals; clicks there are not outside the composer.
function onPointerDown(event: PointerEvent): void {
  const target = event.target as Element | null
  if (!open.value || !target || root.value?.contains(target)) return
  if (target.closest('[data-reka-popper-content-wrapper], [role="menu"], [role="dialog"]')) return
  void close()
}

onMounted(() => document.addEventListener('pointerdown', onPointerDown))
onBeforeUnmount(() => document.removeEventListener('pointerdown', onPointerDown))

function start(kind: LocalNote['type'] = 'text', images: File[] = []): void {
  if (!sync.hasRoom()) return
  type.value = kind
  files.value = images
  open.value = true
}

async function startWithImages(): Promise<void> {
  if (!sync.hasRoom()) return
  const picked = await pickImages()
  if (picked.length > 0) start('text', picked)
}

defineExpose({ start })
</script>

<template>
  <div ref="root" class="mx-auto w-full max-w-[600px]">
    <div
      v-if="!open"
      class="flex h-12 w-full items-center border border-line bg-bg pr-1.5 transition-colors duration-150 hover:border-line-hover"
    >
      <button
        type="button"
        class="h-full flex-1 cursor-text px-4 text-left font-medium text-faint"
        data-testid="composer"
        @click="start('text')"
      >
        {{ $t('composer.placeholder') }}
      </button>
      <button
        type="button"
        :class="iconButton"
        :aria-label="$t('composer.newList')"
        :title="$t('composer.newList')"
        data-testid="composer-list"
        @click="start('checklist')"
      >
        <ListChecks :size="18" />
      </button>
      <button
        type="button"
        :class="iconButton"
        :aria-label="$t('images.newNote')"
        :title="$t('images.newNote')"
        data-testid="composer-image"
        @click="startWithImages"
      >
        <ImagePlus :size="18" />
      </button>
    </div>
    <div
      v-else
      class="flex animate-rise flex-col border border-line-hover motion-reduce:animate-fade"
    >
      <NoteForm
        ref="form"
        :note-id="null"
        :type="type"
        :label-ids="labelIds"
        :files="files"
        :autofocus="type === 'checklist' ? 'body' : 'title'"
        @close="close"
      />
    </div>
  </div>
</template>
