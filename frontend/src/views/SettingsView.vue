<script setup lang="ts">
import { ArrowLeft } from '@lucide/vue'

const sections = ['profile', 'security', 'tokens', 'storage', 'device'] as const
</script>

<template>
  <main class="mx-auto flex w-full max-w-[760px] flex-col gap-8 px-4 py-6 sm:py-10">
    <header class="flex items-center gap-3">
      <RouterLink to="/" class="ui-icon-button" :aria-label="$t('common.back')">
        <ArrowLeft />
      </RouterLink>
      <h1 class="text-xl leading-tight">{{ $t('settings.title') }}</h1>
    </header>
    <div class="flex flex-col gap-8 sm:flex-row sm:gap-10">
      <nav
        class="-mx-4 flex shrink-0 gap-1 overflow-x-auto border-b border-line px-4 sm:mx-0 sm:w-44 sm:flex-col sm:border-b-0 sm:px-0"
        :aria-label="$t('settings.title')"
      >
        <RouterLink
          v-for="section in sections"
          :key="section"
          :to="`/settings/${section}`"
          class="-mb-px border-b-2 border-transparent px-2 py-2 whitespace-nowrap text-muted hover:text-ink aria-[current=page]:border-ink aria-[current=page]:text-ink sm:mb-0 sm:border-b-0 sm:border-l-2 sm:px-3"
          :data-testid="`settings-${section}`"
        >
          {{ $t(`settings.${section}.title`) }}
        </RouterLink>
      </nav>
      <div class="flex min-w-0 flex-1 flex-col gap-10">
        <RouterView />
      </div>
    </div>
  </main>
</template>
