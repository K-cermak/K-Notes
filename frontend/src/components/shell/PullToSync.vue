<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { PULL_THRESHOLD, usePullToSync } from '@/composables/usePullToSync'
import { useSnackbarStore } from '@/stores/snackbar'
import { useSyncStore } from '@/stores/sync'

// Pull the list down to sync (SPEC 9, Pull to sync). The spinner slides out from under the top bar.
const props = defineProps<{ disabled: boolean }>()

const { t } = useI18n()
const sync = useSyncStore()
const snackbar = useSnackbarStore()

async function run(): Promise<void> {
  const state = await sync.syncAndWait()
  if (state === 'offline' || state === 'error' || state === 'unauthorized') {
    snackbar.show(t(`sync.pullFailed.${state}`))
  }
}

// Not while a card is dragged (useNoteDrag marks the page) or a menu, popover or dialog is open:
// Reka keeps those in the page only while they are open.
function allowed(): boolean {
  if (props.disabled || 'dragging' in document.documentElement.dataset) return false
  return !document.querySelector('[role="dialog"], [role="alertdialog"], [role="menu"]')
}
const { distance, phase } = usePullToSync(allowed, run)
const armed = computed(() => distance.value >= PULL_THRESHOLD)
// The box starts hidden under the top bar, its height plus its shadow above where it shows.
const HIDDEN = -48
</script>

<template>
  <div
    v-if="phase !== 'idle'"
    class="pointer-events-none fixed inset-x-0 top-16 z-10 flex justify-center"
    aria-hidden="true"
    data-testid="pull-to-sync"
    :data-phase="phase"
  >
    <div
      class="grid size-10 place-items-center border border-line bg-bg shadow-float"
      :class="[
        armed || phase === 'syncing' ? 'text-ink' : 'text-muted',
        phase !== 'pulling' &&
          'transition-[translate,opacity] duration-(--motion) ease-out motion-reduce:transition-opacity',
      ]"
      :style="{
        translate: `0 ${HIDDEN + distance}px`,
        opacity: phase === 'syncing' ? 1 : Math.min(1, distance / 40),
      }"
    >
      <!-- While pulled, the arc turns with the finger instead of spinning on its own. -->
      <span
        class="ui-spinner"
        :style="
          phase === 'pulling' ? { animation: 'none', rotate: `${distance * 4}deg` } : undefined
        "
      />
    </div>
  </div>
</template>
