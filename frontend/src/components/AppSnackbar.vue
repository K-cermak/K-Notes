<script setup lang="ts">
import { X } from '@lucide/vue'
import { useSnackbarStore } from '@/stores/snackbar'

const snackbar = useSnackbarStore()
</script>

<template>
  <div
    class="pointer-events-none fixed inset-x-4 bottom-[max(16px,env(safe-area-inset-bottom))] z-50 flex sm:right-auto sm:left-6"
    aria-live="polite"
  >
    <Transition
      enter-from-class="opacity-0 translate-y-1.5"
      leave-to-class="opacity-0"
      enter-active-class="transition duration-150 ease-out"
      leave-active-class="transition duration-150"
    >
      <div
        v-if="snackbar.message"
        :key="snackbar.message.id"
        role="status"
        class="pointer-events-auto flex min-h-12 w-full max-w-[480px] items-center gap-3 border border-line bg-bg py-1.5 pr-1.5 pl-4 shadow-float sm:w-auto sm:min-w-[320px]"
        data-testid="snackbar"
      >
        <span class="flex-1">{{ snackbar.message.text }}</span>
        <button
          v-if="snackbar.message.action"
          type="button"
          class="h-9 cursor-pointer px-3 font-medium text-accent hover:bg-[color-mix(in_srgb,var(--ink)_5%,var(--bg))]"
          @click="snackbar.act()"
        >
          {{ snackbar.message.action.label }}
        </button>
        <button
          type="button"
          class="grid size-9 cursor-pointer place-items-center text-muted hover:text-ink"
          :aria-label="$t('common.close')"
          @click="snackbar.dismiss()"
        >
          <X :size="16" />
        </button>
      </div>
    </Transition>
  </div>
</template>
