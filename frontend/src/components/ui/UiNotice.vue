<script setup lang="ts">
import { computed } from 'vue'
import { CircleAlert, CircleCheck, Info, TriangleAlert } from '@lucide/vue'

const props = withDefaults(
  defineProps<{ tone?: 'neutral' | 'info' | 'warning' | 'error' | 'success' }>(),
  { tone: 'neutral' },
)

const tones = {
  neutral: { color: 'var(--muted)', icon: Info },
  info: { color: 'var(--accent)', icon: Info },
  warning: { color: 'var(--warning)', icon: TriangleAlert },
  error: { color: 'var(--danger)', icon: CircleAlert },
  success: { color: 'var(--success)', icon: CircleCheck },
}

const tone = computed(() => tones[props.tone])
</script>

<template>
  <div
    :role="tone === tones.error ? 'alert' : 'status'"
    class="flex items-start gap-2.5 border border-[color-mix(in_srgb,var(--tone)_35%,transparent)] bg-[color-mix(in_srgb,var(--tone)_6%,var(--bg))] px-3.5 py-3 text-sm text-ink"
    :style="{ '--tone': tone.color }"
  >
    <component :is="tone.icon" :size="18" class="mt-px text-(--tone)" aria-hidden="true" />
    <div class="min-w-0 flex-1"><slot /></div>
  </div>
</template>
