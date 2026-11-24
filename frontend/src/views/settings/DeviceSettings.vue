<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { formatBytes } from '@/format'
import { deviceSettings, setDeviceSettings } from '@/db/meta'
import { db } from '@/db/schema'
import { useSyncStore } from '@/stores/sync'
import UiCheckbox from '@/components/ui/UiCheckbox.vue'

const sync = useSyncStore()
const onDemand = ref(false)
const usage = ref<number | null>(null)

onMounted(async () => {
  onDemand.value = (await deviceSettings(db)).downloadOnDemand
  usage.value = (await navigator.storage?.estimate?.())?.usage ?? null
})

async function setOnDemand(value: boolean): Promise<void> {
  onDemand.value = value
  await setDeviceSettings(db, { downloadOnDemand: value })
  if (!value) sync.syncNow()
}
</script>

<template>
  <section class="flex flex-col gap-5">
    <h2 class="ui-section-title">{{ $t('settings.device.title') }}</h2>
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
    <p v-if="usage !== null" class="ui-meta" data-testid="device-usage">
      {{ $t('settings.device.usage', { size: formatBytes(usage) }) }}
    </p>
  </section>
</template>
