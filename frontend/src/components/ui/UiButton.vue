<script setup lang="ts">
import { computed } from 'vue'
import UiSpinner from './UiSpinner.vue'

const props = withDefaults(
  defineProps<{
    variant?: 'primary' | 'secondary' | 'ghost' | 'danger'
    size?: 'md' | 'sm'
    type?: 'button' | 'submit' | 'reset'
    disabled?: boolean
    loading?: boolean
    iconOnly?: boolean
  }>(),
  { variant: 'secondary', size: 'md', type: 'button' },
)

const variants = {
  primary: 'bg-accent text-on-accent hover:bg-accent-hover active:bg-accent-hover',
  secondary: 'border border-line bg-bg text-ink hover:border-line-hover',
  ghost: 'text-muted hover:bg-[color-mix(in_srgb,var(--ink)_6%,var(--bg))] hover:text-ink',
  danger: 'border border-line bg-bg text-danger hover:border-danger',
}

const classes = computed(() => [
  variants[props.variant],
  props.size === 'md' ? 'h-10' : 'h-8',
  props.iconOnly ? (props.size === 'md' ? 'w-10' : 'w-8') : props.size === 'md' ? 'px-4' : 'px-3',
  // A loading button keeps its colours, like the reference's sending state, rather than looking disabled.
  props.loading
    ? 'cursor-progress'
    : 'disabled:cursor-not-allowed disabled:border-line disabled:bg-line disabled:text-faint',
])
</script>

<template>
  <button
    :type="type"
    :disabled="disabled || loading"
    :aria-busy="loading || undefined"
    class="inline-flex shrink-0 cursor-pointer items-center justify-center gap-2 font-medium whitespace-nowrap transition-colors duration-150 select-none"
    :class="classes"
  >
    <UiSpinner v-if="loading" />
    <slot />
  </button>
</template>
