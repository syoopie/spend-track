/**
 * Client-side mirror of the active country's display-facing constants -
 * kept here (not fetched) because currency/contact-hint formatting is
 * needed synchronously during render, before any API round-trip could
 * resolve. Must stay in sync with backend/src/app/localization.py's
 * SINGAPORE profile; GET /api/settings reports the same values from that
 * single backend source of truth for anything that legitimately needs a
 * live check (see Settings.tsx's Region card).
 */
export const CURRENCY_SYMBOL = '$'
export const CONTACT_IDENTIFIER_HINT = '+65 9xxx xxxx, UEN, or account no.'
