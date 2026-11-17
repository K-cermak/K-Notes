<script setup lang="ts">
import UiSpinner from './UiSpinner.vue'

/** The .ui-button classes of styles/ui.css as a component, with a spinner while loading. */
withDefaults(
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
</script>

<template>
  <button
    :type="type"
    :disabled="disabled || loading"
    :aria-busy="loading || undefined"
    class="ui-button"
    :class="[
      variant !== 'secondary' && `ui-button--${variant}`,
      size === 'sm' && 'ui-button--sm',
      iconOnly && 'ui-button--icon',
    ]"
  >
    <UiSpinner v-if="loading" />
    <slot />
  </button>
</template>
