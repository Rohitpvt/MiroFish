import { createI18n } from 'vue-i18n'
import languages from '../../../locales/languages.json'

const localeFiles = import.meta.glob('../../../locales/!(languages).json', { eager: true })

const messages = {}
const availableLocales = []

// Order availableLocales according to languages.json
for (const key of Object.keys(languages)) {
  for (const path in localeFiles) {
    const fileKey = path.match(/\/([^/]+)\.json$/)[1]
    if (fileKey === key) {
      messages[key] = localeFiles[path].default
      availableLocales.push({ key, label: languages[key].label })
      break
    }
  }
}

// Fallback for any locale file not in languages.json
for (const path in localeFiles) {
  const key = path.match(/\/([^/]+)\.json$/)[1]
  if (!messages[key]) {
    messages[key] = localeFiles[path].default
  }
}

// Default to English ('en') unless user has explicitly chosen another language
const userExplicitlySelected = localStorage.getItem('locale_user_selected') === 'true'
let savedLocale = localStorage.getItem('locale')

if (!savedLocale || !userExplicitlySelected) {
  savedLocale = 'en'
}

const i18n = createI18n({
  legacy: false,
  locale: savedLocale,
  fallbackLocale: 'en',
  messages
})

export { availableLocales }
export default i18n
