<script setup lang="ts">
import { computed } from 'vue'
import { CircleAlert, CircleCheck, Info, TriangleAlert } from '@lucide/vue'

const props = withDefaults(
  defineProps<{ tone?: 'neutral' | 'info' | 'warning' | 'error' | 'success' }>(),
  { tone: 'neutral' },
)

const icons = {
  neutral: Info,
  info: Info,
  warning: TriangleAlert,
  error: CircleAlert,
  success: CircleCheck,
}

const icon = computed(() => icons[props.tone])
</script>

<template>
  <div
    :role="tone === 'error' ? 'alert' : 'status'"
    class="ui-notice"
    :class="tone !== 'neutral' && `ui-notice--${tone}`"
  >
    <component :is="icon" :size="18" class="ui-notice__icon" aria-hidden="true" />
    <div class="min-w-0 flex-1"><slot /></div>
  </div>
</template>
