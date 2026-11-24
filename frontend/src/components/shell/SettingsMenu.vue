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

// The device setting is read when the menu opens, as it can change elsewhere.
async function refresh(open: boolean): Promise<void> {
  if (!open) return
  onDemand.value = (await deviceSettings(db)).downloadOnDemand
}

async function setOnDemand(value: boolean): Promise<void> {
  onDemand.value = value
  await setDeviceSettings(db, { downloadOnDemand: value })
  if (!value) sync.syncNow()
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
      </DropdownMenuContent>
    </DropdownMenuPortal>
  </DropdownMenuRoot>
</template>
