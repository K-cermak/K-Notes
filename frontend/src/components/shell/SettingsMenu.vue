<script setup lang="ts">
import { ref } from 'vue'
import {
  DropdownMenuCheckboxItem,
  DropdownMenuContent,
  DropdownMenuItemIndicator,
  DropdownMenuLabel,
  DropdownMenuPortal,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuRoot,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from 'reka-ui'
import { Check, SlidersHorizontal } from '@lucide/vue'
import { themes, type Theme } from '@/theme'
import { deviceSettings, setDeviceSettings } from '@/db/meta'
import { db } from '@/db/schema'
import { useSessionStore } from '@/stores/session'
import { useSyncStore } from '@/stores/sync'
import { iconButton, menuItem, menuPanel } from '@/components/ui/menu'

const session = useSessionStore()
const sync = useSyncStore()
const onDemand = ref(false)
const usage = ref<number | null>(null)

// Device settings and storage use are read when the menu opens, as they can change elsewhere.
async function refresh(open: boolean): Promise<void> {
  if (!open) return
  onDemand.value = (await deviceSettings(db)).downloadOnDemand
  usage.value = (await navigator.storage?.estimate?.())?.usage ?? null
}

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
  <DropdownMenuRoot :modal="false" @update:open="refresh">
    <DropdownMenuTrigger
      :class="iconButton"
      :aria-label="$t('topbar.settings')"
      :title="$t('topbar.settings')"
    >
      <SlidersHorizontal :size="18" />
    </DropdownMenuTrigger>
    <DropdownMenuPortal>
      <DropdownMenuContent :class="menuPanel" align="end" :side-offset="6">
        <DropdownMenuLabel class="ui-menu-label">{{ $t('theme.label') }}</DropdownMenuLabel>
        <DropdownMenuRadioGroup
          :model-value="session.user?.theme"
          @update:model-value="(value) => session.updateProfile({ theme: value as Theme })"
        >
          <DropdownMenuRadioItem
            v-for="theme in themes"
            :key="theme"
            :value="theme"
            :class="menuItem"
          >
            <span class="grid size-4 place-items-center">
              <DropdownMenuItemIndicator><Check :size="16" /></DropdownMenuItemIndicator>
            </span>
            {{ $t(`theme.${theme}`) }}
          </DropdownMenuRadioItem>
        </DropdownMenuRadioGroup>
        <DropdownMenuSeparator class="ui-menu-separator" />
        <DropdownMenuCheckboxItem
          :model-value="onDemand"
          :class="menuItem"
          data-testid="download-on-demand"
          @update:model-value="(value) => setOnDemand(value === true)"
          @select.prevent
        >
          <span class="grid size-4 place-items-center">
            <DropdownMenuItemIndicator><Check :size="16" /></DropdownMenuItemIndicator>
          </span>
          {{ $t('settings.downloadOnDemand') }}
        </DropdownMenuCheckboxItem>
        <p v-if="usage !== null" class="ui-meta px-3 pt-1 pb-2 pl-10" data-testid="storage-use">
          {{ $t('settings.storage', { mb: megabytes(usage) }) }}
        </p>
      </DropdownMenuContent>
    </DropdownMenuPortal>
  </DropdownMenuRoot>
</template>
