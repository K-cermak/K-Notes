<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { Monitor, Moon, Sun } from '@lucide/vue'
import { themes, type Theme } from '@/theme'
import UiSegmented from '@/components/ui/UiSegmented.vue'

const model = defineModel<Theme>({ required: true })
const { t } = useI18n()

const icons = { system: Monitor, light: Sun, dark: Moon }
const options = computed(() =>
  themes.map((theme) => ({ value: theme, label: t(`theme.${theme}`), icon: icons[theme] })),
)
</script>

<template>
  <UiSegmented v-model="model" :options="options" :label="$t('theme.label')" />
</template>
