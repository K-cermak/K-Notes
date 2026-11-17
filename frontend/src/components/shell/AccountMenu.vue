<script setup lang="ts">
import { useRouter } from 'vue-router'
import {
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuItemIndicator,
  DropdownMenuLabel,
  DropdownMenuPortal,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuRoot,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from 'reka-ui'
import { Check, LayoutGrid, LogOut, Rows3, Settings, Shield } from '@lucide/vue'
import { themes } from '@/theme'
import { useSubmit } from '@/composables/useSubmit'
import { useSessionStore } from '@/stores/session'
import { useSnackbarStore } from '@/stores/snackbar'
import { menuItem, menuPanel } from '@/components/ui/menu'

// On phones the view toggle and theme move in here from the top bar (SPEC 9, Layout).
defineProps<{ compact: boolean }>()

const router = useRouter()
const session = useSessionStore()
const snackbar = useSnackbarStore()
const signOut = useSubmit()

async function logout(): Promise<void> {
  const done = await signOut.attempt(() => session.logout())
  if (done) await router.replace('/login')
  else if (signOut.error.value) snackbar.show(signOut.error.value)
}
</script>

<template>
  <DropdownMenuRoot :modal="false">
    <DropdownMenuTrigger
      class="grid size-9 cursor-pointer place-items-center border border-line bg-[color-mix(in_srgb,var(--ink)_6%,var(--bg))] font-medium text-ink hover:border-line-hover pointer-coarse:size-11"
      :aria-label="$t('account.menu')"
      data-testid="account-menu"
    >
      {{ session.user?.display_name.charAt(0).toUpperCase() }}
    </DropdownMenuTrigger>
    <DropdownMenuPortal>
      <DropdownMenuContent :class="[menuPanel, 'min-w-[260px]']" align="end" :side-offset="6">
        <DropdownMenuLabel class="flex flex-col px-3 py-2">
          <span class="font-medium" data-testid="signed-in-as">{{
            session.user?.display_name
          }}</span>
          <span class="text-label text-muted">{{ session.user?.email }}</span>
        </DropdownMenuLabel>
        <DropdownMenuSeparator class="ui-menu-separator" />
        <template v-if="compact">
          <DropdownMenuItem
            :class="menuItem"
            @select="
              session.updateProfile({
                default_view: session.user?.default_view === 'list' ? 'grid' : 'list',
              })
            "
          >
            <LayoutGrid v-if="session.user?.default_view === 'list'" :size="16" />
            <Rows3 v-else :size="16" />
            {{ $t(session.user?.default_view === 'list' ? 'topbar.gridView' : 'topbar.listView') }}
          </DropdownMenuItem>
          <DropdownMenuLabel class="ui-menu-label">{{ $t('theme.label') }}</DropdownMenuLabel>
          <DropdownMenuRadioGroup
            :model-value="session.user?.theme"
            @update:model-value="
              (value) => session.updateProfile({ theme: value as (typeof themes)[number] })
            "
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
        </template>
        <DropdownMenuItem :class="menuItem" @select="router.push('/settings')">
          <Settings :size="16" /> {{ $t('settings.title') }}
        </DropdownMenuItem>
        <DropdownMenuItem
          v-if="session.user?.is_admin"
          :class="menuItem"
          @select="router.push('/admin')"
        >
          <Shield :size="16" /> {{ $t('admin.title') }}
        </DropdownMenuItem>
        <DropdownMenuItem :class="menuItem" @select="logout">
          <LogOut :size="16" /> {{ $t('home.signOut') }}
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenuPortal>
  </DropdownMenuRoot>
</template>
