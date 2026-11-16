import { createI18n } from 'vue-i18n'
import en from '@/locales/en.json'

type MessageSchema = typeof en

export const i18n = createI18n<[MessageSchema], 'en'>({
  legacy: false,
  locale: 'en',
  fallbackLocale: 'en',
  messages: { en },
  datetimeFormats: {
    en: {
      time: { hour: 'numeric', minute: '2-digit' },
      date: { day: 'numeric', month: 'short', year: 'numeric' },
    },
  },
})
