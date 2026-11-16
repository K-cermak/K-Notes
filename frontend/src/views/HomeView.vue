<script setup lang="ts">
import { onMounted } from 'vue'
import { ArrowRight } from '@lucide/vue'
import branding from '@branding'
import { useInstanceStore } from '@/stores/instance'
import UiNotice from '@/components/ui/UiNotice.vue'

const instance = useInstanceStore()

onMounted(() => instance.load())
</script>

<template>
  <main class="mx-auto flex min-h-dvh max-w-[560px] flex-col justify-center gap-6 px-4 py-10">
    <div class="flex flex-col gap-2">
      <h1 class="text-2xl leading-tight">{{ branding.name }}</h1>
      <p class="text-muted">{{ $t('home.tagline') }}</p>
    </div>
    <p
      v-if="instance.config"
      class="font-mono text-meta text-faint tabular-nums"
      data-testid="version"
    >
      {{ $t('home.version', { version: instance.config.version }) }}
    </p>
    <UiNotice v-else-if="instance.failed" tone="error">{{ $t('home.error') }}</UiNotice>
    <p v-else class="text-meta text-faint">{{ $t('home.loading') }}</p>
    <RouterLink
      to="/showcase"
      class="group inline-flex items-center gap-2 self-start font-medium text-accent"
    >
      {{ $t('home.showcase') }}
      <ArrowRight
        :size="16"
        class="transition-transform duration-150 ease-out group-hover:translate-x-[3px]"
      />
    </RouterLink>
  </main>
</template>
