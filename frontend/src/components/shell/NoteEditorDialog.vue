<script setup lang="ts">
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { DialogContent, DialogOverlay, DialogPortal, DialogRoot, DialogTitle } from 'reka-ui'
import NoteForm from '@/components/notes/NoteForm.vue'

// The open note has its own route, so Back and the Android back gesture close it (SPEC 9, Editor).
const props = defineProps<{ fallback: string }>()

const route = useRoute()
const router = useRouter()
const form = ref<{ finish: () => Promise<void> } | null>(null)
let closing = false

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
  <DialogRoot :open="true" @update:open="(open) => !open && close()">
    <DialogPortal>
      <DialogOverlay
        class="fixed inset-0 z-30 animate-fade bg-[color-mix(in_srgb,var(--ink)_28%,transparent)]"
      />
      <DialogContent
        class="fixed inset-0 z-30 flex flex-col overflow-hidden bg-bg outline-none motion-reduce:animate-fade sm:inset-auto sm:top-[10dvh] sm:left-1/2 sm:max-h-[80dvh] sm:w-[600px] sm:-translate-x-1/2 sm:animate-rise sm:border sm:border-line sm:shadow-float"
        :aria-describedby="undefined"
        data-testid="editor"
      >
        <DialogTitle class="sr-only">{{ $t('note.editor') }}</DialogTitle>
        <NoteForm
          :key="String(route.params.id)"
          ref="form"
          :note-id="route.params.id === 'new' ? null : String(route.params.id)"
          :autofocus="route.params.id === 'new' ? 'title' : undefined"
          :label-ids="route.query.label ? [String(route.query.label)] : undefined"
          @close="close"
        />
      </DialogContent>
    </DialogPortal>
  </DialogRoot>
</template>
