<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { LogOut, Plus } from '@lucide/vue'
import branding from '@branding'
import { createNote, byPosition } from '@/db/notes'
import { fromPlainText } from '@/db/richtext'
import { db } from '@/db/schema'
import { useLiveQuery } from '@/composables/useLiveQuery'
import { useSubmit } from '@/composables/useSubmit'
import { useSessionStore } from '@/stores/session'
import { useSyncStore } from '@/stores/sync'
import PlainNote from '@/components/PlainNote.vue'
import SyncStatus from '@/components/SyncStatus.vue'
import UiButton from '@/components/ui/UiButton.vue'
import UiNotice from '@/components/ui/UiNotice.vue'

// Deliberately plain: it exists to exercise sync and is replaced by the real interface in phase 4.
const router = useRouter()
const session = useSessionStore()
const sync = useSyncStore()
const signOut = useSubmit()

const notes = useLiveQuery(async () => (await db.notes.toArray()).sort(byPosition), [])
const newTitle = ref('')
const newText = ref('')

async function add(): Promise<void> {
  if (!newTitle.value && !newText.value) return
  await createNote({ title: newTitle.value, content: fromPlainText(newText.value) })
  newTitle.value = ''
  newText.value = ''
}

async function logout(): Promise<void> {
  const done = await signOut.attempt(() => session.logout())
  if (done) await router.replace('/login')
}
</script>

<template>
  <main class="mx-auto flex w-full max-w-[600px] flex-col gap-6 px-4 py-6">
    <header class="flex flex-wrap items-center justify-between gap-3">
      <div class="flex flex-col">
        <h1 class="text-xl leading-tight">{{ branding.name }}</h1>
        <p v-if="session.user" class="text-label text-muted" data-testid="signed-in-as">
          {{
            $t('home.signedInAs', { name: session.user.display_name, email: session.user.email })
          }}
        </p>
      </div>
      <div class="flex items-center gap-3">
        <SyncStatus />
        <RouterLink
          v-if="session.user?.is_admin"
          to="/admin"
          class="text-label font-medium text-accent"
        >
          {{ $t('admin.title') }}
        </RouterLink>
        <UiButton size="sm" :loading="signOut.pending.value" @click="logout">
          <LogOut :size="16" />
          {{ $t('home.signOut') }}
        </UiButton>
      </div>
    </header>

    <UiNotice v-if="session.expired" tone="warning">
      {{ $t('sync.signInAgain') }}
      <RouterLink to="/login" class="font-medium text-accent">{{ $t('login.submit') }}</RouterLink>
    </UiNotice>
    <UiNotice v-if="sync.rejected > 0" tone="error">
      {{ $t('sync.rejected', { count: sync.rejected }, sync.rejected) }}
    </UiNotice>
    <UiNotice v-if="signOut.error.value" tone="error">{{ signOut.error.value }}</UiNotice>

    <form class="flex flex-col gap-2 border border-line p-3" @submit.prevent="add">
      <input
        v-model="newTitle"
        class="w-full bg-transparent font-semibold outline-none placeholder:text-faint"
        :placeholder="$t('plain.title')"
        :aria-label="$t('plain.newTitle')"
        data-testid="new-title"
      />
      <textarea
        v-model="newText"
        rows="2"
        class="field-sizing-content w-full resize-none bg-transparent outline-none placeholder:text-faint"
        :placeholder="$t('plain.text')"
        :aria-label="$t('plain.newText')"
        data-testid="new-text"
      />
      <UiButton type="submit" variant="primary" size="sm" class="self-end" data-testid="add">
        <Plus :size="16" />
        {{ $t('plain.add') }}
      </UiButton>
    </form>

    <ul class="flex flex-col gap-3" data-testid="notes">
      <PlainNote v-for="note in notes" :key="note.id" :note="note" />
    </ul>
    <p v-if="notes.length === 0" class="text-center text-muted">{{ $t('plain.empty') }}</p>
  </main>
</template>
