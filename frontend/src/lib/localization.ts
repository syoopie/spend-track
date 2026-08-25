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
// No phone number example here on purpose - real UOB PayNow lines almost
// never carry the payer's actual phone number in the raw description (see
// lib/paynowIdentifier.ts's docstring), so hinting one was actively
// misleading about what usually ends up in this field (a UEN, an account
// number, or - now the common case - the payee name itself, since
// ReviewDialog.tsx's "Save as Contact" falls back to that when no
// phone/UEN is found).
export const CONTACT_IDENTIFIER_HINT = 'UEN, account no., or payee name'
