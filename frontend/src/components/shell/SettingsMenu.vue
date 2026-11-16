<script setup lang="ts">
import {
  DropdownMenuContent,
  DropdownMenuItemIndicator,
  DropdownMenuLabel,
  DropdownMenuPortal,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuRoot,
  DropdownMenuTrigger,
} from 'reka-ui'
import { Check, Settings } from '@lucide/vue'
import { themes, type Theme } from '@/theme'
import { useSessionStore } from '@/stores/session'
import { iconButton, menuItem, menuPanel } from '@/components/ui/menu'

const session = useSessionStore()
</script>

<template>
  <DropdownMenuRoot :modal="false">
    <DropdownMenuTrigger
      :class="iconButton"
      :aria-label="$t('topbar.settings')"
      :title="$t('topbar.settings')"
    >
      <Settings :size="18" />
    </DropdownMenuTrigger>
    <DropdownMenuPortal>
      <DropdownMenuContent :class="menuPanel" align="end" :side-offset="6">
        <DropdownMenuLabel class="px-3 pt-2 pb-1 text-meta text-muted">{{
          $t('theme.label')
        }}</DropdownMenuLabel>
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
      </DropdownMenuContent>
    </DropdownMenuPortal>
  </DropdownMenuRoot>
</template>
