<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { deviceSettings, setDeviceSettings } from '@/db/meta'
import { db } from '@/db/schema'
import { useSyncStore } from '@/stores/sync'
import UiCheckbox from '@/components/ui/UiCheckbox.vue'

const sync = useSyncStore()
const onDemand = ref(false)
const usage = ref<{ used: number; quota: number } | null>(null)

onMounted(async () => {
  onDemand.value = (await deviceSettings(db)).downloadOnDemand
  const estimate = await navigator.storage?.estimate?.()
  if (estimate?.usage !== undefined)
    usage.value = { used: estimate.usage, quota: estimate.quota ?? 0 }
})

async function setOnDemand(value: boolean): Promise<void> {
  onDemand.value = value
  await setDeviceSettings(db, { downloadOnDemand: value })
  if (!value) sync.syncNow()
}

function megabytes(bytes: number): string {
  return (bytes / 1_000_000).toFixed(bytes < 10_000_000 ? 1 : 0)
}
</script>

<template>
  <section class="flex flex-col gap-5">
    <h2 class="text-base">{{ $t('settings.device.title') }}</h2>
    <p class="text-muted">{{ $t('settings.device.intro') }}</p>
    <label class="flex cursor-pointer items-start gap-3">
      <UiCheckbox
        :model-value="onDemand"
        class="mt-0.5"
        data-testid="device-on-demand"
        @update:model-value="setOnDemand($event === true)"
      />
      <span class="flex flex-col">
        <span>{{ $t('settings.downloadOnDemand') }}</span>
        <span class="text-label text-muted">{{ $t('settings.device.onDemandHint') }}</span>
      </span>
    </label>
    <p v-if="usage" class="font-mono text-meta text-muted tabular-nums">
      {{ $t('settings.storage', { mb: megabytes(usage.used) }) }}
    </p>
  </section>
</template>
