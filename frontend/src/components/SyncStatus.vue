<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { PopoverContent, PopoverPortal, PopoverRoot, PopoverTrigger } from 'reka-ui'
import { Cloud, CloudAlert, CloudOff, RefreshCw } from '@lucide/vue'
import CloudSynced from '@/components/icons/CloudSynced.vue'
import { floatingPanel } from '@/components/ui/menu'
import { useSyncStore } from '@/stores/sync'

const sync = useSyncStore()
const { t, d } = useI18n()

const icon = computed(
  () =>
    ({
      idle: Cloud,
      synced: CloudSynced,
      syncing: RefreshCw,
      offline: CloudOff,
      error: CloudAlert,
      unauthorized: CloudAlert,
    })[sync.state],
)

const lastSynced = computed(() => {
  const at = sync.lastSynced
  if (at === null) return t('sync.never')
  const sameDay = new Date(at).toDateString() === new Date().toDateString()
  return d(new Date(at), sameDay ? 'time' : 'dateTime')
})

// The state and the unsent count, as the visible icon and number say them.
const label = computed(() =>
  [
    t(`sync.${sync.state}`),
    sync.unsent > 0 ? t('sync.unsent', { count: sync.unsent }, sync.unsent) : '',
  ]
    .filter(Boolean)
    .join(', '),
)

const canSync = computed(() => sync.state !== 'syncing' && sync.state !== 'unauthorized')
</script>

<template>
  <!-- The wrapper carries the sync state: Reka writes its own data-state (open, closed) on the trigger. -->
  <div class="flex shrink-0" data-testid="sync-status" :data-state="sync.state">
    <PopoverRoot>
      <PopoverTrigger
        class="flex h-9 cursor-pointer items-center gap-1.5 px-1.5 text-muted transition-colors duration-150 hover:text-ink data-[state=open]:text-ink"
        :aria-label="label"
        :title="$t(`sync.${sync.state}`)"
      >
        <!-- A little larger than the toolbar icons beside it: the cloud is wide and flat, and at 18 px
           the check inside it is too small to read. -->
        <component
          :is="icon"
          :size="20"
          :class="[
            sync.state === 'error' && 'text-danger',
            sync.state === 'syncing' &&
              'animate-spin [animation-duration:1.5s] motion-reduce:animate-none',
          ]"
          aria-hidden="true"
        />
        <span v-if="sync.unsent > 0" class="ui-meta" data-testid="unsent" aria-hidden="true">
          {{ sync.unsent }}
        </span>
      </PopoverTrigger>
      <PopoverPortal>
        <PopoverContent
          :class="[floatingPanel, 'flex w-[280px] flex-col gap-3 p-4']"
          side="bottom"
          align="end"
          :side-offset="6"
          :collision-padding="8"
          data-testid="sync-details"
        >
          <div>
            <p class="font-semibold">{{ $t(`sync.${sync.state}`) }}</p>
            <p class="text-label text-muted">{{ $t(`sync.about.${sync.state}`) }}</p>
          </div>
          <dl class="flex flex-col gap-1 border-t border-line pt-3 text-label">
            <div class="flex justify-between gap-4">
              <dt class="text-muted">{{ $t('sync.unsentLabel') }}</dt>
              <dd class="tabular-nums" data-testid="sync-details-unsent">{{ sync.unsent }}</dd>
            </div>
            <div v-if="sync.rejected > 0" class="flex justify-between gap-4">
              <dt class="text-muted">{{ $t('sync.rejectedLabel') }}</dt>
              <dd class="text-danger tabular-nums">{{ sync.rejected }}</dd>
            </div>
            <div class="flex justify-between gap-4">
              <dt class="text-muted">{{ $t('sync.lastSynced') }}</dt>
              <dd class="tabular-nums" data-testid="sync-details-last">{{ lastSynced }}</dd>
            </div>
          </dl>
          <RouterLink
            v-if="sync.state === 'unauthorized'"
            to="/login"
            class="ui-button ui-button--sm ui-button--primary self-end"
          >
            {{ $t('login.submit') }}
          </RouterLink>
          <button
            v-else
            type="button"
            class="ui-button ui-button--sm self-end"
            :disabled="!canSync"
            data-testid="sync-now"
            @click="sync.syncNow()"
          >
            {{ $t('sync.now') }}
          </button>
        </PopoverContent>
      </PopoverPortal>
    </PopoverRoot>
  </div>
</template>
