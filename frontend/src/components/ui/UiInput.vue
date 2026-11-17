<script setup lang="ts">
import { ref } from 'vue'

defineProps<{ invalid?: boolean; multiline?: boolean }>()

const model = defineModel<string>({ default: '' })
const field = ref<HTMLInputElement | HTMLTextAreaElement | null>(null)

defineExpose({ focus: () => field.value?.focus() })
</script>

<template>
  <textarea
    v-if="multiline"
    ref="field"
    v-model="model"
    :aria-invalid="invalid || undefined"
    class="ui-input min-h-40 resize-y py-2.5"
  />
  <input
    v-else
    ref="field"
    v-model="model"
    :aria-invalid="invalid || undefined"
    class="ui-input h-10"
  />
</template>

<style scoped>
@reference '../../styles/main.css';

.ui-input {
  @apply w-full border border-line bg-bg px-3 text-sm text-ink transition-[border-color,box-shadow] duration-150 placeholder:text-faint;
  @apply hover:not-focus:not-aria-invalid:border-line-hover;
  @apply focus:border-ink focus:shadow-[0_0_0_3px_var(--ring)] focus:outline-none;
  @apply aria-invalid:border-danger aria-invalid:focus:shadow-[0_0_0_3px_color-mix(in_srgb,var(--danger)_18%,transparent)];
  @apply disabled:cursor-not-allowed disabled:bg-[color-mix(in_srgb,var(--ink)_3%,var(--bg))] disabled:text-faint;
}
</style>
