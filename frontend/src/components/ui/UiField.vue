<script setup lang="ts">
defineProps<{
  label: string
  for: string
  error?: string
  hint?: string
}>()
</script>

<template>
  <div class="ui-field">
    <div class="flex items-baseline justify-between gap-4">
      <label :for="$props.for" class="ui-label">{{ label }}</label>
      <slot name="aside" />
    </div>
    <slot />
    <p v-if="error" :id="`${$props.for}-error`" class="ui-error">{{ error }}</p>
    <p v-else-if="hint" :id="`${$props.for}-hint`" class="ui-hint">{{ hint }}</p>
  </div>
</template>
