<script setup lang="ts">
import {
  AlertDialogAction,
  AlertDialogCancel,
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
        <div class="flex justify-end gap-3">
          <AlertDialogCancel as-child>
            <UiButton>{{ $t('common.cancel') }}</UiButton>
          </AlertDialogCancel>
          <AlertDialogAction as-child>
            <UiButton
              :variant="confirm.request.danger ? 'danger' : 'primary'"
              @click="confirm.answer(true)"
            >
              {{ confirm.request.confirmLabel }}
            </UiButton>
          </AlertDialogAction>
        </div>
      </AlertDialogContent>
    </AlertDialogPortal>
  </AlertDialogRoot>
</template>
