<script setup lang="ts">
import branding from '@branding'
import { useInstanceStore } from '@/stores/instance'

defineProps<{ title: string; description?: string }>()

const instance = useInstanceStore()
</script>

<template>
  <main
    class="mx-auto flex min-h-dvh w-full max-w-[400px] flex-col justify-center gap-8 px-4 py-10"
  >
    <header class="flex flex-col gap-2">
      <p class="text-label font-medium text-muted">{{ branding.name }}</p>
      <h1 class="text-xl leading-tight">{{ title }}</h1>
      <p v-if="description" class="text-muted">{{ description }}</p>
    </header>
    <slot />
    <footer
      v-if="instance.config"
      class="font-mono text-meta text-faint tabular-nums"
      data-testid="version"
    >
      {{ $t('home.version', { version: instance.config.version }) }}
    </footer>
  </main>
</template>
