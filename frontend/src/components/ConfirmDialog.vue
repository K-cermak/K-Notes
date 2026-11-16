<script setup lang="ts">
import {
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogOverlay,
  AlertDialogPortal,
  AlertDialogRoot,
  AlertDialogTitle,
} from 'reka-ui'
import { useConfirmStore } from '@/stores/confirm'
import UiButton from '@/components/ui/UiButton.vue'

const confirm = useConfirmStore()
</script>

<template>
  <AlertDialogRoot
    :open="confirm.request !== null"
    @update:open="(open) => !open && confirm.answer(false)"
  >
    <AlertDialogPortal>
      <AlertDialogOverlay
        class="fixed inset-0 z-40 bg-[color-mix(in_srgb,var(--ink)_30%,transparent)]"
      />
      <AlertDialogContent
        v-if="confirm.request"
        class="fixed top-1/2 left-1/2 z-50 flex w-[calc(100%-32px)] max-w-[420px] -translate-1/2 animate-rise flex-col gap-4 border border-line bg-bg p-5 shadow-float motion-reduce:animate-fade"
      >
        <AlertDialogTitle class="text-base font-semibold tracking-[-0.01em]">
          {{ confirm.request.title }}
        </AlertDialogTitle>
        <AlertDialogDescription class="text-muted">
          {{ confirm.request.message }}
        </AlertDialogDescription>
        <!-- Plain buttons: Reka's Action and Cancel close the dialog before their click handlers run,
             which would answer every confirmation as a cancel. -->
        <div class="flex justify-end gap-3">
          <UiButton @click="confirm.answer(false)">{{ $t('common.cancel') }}</UiButton>
          <UiButton
            :variant="confirm.request.danger ? 'danger' : 'primary'"
            @click="confirm.answer(true)"
          >
            {{ confirm.request.confirmLabel }}
          </UiButton>
        </div>
      </AlertDialogContent>
    </AlertDialogPortal>
  </AlertDialogRoot>
</template>
