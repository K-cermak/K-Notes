import { createRouter, createWebHistory } from 'vue-router'
import type { NotesView } from '@/notes'
import { useInstanceStore } from '@/stores/instance'
import { useSessionStore } from '@/stores/session'

declare module 'vue-router' {
  interface RouteMeta {
    /** Reachable without signing in. */
    public?: boolean
    /** Only for visitors who are not signed in; signed-in users go home. */
    guestOnly?: boolean
    admin?: boolean
    /** Which list the shell shows; note routes keep the previous one behind the editor. */
    view?: NotesView
  }
}

// The shell carries Tiptap, so it loads on its own; every list route shares the one instance.
const AppShell = () => import('@/views/AppShell.vue')

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'notes', component: AppShell, meta: { view: 'notes' } },
    { path: '/archive', name: 'archive', component: AppShell, meta: { view: 'archive' } },
    { path: '/trash', name: 'trash', component: AppShell, meta: { view: 'trash' } },
    { path: '/label/:id', name: 'label', component: AppShell, meta: { view: 'label' } },
    { path: '/search', name: 'search', component: AppShell, meta: { view: 'search' } },
    { path: '/note/:id', name: 'note', component: AppShell },
    {
      path: '/setup',
      name: 'setup',
      component: () => import('@/views/auth/SetupView.vue'),
      meta: { public: true },
    },
    {
      path: '/login',
      name: 'login',
      component: () => import('@/views/auth/LoginView.vue'),
      meta: { public: true, guestOnly: true },
    },
    {
      path: '/register',
      name: 'register',
      component: () => import('@/views/auth/RegisterView.vue'),
      meta: { public: true, guestOnly: true },
    },
    {
      path: '/invite/:token',
      name: 'invite',
      component: () => import('@/views/auth/InviteView.vue'),
      meta: { public: true },
    },
    {
      path: '/reset/:token',
      name: 'reset',
      component: () => import('@/views/auth/ResetView.vue'),
      meta: { public: true },
    },
    {
      path: '/admin',
      name: 'admin',
      component: () => import('@/views/AdminView.vue'),
      meta: { admin: true },
    },
    {
      path: '/showcase',
      name: 'showcase',
      component: () => import('@/views/ShowcaseView.vue'),
      meta: { public: true },
    },
    {
      path: '/:pathMatch(.*)*',
      name: 'not-found',
      component: () => import('@/views/NotFoundView.vue'),
      meta: { public: true },
    },
  ],
})

router.beforeEach(async (to) => {
  const instance = useInstanceStore()
  const session = useSessionStore()
  if (!instance.config) await instance.load()
  // Without the server there is nothing to decide on yet; offline start arrives with the sync engine.
  if (!instance.config) return true

  if (instance.config.setup_required) {
    return to.name === 'setup' || to.name === 'showcase' ? true : { name: 'setup' }
  }
  if (!session.loaded) await session.load()
  if (to.name === 'setup') return { name: session.user ? 'home' : 'login' }
  if (to.meta.guestOnly && session.user && !session.expired) return { name: 'notes' }
  if (!to.meta.public && !session.user) {
    return { name: 'login', query: to.fullPath === '/' ? {} : { next: to.fullPath } }
  }
  if (to.meta.admin && !session.user?.is_admin) return { name: 'notes' }
  return true
})

/** Where to go after signing in: the page that sent the user to the login screen, if it is ours. */
export function afterSignIn(next: unknown): string {
  return typeof next === 'string' && next.startsWith('/') && !next.startsWith('//') ? next : '/'
}
