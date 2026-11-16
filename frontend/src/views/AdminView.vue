<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ArrowLeft, Check, Copy, X } from '@lucide/vue'
import { api, call, type AdminUser, type CreatedLink, type PendingInvite } from '@/api/client'
import { useSubmit } from '@/composables/useSubmit'
import UiButton from '@/components/ui/UiButton.vue'
import UiCheckbox from '@/components/ui/UiCheckbox.vue'
import UiField from '@/components/ui/UiField.vue'
import UiInput from '@/components/ui/UiInput.vue'
import UiNotice from '@/components/ui/UiNotice.vue'

// A minimal admin page for phase 1: enough to invite people. The full screen arrives in phase 10.
const users = ref<AdminUser[]>([])
const invites = ref<PendingInvite[]>([])
const registration = ref(false)
const inviteEmail = ref('')
const link = ref<CreatedLink | null>(null)
const copied = ref(false)
const load = useSubmit()
const create = useSubmit()
const toggle = useSubmit()

async function refresh(): Promise<void> {
  await load.run(async () => {
    const [u, i, s] = await Promise.all([
      call(() => api.GET('/api/v1/admin/users')),
      call(() => api.GET('/api/v1/admin/invites')),
      call(() => api.GET('/api/v1/admin/settings')),
    ])
    users.value = u
    invites.value = i
    registration.value = s.registration_enabled
  })
}

async function createInvite(): Promise<void> {
  copied.value = false
  await create.run(async () => {
    link.value = await call(() =>
      api.POST('/api/v1/admin/invites', { body: { email: inviteEmail.value.trim() || null } }),
    )
    inviteEmail.value = ''
    invites.value = await call(() => api.GET('/api/v1/admin/invites'))
  })
}

async function copyLink(): Promise<void> {
  if (!link.value) return
  try {
    await navigator.clipboard.writeText(link.value.url)
    copied.value = true
  } catch {
    document.querySelector<HTMLInputElement>('#invite-link')?.select()
  }
}

async function revoke(invite: PendingInvite): Promise<void> {
  await load.run(async () => {
    await call(() =>
      api.DELETE('/api/v1/admin/invites/{invite_id}', {
        params: { path: { invite_id: invite.id } },
      }),
    )
    invites.value = invites.value.filter((i) => i.id !== invite.id)
  })
}

async function setRegistration(value: boolean): Promise<void> {
  await toggle.run(async () => {
    const result = await call(() =>
      api.PATCH('/api/v1/admin/settings', { body: { registration_enabled: value } }),
    )
    registration.value = result.registration_enabled
  })
}

function formatDate(ms: number): string {
  return new Date(ms).toLocaleString()
}

onMounted(refresh)
</script>

<template>
  <main class="mx-auto flex w-full max-w-[600px] flex-col gap-10 px-4 py-6 sm:py-10">
    <header class="flex items-center gap-3">
      <RouterLink
        to="/"
        class="grid size-8 place-items-center text-muted hover:text-ink"
        :aria-label="$t('common.back')"
      >
        <ArrowLeft />
      </RouterLink>
      <h1 class="text-xl leading-tight">{{ $t('admin.title') }}</h1>
    </header>

    <UiNotice v-if="load.error.value" tone="error">{{ load.error.value }}</UiNotice>

    <section class="flex flex-col gap-4">
      <h2 class="text-base">{{ $t('admin.invite.title') }}</h2>
      <p class="text-muted">{{ $t('admin.invite.description') }}</p>
      <form class="flex flex-col gap-3 sm:flex-row sm:items-end" @submit.prevent="createInvite">
        <UiField :label="$t('admin.invite.email')" for="invite-email" class="flex-1">
          <UiInput id="invite-email" v-model="inviteEmail" type="email" autocomplete="off" />
        </UiField>
        <UiButton type="submit" variant="primary" :loading="create.pending.value">
          {{ $t('admin.invite.create') }}
        </UiButton>
      </form>
      <UiNotice v-if="create.error.value" tone="error">{{ create.error.value }}</UiNotice>
      <div v-if="link" class="flex flex-col gap-2">
        <div class="flex gap-2">
          <UiInput id="invite-link" :model-value="link.url" readonly class="font-mono text-meta" />
          <UiButton :aria-label="$t('admin.invite.copy')" icon-only @click="copyLink">
            <Check v-if="copied" class="text-success" />
            <Copy v-else />
          </UiButton>
        </div>
        <p class="text-meta text-faint">
          {{ $t('admin.invite.once', { date: formatDate(link.expires_at) }) }}
        </p>
      </div>
      <ul v-if="invites.length" class="border border-line">
        <li
          v-for="invite in invites"
          :key="invite.id"
          class="flex items-center gap-3 px-3 py-2 not-first:border-t not-first:border-line"
        >
          <span class="min-w-0 flex-1 truncate">{{
            invite.email ?? $t('admin.invite.anyone')
          }}</span>
          <span class="font-mono text-meta text-faint tabular-nums">
            {{ $t('admin.invite.expires', { date: formatDate(invite.expires_at) }) }}
          </span>
          <UiButton
            variant="ghost"
            size="sm"
            icon-only
            :aria-label="$t('admin.invite.revoke')"
            @click="revoke(invite)"
          >
            <X :size="16" />
          </UiButton>
        </li>
      </ul>
    </section>

    <section class="flex flex-col gap-4">
      <h2 class="text-base">{{ $t('admin.users.title') }}</h2>
      <ul class="border border-line">
        <li
          v-for="user in users"
          :key="user.id"
          class="flex items-center gap-3 px-3 py-2.5 not-first:border-t not-first:border-line"
        >
          <div class="flex min-w-0 flex-1 flex-col">
            <span class="truncate font-medium">{{ user.display_name }}</span>
            <span class="truncate text-label text-muted">{{ user.email }}</span>
          </div>
          <span v-if="user.is_admin" class="border border-line px-1.5 text-meta text-muted">
            {{ $t('admin.users.admin') }}
          </span>
          <span v-if="!user.is_active" class="border border-danger px-1.5 text-meta text-danger">
            {{ $t('admin.users.inactive') }}
          </span>
        </li>
      </ul>
    </section>

    <section class="flex flex-col gap-3">
      <h2 class="text-base">{{ $t('admin.registration.title') }}</h2>
      <label class="flex cursor-pointer items-start gap-3">
        <UiCheckbox
          :model-value="registration"
          :disabled="toggle.pending.value"
          class="mt-0.5"
          @update:model-value="setRegistration($event === true)"
        />
        <span class="flex flex-col">
          <span>{{ $t('admin.registration.label') }}</span>
          <span class="text-label text-muted">{{ $t('admin.registration.hint') }}</span>
        </span>
      </label>
      <UiNotice v-if="toggle.error.value" tone="error">{{ toggle.error.value }}</UiNotice>
    </section>
  </main>
</template>
