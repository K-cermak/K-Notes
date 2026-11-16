<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue'
import NoteForm from '@/components/notes/NoteForm.vue'

// The desktop "Take a note…" bar; it expands in place and saves when it loses focus (SPEC 9).
defineProps<{ labelIds?: string[] }>()

const open = ref(false)
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

defineExpose({ start: () => (open.value = true) })
</script>

<template>
  <div ref="root" class="mx-auto w-full max-w-[600px]">
    <button
      v-if="!open"
      type="button"
      class="flex h-12 w-full cursor-text items-center border border-line bg-bg px-4 text-left font-medium text-faint shadow-none transition-colors duration-150 hover:border-line-hover"
      data-testid="composer"
      @click="open = true"
    >
      {{ $t('composer.placeholder') }}
    </button>
    <div
      v-else
      class="flex animate-rise flex-col border border-line-hover motion-reduce:animate-fade"
    >
      <NoteForm ref="form" :note-id="null" :label-ids="labelIds" autofocus="title" @close="close" />
    </div>
  </div>
</template>
