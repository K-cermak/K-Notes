<script setup lang="ts">
import { LayoutGrid, Menu, NotebookPen, Rows3 } from '@lucide/vue'
import branding from '@branding'
import { useSessionStore } from '@/stores/session'
import { iconButton } from '@/components/ui/menu'
import SyncStatus from '@/components/SyncStatus.vue'
import AccountMenu from './AccountMenu.vue'
import SettingsMenu from './SettingsMenu.vue'

defineProps<{ compact: boolean; drawerOpen: boolean }>()
const emit = defineEmits<{ menu: [] }>()

const session = useSessionStore()
</script>

<template>
  <header
    class="sticky top-0 z-20 flex h-16 items-center gap-1 border-b border-line bg-bg pt-[env(safe-area-inset-top)] pr-3 pl-2 sm:pl-3"
  >
    <button
      type="button"
      :class="iconButton"
      :aria-label="$t('topbar.menu')"
      :aria-expanded="drawerOpen"
      :title="$t('topbar.menu')"
      @click="emit('menu')"
    >
      <Menu :size="20" />
    </button>
    <RouterLink to="/" class="ml-1 flex items-center gap-2.5 pr-4">
      <span class="grid size-8 place-items-center bg-ink text-bg" aria-hidden="true">
        <NotebookPen :size="18" />
      </span>
      <span class="text-[17px] font-semibold tracking-[-0.02em]">{{ branding.name }}</span>
    </RouterLink>
    <div class="flex-1" />
    <SyncStatus />
    <template v-if="!compact">
      <button
        type="button"
        :class="iconButton"
        :aria-label="
          $t(session.user?.default_view === 'list' ? 'topbar.gridView' : 'topbar.listView')
        "
        :title="$t(session.user?.default_view === 'list' ? 'topbar.gridView' : 'topbar.listView')"
        data-testid="view-toggle"
        @click="
          session.updateProfile({
            default_view: session.user?.default_view === 'list' ? 'grid' : 'list',
          })
        "
      >
        <LayoutGrid v-if="session.user?.default_view === 'list'" :size="18" />
        <Rows3 v-else :size="18" />
      </button>
      <SettingsMenu />
    </template>
    <div class="ml-1.5"><AccountMenu :compact="compact" /></div>
  </header>
</template>
