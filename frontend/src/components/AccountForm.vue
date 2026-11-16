<script setup lang="ts">
import { computed, ref } from 'vue'
import UiButton from '@/components/ui/UiButton.vue'
import UiField from '@/components/ui/UiField.vue'
import UiInput from '@/components/ui/UiInput.vue'
import UiNotice from '@/components/ui/UiNotice.vue'

/** The fields for a new account, shared by setup, invite acceptance and registration. */
const props = defineProps<{
  submitLabel: string
  pending: boolean
  error: string | null
  fixedEmail?: string | null
}>()

const emit = defineEmits<{ submit: [] }>()

const email = defineModel<string>('email', { required: true })
const displayName = defineModel<string>('displayName', { required: true })
const password = defineModel<string>('password', { required: true })

const attempted = ref(false)
const tooShort = computed(
  () => (attempted.value || password.value.length > 0) && password.value.length < 10,
)
const emailValue = computed(() => props.fixedEmail ?? email.value)

function submit(): void {
  attempted.value = true
  if (tooShort.value) {
    document.getElementById('account-password')?.focus()
    return
  }
  emit('submit')
}
</script>

<template>
  <form class="flex flex-col gap-5" novalidate @submit.prevent="submit">
    <UiField :label="$t('account.displayName')" for="account-name">
      <UiInput
        id="account-name"
        v-model="displayName"
        autocomplete="name"
        maxlength="100"
        required
      />
    </UiField>
    <UiField :label="$t('account.email')" for="account-email">
      <UiInput
        id="account-email"
        :model-value="emailValue"
        type="email"
        autocomplete="username"
        :disabled="!!fixedEmail"
        required
        @update:model-value="email = $event"
      />
    </UiField>
    <UiField
      :label="$t('account.password')"
      for="account-password"
      :hint="$t('account.passwordHint')"
      :error="tooShort ? $t('errors.password_too_short') : undefined"
    >
      <UiInput
        id="account-password"
        v-model="password"
        type="password"
        autocomplete="new-password"
        :invalid="tooShort"
        required
      />
    </UiField>
    <UiNotice v-if="error" tone="error">{{ error }}</UiNotice>
    <UiButton type="submit" variant="primary" :loading="pending">{{ submitLabel }}</UiButton>
  </form>
</template>
