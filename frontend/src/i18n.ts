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

export type TimeFormat = '24h' | '12h'

// The user's choice rather than the language's convention, so 24-hour time also in English.
function dateTimeFormats(format: TimeFormat) {
  const hourCycle = format === '12h' ? 'h12' : 'h23'
  return {
    time: { hour: 'numeric', minute: '2-digit', hourCycle },
    date: { day: 'numeric', month: 'short', year: 'numeric' },
    dateTime: {
      day: 'numeric',
      month: 'short',
      year: 'numeric',
      hour: 'numeric',
      minute: '2-digit',
      hourCycle,
    },
  } as const
}

export const i18n = createI18n<[MessageSchema], string, false>({
  legacy: false,
  locale: 'en',
  fallbackLocale: 'en',
  messages,
  datetimeFormats: Object.fromEntries(
    Object.keys(LOCALES).map((code) => [code, dateTimeFormats('24h')]),
  ),
})

/** Shows times on a 24-hour or 12-hour clock, whatever the language. */
export function applyTimeFormat(format: TimeFormat | undefined): void {
  for (const code of Object.keys(LOCALES)) {
    i18n.global.setDateTimeFormat(code, dateTimeFormats(format === '12h' ? '12h' : '24h'))
  }
}

/** Switches the interface language, keeping English for a language that is not available. */
export function applyLocale(code: string | undefined): void {
  const locale = code && code in LOCALES ? code : 'en'
  i18n.global.locale.value = locale
  document.documentElement.lang = locale
}
