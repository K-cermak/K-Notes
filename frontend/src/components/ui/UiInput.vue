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
    class="ui-input"
  />
  <input v-else ref="field" v-model="model" :aria-invalid="invalid || undefined" class="ui-input" />
</template>
