<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { ImageDown } from '@lucide/vue'
import { db, type LocalAttachment } from '@/db/schema'
import { acquireUrl, releaseUrl } from '@/images/urls'
import { useLiveQuery } from '@/composables/useLiveQuery'

/**
 * One stored image. A lazy image gets its object URL only while it is on screen; until its bytes
 * are here it is a placeholder with the image's aspect ratio.
 */
const props = defineProps<{
  attachment: Pick<LocalAttachment, 'blob_hash' | 'width' | 'height'>
  lazy?: boolean
  fit?: 'cover' | 'contain'
}>()
const emit = defineEmits<{ missing: [] }>()

const root = ref<HTMLElement | null>(null)
const visible = ref(!props.lazy)
const stored = useLiveQuery(
  () => db.blobs.get(props.attachment.blob_hash),
  undefined,
  () => props.attachment.blob_hash,
)
const url = ref<string | null>(null)
let held: string | null = null

function release(): void {
  if (held) releaseUrl(held)
  held = null
  url.value = null
}

watch(
  [visible, stored],
  ([isVisible, blob]) => {
    if (isVisible && blob && held === blob.hash) return
    release()
    if (!isVisible || !blob) return
    held = blob.hash
    url.value = acquireUrl(blob.hash, blob.blob)
  },
  { immediate: true },
)

let observer: IntersectionObserver | null = null
onMounted(() => {
  if (!props.lazy || !root.value) return
  observer = new IntersectionObserver(
    ([entry]) => {
      visible.value = entry?.isIntersecting ?? false
    },
    { rootMargin: '300px 0px' },
  )
  observer.observe(root.value)
})
onBeforeUnmount(() => {
  observer?.disconnect()
  release()
})
</script>

<template>
  <div
    ref="root"
    class="relative overflow-hidden bg-[color-mix(in_srgb,var(--ink)_7%,transparent)]"
    :style="{ aspectRatio: `${attachment.width} / ${attachment.height}` }"
    data-testid="note-image"
    :data-loaded="!!url"
  >
    <img
      v-if="url"
      :src="url"
      alt=""
      draggable="false"
      class="block size-full"
      :class="fit === 'contain' ? 'object-contain' : 'object-cover'"
    />
    <button
      v-else-if="visible && stored === undefined"
      type="button"
      class="absolute inset-0 grid cursor-pointer place-items-center text-faint hover:text-muted"
      :aria-label="$t('images.download')"
      :title="$t('images.download')"
      @click.stop="emit('missing')"
    >
      <ImageDown :size="22" />
    </button>
  </div>
</template>
