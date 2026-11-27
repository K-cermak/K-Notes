<script setup lang="ts">
import { onBeforeUnmount, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { DialogContent, DialogOverlay, DialogPortal, DialogRoot, DialogTitle } from 'reka-ui'
import NoteForm from '@/components/notes/NoteForm.vue'
import { useMediaQuery } from '@/composables/useMediaQuery'
import type { NoteColor } from '@/notes'
import { setBarColor } from '@/theme'

// The open note has its own route, so Back and the Android back gesture close it (SPEC 9, Editor).
// On phones it fills the visual viewport, so the on-screen keyboard does not cover its toolbar.
const props = defineProps<{ open: boolean; fallback: string }>()

const route = useRoute()
const router = useRouter()
const form = ref<{ finish: () => Promise<void>; color: NoteColor } | null>(null)
let closing = false

interface Shown {
  id: string
  type: 'text' | 'checklist'
  label?: string
}

// The note being shown outlives its route while the editor animates closed, so the form keeps
// showing it instead of switching to an empty one.
const shown = ref<Shown | null>(null)
watch(
  () => (props.open ? route.fullPath : null),
  (path) => {
    if (path === null) return
    closing = false
    shown.value = {
      id: String(route.params.id),
      type: route.query.type === 'checklist' ? 'checklist' : 'text',
      label: route.query.label ? String(route.query.label) : undefined,
    }
  },
  { immediate: true },
)

// The phone editor fills the screen up to the status bar, which would otherwise keep the page's
// colour above a coloured note.
const phone = useMediaQuery('(max-width: 639px)')
watch(
  () => (props.open && phone.value ? form.value?.color : undefined),
  (color) => setBarColor(color && color !== 'default' ? `var(--note-${color})` : null),
)
onBeforeUnmount(() => setBarColor(null))

async function close(): Promise<void> {
  if (closing) return
  closing = true
  await form.value?.finish()
  // Back keeps the list's scroll position; a directly opened note goes to the list instead.
  if (window.history.state?.back) router.back()
  else await router.replace(props.fallback)
}
</script>

<template>
  <DialogRoot :open="open" @update:open="(value) => !value && close()">
    <DialogPortal>
      <DialogOverlay
        class="fixed inset-0 z-30 animate-fade bg-scrim data-[state=closed]:animate-fade-out"
      />
      <DialogContent
        v-if="shown"
        class="note-editor fixed inset-x-0 top-[var(--viewport-top,0px)] z-30 flex h-[var(--viewport-height,100dvh)] flex-col overflow-hidden bg-bg outline-none sm:inset-auto sm:top-[10dvh] sm:left-1/2 sm:h-auto sm:max-h-[80dvh] sm:w-[600px] sm:-translate-x-1/2 sm:border sm:border-line sm:shadow-float"
        :aria-describedby="undefined"
        data-testid="editor"
      >
        <DialogTitle class="sr-only">{{ $t('note.editor') }}</DialogTitle>
        <NoteForm
          :key="shown.id"
          ref="form"
          :note-id="shown.id === 'new' ? null : shown.id"
          :type="shown.type"
          :autofocus="shown.id === 'new'"
          back
          :label-ids="shown.label ? [shown.label] : undefined"
          @close="close"
        />
      </DialogContent>
    </DialogPortal>
  </DialogRoot>
</template>
