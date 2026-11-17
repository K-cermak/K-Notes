import { createI18n } from 'vue-i18n'
import en from '@/locales/en.json'

type MessageSchema = typeof en

/**
 * The languages users can pick. Adding one takes a JSON file in locales/ with the same keys as
 * en.json and an entry here, under its file name, with the language's own name for itself.
 */
export const LOCALES: Record<string, string> = { en: 'English' }

const messages = Object.fromEntries(
  Object.entries(
    import.meta.glob<MessageSchema>('./locales/*.json', { eager: true, import: 'default' }),
  ).map(([path, value]) => [path.replace(/^.*\/(.+)\.json$/, '$1'), value]),
)

export const i18n = createI18n<[MessageSchema], string, false>({
  legacy: false,
  locale: 'en',
  fallbackLocale: 'en',
  messages,
  datetimeFormats: Object.fromEntries(
    Object.keys(LOCALES).map((code) => [
      code,
      {
        time: { hour: 'numeric', minute: '2-digit' },
        date: { day: 'numeric', month: 'short', year: 'numeric' },
        dateTime: {
          day: 'numeric',
          month: 'short',
          year: 'numeric',
          hour: 'numeric',
          minute: '2-digit',
        },
      },
    ]),
  ),
})

/** Switches the interface language, keeping English for a language that is not available. */
export function applyLocale(code: string | undefined): void {
  const locale = code && code in LOCALES ? code : 'en'
  i18n.global.locale.value = locale
  document.documentElement.lang = locale
}
