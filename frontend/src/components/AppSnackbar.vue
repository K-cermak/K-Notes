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
    <!-- Transitions rather than keyframes: a new message can replace one that is still arriving.
         It leaves the way it came, a little faster. -->
    <Transition
      enter-from-class="opacity-0 translate-y-2 motion-reduce:translate-y-0"
      leave-to-class="opacity-0 translate-y-2 motion-reduce:translate-y-0"
      enter-active-class="transition-[opacity,translate] duration-240 ease-out"
      leave-active-class="transition-[opacity,translate] duration-150 ease-out"
    >
      <div
        v-if="snackbar.current"
        :key="snackbar.current.id"
        role="status"
        class="ui-snackbar pointer-events-auto w-full max-w-[480px] sm:w-auto sm:min-w-[320px]"
        data-testid="snackbar"
      >
        <span class="flex-1">{{ snackbar.current.text }}</span>
        <button
          v-if="snackbar.current.action"
          type="button"
          class="ui-snackbar__action"
          @click="snackbar.act()"
        >
          {{ snackbar.current.action.label }}
        </button>
        <button
          type="button"
          class="ui-icon-button"
          :aria-label="$t('common.close')"
          @click="snackbar.close()"
        >
          <X :size="16" />
        </button>
      </div>
    </Transition>
  </div>
</template>
