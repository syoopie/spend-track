// Best-effort extraction of a phone-number- or UEN-shaped substring from a
// PayNow transaction's raw bank description, for pre-filling the "Save as
// Contact" dialog's identifier field (ReviewDialog.tsx). Real UOB PayNow
// lines usually only carry the resolved payee NAME - see
// backend/src/app/engine/naming.py's docstring example
// ("PAYNOW-FAST PIB2605050213183371 BOON HENG PTE. LTD. OTHR
// QL0TbuzeBASv00000002Sj"), which has no phone number in it at all - so this
// often comes back empty. This function itself never guesses a name - it
// only ever returns a genuine phone/UEN-shaped match, or ''. The empty case
// is common enough in practice that the caller falls back to the payee name
// on its own when this returns '' (see ReviewDialog.tsx's use of this
// function) rather than leaving the identifier field blank.
const UEN_TOKEN_RE = /^\d{8,9}[A-Za-z]$|^[TSts]\d{2}[A-Za-z]{2}\d{4}[A-Za-z]$/

export function extractPaynowIdentifierCandidate(rawDescription: string): string {
  const tokens = rawDescription.split(/\s+/).filter(Boolean)

  for (const token of tokens) {
    if (UEN_TOKEN_RE.test(token)) return token.toUpperCase()
  }

  // A reference number like "PIB2605050213183371" is one whitespace token
  // mixing letters and digits - it never enters a run below, since the
  // whole-token digits-only test fails at the first letter. A phone number
  // sometimes gets space-split by the bank ("+65 9123 4567" as three
  // tokens) - this groups consecutive purely-numeric tokens back together
  // and checks the combined digit count, rather than only ever looking at
  // one token in isolation.
  const runs: string[][] = []
  let run: string[] = []
  for (const token of tokens) {
    const withoutSign = token.replace(/^\+/, '')
    if (withoutSign.length > 0 && /^\d+$/.test(withoutSign)) {
      run.push(token)
    } else if (run.length) {
      runs.push(run)
      run = []
    }
  }
  if (run.length) runs.push(run)

  for (const r of runs) {
    const joined = r.join('')
    const digitCount = joined.replace(/^\+/, '').length
    if (digitCount >= 8 && digitCount <= 11) return joined
  }
  return ''
}
