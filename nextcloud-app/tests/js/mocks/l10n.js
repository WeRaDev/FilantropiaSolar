/**
 * Mock for @nextcloud/l10n
 */

export function translate(app, text, vars = {}) {
    let result = text
    for (const [key, value] of Object.entries(vars)) {
        result = result.replace(`{${key}}`, String(value))
    }
    return result
}

export function translatePlural(app, singular, plural, count, vars = {}) {
    const text = count === 1 ? singular : plural
    return translate(app, text, { ...vars, count })
}

export const t = translate
export const n = translatePlural

export function getLanguage() {
    return 'en'
}

export function getLocale() {
    return 'en_US'
}
