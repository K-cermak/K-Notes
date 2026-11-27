<script setup lang="ts">
import { computed, onBeforeUnmount, watch } from 'vue'
import { DialogContent, DialogOverlay, DialogPortal, DialogRoot, DialogTitle } from 'reka-ui'
import { ChevronLeft, ChevronRight, X } from '@lucide/vue'
import type { LocalAttachment } from '@/db/schema'
import NoteImage from './NoteImage.vue'
import { allowZoom } from '@/zoom'

/** A note's images one at a time over everything else, with arrows between them. */
const props = defineProps<{ attachments: LocalAttachment[] }>()
const index = defineModel<number | null>('index', { required: true })

const current = computed(() => (index.value === null ? undefined : props.attachments[index.value]))
const count = computed(() => props.attachments.length)

// The rest of the app does not zoom, but a photo often needs a closer look.
let releaseZoom: (() => void) | null = null
watch(
  () => !!current.value,
  (open) => {
    if (open) releaseZoom ??= allowZoom()
    else {
      releaseZoom?.()
      releaseZoom = null
    }
  },
  { immediate: true },
)
onBeforeUnmount(() => releaseZoom?.())

function step(by: number): void {
  if (index.value === null || count.value < 2) return
  index.value = (index.value + by + count.value) % count.value
}

function onKeydown(event: KeyboardEvent): void {
  if (event.key === 'ArrowRight') step(1)
  else if (event.key === 'ArrowLeft') step(-1)
}

const control =
  'grid size-11 cursor-pointer place-items-center text-ink hover:bg-[color-mix(in_srgb,var(--ink)_12%,transparent)]'
</script>

<template>
  <DialogRoot :open="!!current" @update:open="(open) => !open && (index = null)">
    <DialogPortal>
      <!-- Always dark, whatever the theme: the tokens follow color-scheme. -->
      <DialogOverlay
        class="fixed inset-0 z-40 animate-fade bg-[color-mix(in_srgb,var(--bg)_97%,transparent)] scheme-dark"
      />
      <DialogContent
        class="fixed inset-0 z-40 flex flex-col text-ink scheme-dark outline-none"
        :aria-describedby="undefined"
        data-testid="image-viewer"
        @keydown="onKeydown"
      >
        <DialogTitle class="sr-only">{{ $t('images.viewer') }}</DialogTitle>
        <div class="flex items-center justify-between px-2 pt-[max(8px,env(safe-area-inset-top))]">
          <span class="ui-meta px-3">
            <template v-if="count > 1">{{ (index ?? 0) + 1 }} / {{ count }}</template>
          </span>
          <button
            type="button"
            :class="control"
            :aria-label="$t('common.close')"
            :title="$t('common.close')"
            @click="index = null"
          >
            <X :size="20" />
          </button>
        </div>
        <div class="relative flex min-h-0 flex-1 items-center justify-center p-4">
          <NoteImage
            v-if="current"
            :key="current.id"
            :attachment="current"
            fit="contain"
            class="max-h-full max-w-full bg-transparent!"
            :style="{
              width: `min(100%, calc((100dvh - 120px) * ${current.width / current.height}))`,
            }"
          />
          <template v-if="count > 1">
            <button
              type="button"
              :class="[control, 'absolute top-1/2 left-2 -translate-y-1/2']"
              :aria-label="$t('images.previous')"
              :title="$t('images.previous')"
              @click="step(-1)"
            >
              <ChevronLeft :size="24" />
            </button>
            <button
              type="button"
              :class="[control, 'absolute top-1/2 right-2 -translate-y-1/2']"
              :aria-label="$t('images.next')"
              :title="$t('images.next')"
              @click="step(1)"
            >
              <ChevronRight :size="24" />
            </button>
          </template>
        </div>
      </DialogContent>
    </DialogPortal>
  </DialogRoot>
</template>
