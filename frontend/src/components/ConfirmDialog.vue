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
      <AlertDialogOverlay class="ui-overlay" />
      <AlertDialogContent v-if="confirm.request" class="ui-dialog">
        <AlertDialogTitle class="ui-dialog__title">
          {{ confirm.request.title }}
        </AlertDialogTitle>
        <AlertDialogDescription class="text-muted">
          {{ confirm.request.message }}
        </AlertDialogDescription>
        <!-- Plain buttons: Reka's Action and Cancel close the dialog before their click handlers run,
             which would answer every confirmation as a cancel. -->
        <div class="ui-dialog__actions">
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
