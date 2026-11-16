// Adding a language: add a JSON file next to en.json and one entry here.
export const locales = [{ code: 'en', name: 'English' }] as const

export type LocaleCode = (typeof locales)[number]['code']
