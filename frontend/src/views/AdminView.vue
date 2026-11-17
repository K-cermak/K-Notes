<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import {
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuPortal,
  DropdownMenuRoot,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from 'reka-ui'
import { ArrowLeft, Check, Copy, EllipsisVertical, X } from '@lucide/vue'
import { api, call, type AdminUser, type CreatedLink, type PendingInvite } from '@/api/client'
import type { components } from '@/api/schema'
import { useSubmit } from '@/composables/useSubmit'
import { useConfirmStore } from '@/stores/confirm'
import { useSessionStore } from '@/stores/session'
import { iconButton, menuItem, menuPanel } from '@/components/ui/menu'
import UiButton from '@/components/ui/UiButton.vue'
import UiCheckbox from '@/components/ui/UiCheckbox.vue'
import UiField from '@/components/ui/UiField.vue'
import UiInput from '@/components/ui/UiInput.vue'
import UiNotice from '@/components/ui/UiNotice.vue'

const i18n = useI18n()
const session = useSessionStore()
const confirm = useConfirmStore()
const users = ref<AdminUser[]>([])
const status = ref<components['schemas']['InstanceStatus'] | null>(null)
const resetLink = ref<{ user: AdminUser; link: CreatedLink } | null>(null)
const userAction = useSubmit()
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
    const [u, i, s, st] = await Promise.all([
      call(() => api.GET('/api/v1/admin/users')),
      call(() => api.GET('/api/v1/admin/invites')),
      call(() => api.GET('/api/v1/admin/settings')),
      call(() => api.GET('/api/v1/admin/status')),
    ])
    users.value = u
    invites.value = i
    registration.value = s.registration_enabled
    status.value = st
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

// The server enforces both guards (SPEC 7); the menu only reflects them.
const activeAdmins = computed(() => users.value.filter((u) => u.is_admin && u.is_active).length)
function isSelf(user: AdminUser): boolean {
  return user.id === session.user?.id
}
function lastAdmin(user: AdminUser): boolean {
  return user.is_admin && user.is_active && activeAdmins.value <= 1
}

async function updateUser(user: AdminUser, body: { is_admin?: boolean; is_active?: boolean }) {
  await userAction.run(async () => {
    await call(() =>
      api.PATCH('/api/v1/admin/users/{user_id}', { params: { path: { user_id: user.id } }, body }),
    )
    users.value = await call(() => api.GET('/api/v1/admin/users'))
  })
}

async function createResetLink(user: AdminUser): Promise<void> {
  copied.value = false
  await userAction.run(async () => {
    const created = await call(() =>
      api.POST('/api/v1/admin/users/{user_id}/reset-link', {
        params: { path: { user_id: user.id } },
      }),
    )
    resetLink.value = { user, link: created }
  })
}

async function resetTotp(user: AdminUser): Promise<void> {
  const sure = await confirm.ask({
    title: i18n.t('admin.users.resetTotpTitle', { name: user.display_name }),
    message: i18n.t('admin.users.resetTotpMessage'),
    confirmLabel: i18n.t('admin.users.resetTotp'),
  })
  if (!sure) return
  await userAction.run(async () => {
    await call(() =>
      api.DELETE('/api/v1/admin/users/{user_id}/totp', { params: { path: { user_id: user.id } } }),
    )
    users.value = await call(() => api.GET('/api/v1/admin/users'))
  })
}

async function deleteUser(user: AdminUser): Promise<void> {
  const sure = await confirm.ask({
    title: i18n.t('admin.users.deleteTitle', { name: user.display_name }),
    message: i18n.t('admin.users.deleteMessage'),
    confirmLabel: i18n.t('admin.users.delete'),
    danger: true,
  })
  if (!sure) return
  await userAction.run(async () => {
    await call(() =>
      api.DELETE('/api/v1/admin/users/{user_id}', { params: { path: { user_id: user.id } } }),
    )
    users.value = users.value.filter((u) => u.id !== user.id)
  })
}

async function copyResetLink(): Promise<void> {
  if (!resetLink.value) return
  await navigator.clipboard.writeText(resetLink.value.link.url)
  copied.value = true
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
          <span v-if="user.totp_enabled" class="border border-line px-1.5 text-meta text-muted">
            2FA
          </span>
          <DropdownMenuRoot :modal="false">
            <DropdownMenuTrigger
              :class="iconButton"
              :aria-label="$t('admin.users.actions', { name: user.display_name })"
              data-testid="user-actions"
            >
              <EllipsisVertical :size="18" />
            </DropdownMenuTrigger>
            <DropdownMenuPortal>
              <DropdownMenuContent :class="menuPanel" align="end" :side-offset="4">
                <DropdownMenuItem
                  :class="menuItem"
                  :disabled="!user.is_active"
                  @select="createResetLink(user)"
                >
                  {{ $t('admin.users.resetLink') }}
                </DropdownMenuItem>
                <DropdownMenuItem
                  v-if="user.totp_enabled"
                  :class="menuItem"
                  @select="resetTotp(user)"
                >
                  {{ $t('admin.users.resetTotp') }}
                </DropdownMenuItem>
                <DropdownMenuSeparator class="my-1 h-px bg-line" />
                <DropdownMenuItem
                  :class="menuItem"
                  :disabled="user.is_admin && (isSelf(user) || lastAdmin(user))"
                  @select="updateUser(user, { is_admin: !user.is_admin })"
                >
                  {{ $t(user.is_admin ? 'admin.users.revokeAdmin' : 'admin.users.makeAdmin') }}
                </DropdownMenuItem>
                <DropdownMenuItem
                  :class="menuItem"
                  :disabled="user.is_active && (isSelf(user) || lastAdmin(user))"
                  @select="updateUser(user, { is_active: !user.is_active })"
                >
                  {{ $t(user.is_active ? 'admin.users.deactivate' : 'admin.users.reactivate') }}
                </DropdownMenuItem>
                <DropdownMenuItem
                  :class="[menuItem, 'text-danger']"
                  :disabled="isSelf(user) || lastAdmin(user)"
                  @select="deleteUser(user)"
                >
                  {{ $t('admin.users.delete') }}
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenuPortal>
          </DropdownMenuRoot>
        </li>
      </ul>
      <UiNotice v-if="userAction.error.value" tone="error">{{ userAction.error.value }}</UiNotice>
      <div v-if="resetLink" class="flex flex-col gap-2" data-testid="reset-link">
        <p class="text-muted">
          {{ $t('admin.users.resetLinkFor', { name: resetLink.user.display_name }) }}
        </p>
        <div class="flex gap-2">
          <UiInput :model-value="resetLink.link.url" readonly class="font-mono text-meta" />
          <UiButton :aria-label="$t('admin.invite.copy')" icon-only @click="copyResetLink">
            <Check v-if="copied" class="text-success" />
            <Copy v-else />
          </UiButton>
        </div>
        <p class="text-meta text-faint">
          {{ $t('admin.users.resetOnce', { date: formatDate(resetLink.link.expires_at) }) }}
        </p>
      </div>
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

    <section v-if="status" class="flex flex-col gap-3" data-testid="instance-status">
      <h2 class="text-base">{{ $t('admin.status.title') }}</h2>
      <dl class="grid grid-cols-[auto_1fr] gap-x-6 gap-y-1.5">
        <dt class="text-muted">{{ $t('admin.status.version') }}</dt>
        <dd class="font-mono tabular-nums">{{ status.version }}</dd>
        <dt class="text-muted">{{ $t('admin.status.users') }}</dt>
        <dd class="font-mono tabular-nums">{{ status.user_count }}</dd>
        <dt class="text-muted">{{ $t('admin.status.oidc') }}</dt>
        <dd>{{ $t(status.oidc_enabled ? 'admin.status.yes' : 'admin.status.no') }}</dd>
        <dt class="text-muted">{{ $t('admin.status.passwordLogin') }}</dt>
        <dd>{{ $t(status.password_login_enabled ? 'admin.status.yes' : 'admin.status.no') }}</dd>
      </dl>
    </section>
  </main>
</template>
