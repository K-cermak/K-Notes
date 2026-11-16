<script setup lang="ts">
defineProps<{
  label: string
  for: string
  error?: string
  hint?: string
}>()
</script>

<template>
  <div class="group flex flex-col gap-2">
    <div class="flex items-baseline justify-between gap-4">
      <label
        :for="$props.for"
        class="text-label font-medium text-muted transition-colors duration-150 group-focus-within:text-ink"
      >
        {{ label }}
      </label>
      <slot name="aside" />
    </div>
    <slot />
    <p
      v-if="error"
      :id="`${$props.for}-error`"
      class="animate-rise text-label text-danger motion-reduce:animate-fade"
    >
      {{ error }}
    </p>
    <p v-else-if="hint" :id="`${$props.for}-hint`" class="text-meta text-faint">{{ hint }}</p>
  </div>
</template>
