import { useState } from 'react'
import {
  BarChart3,
  BookOpen,
  FileUp,
  Filter,
  Settings as SettingsIcon,
  SlidersHorizontal,
  Users,
} from 'lucide-react'

const SECTIONS = [
  { id: 'overview', label: 'Overview', icon: BookOpen },
  { id: 'uploading', label: 'Uploading Statements', icon: FileUp },
  { id: 'categorization', label: 'Categorization', icon: SlidersHorizontal },
  { id: 'dashboard', label: 'Dashboard & Filters', icon: Filter },
  { id: 'charts', label: 'Reading the Charts', icon: BarChart3 },
  { id: 'contacts', label: 'Contacts & PayNow', icon: Users },
  { id: 'settings', label: 'Settings & Data', icon: SettingsIcon },
]

function Section({ id, title, children }: { id: string; title: string; children: React.ReactNode }) {
  return (
    <section id={id} className="bg-card border border-border rounded-xl p-5 scroll-mt-24">
      <h2 className="text-[15px] font-bold mb-3">{title}</h2>
      <div className="text-[13px] text-muted leading-relaxed flex flex-col gap-2.5">{children}</div>
    </section>
  )
}

function Kbd({ children }: { children: React.ReactNode }) {
  return <code className="font-mono text-[12px] bg-input px-1.5 py-0.5 rounded text-text-2">{children}</code>
}

export function Guide() {
  const [activeId, setActiveId] = useState('overview')

  function scrollTo(id: string) {
    setActiveId(id)
    document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }

  return (
    <div className="px-9 pt-7 pb-15">
      <div className="mb-5.5">
        <div className="text-[22px] font-bold">User Guide</div>
        <div className="text-[13px] text-muted mt-0.5">
          How the pieces fit together — upload, categorize, review, repeat.
        </div>
      </div>

      <div className="grid grid-cols-[190px_1fr] gap-5 items-start">
        <div className="sticky top-7 flex flex-col gap-0.5">
          {SECTIONS.map((s) => {
            const Icon = s.icon
            return (
              <button
                key={s.id}
                onClick={() => scrollTo(s.id)}
                className={`flex items-center gap-2 text-left text-[13px] px-2.5 py-2 rounded-lg border-none cursor-pointer transition-colors ${
                  activeId === s.id ? 'bg-accent/12 text-text font-semibold' : 'bg-transparent text-muted hover:text-text'
                }`}
              >
                <Icon size={14} className="shrink-0" />
                {s.label}
              </button>
            )
          })}
        </div>

        <div className="flex flex-col gap-3.5 max-w-2xl">
          <Section id="overview" title="Overview">
            <p>
              This app turns bank statement PDFs into a categorized, searchable transaction history — entirely on
              your own machine. Nothing is uploaded anywhere; the SQLite database backing everything lives on your
              local disk (see the path under <strong className="text-text">Settings</strong>).
            </p>
            <p>The everyday loop is:</p>
            <ol className="list-decimal list-inside flex flex-col gap-1">
              <li>Upload one or more statement PDFs.</li>
              <li>Review how they were auto-categorized in the staging screen.</li>
              <li>Commit — transactions land in the dashboard, ready to filter and analyze.</li>
            </ol>
          </Section>

          <Section id="uploading" title="Uploading Statements">
            <p>
              Click <strong className="text-text">Upload Bank Statement</strong> in the sidebar (or drag a PDF
              anywhere onto the app). Currently UOB account and credit card e-statements are supported — other
              banks will show an "unrecognized format" error rather than silently misparsing.
            </p>
            <p>
              You can select multiple PDFs at once — they're merged into a single review batch, even across
              different months or a mix of account and card statements. If a PDF is password-protected, you'll be
              prompted for the password before it's parsed.
            </p>
            <p>
              Only one batch can be staged at a time. If you have a pending review, you'll need to commit or discard
              it before uploading another — the sidebar's yellow banner is a reminder that one is waiting.
            </p>
            <p>
              <strong className="text-text">Duplicate detection</strong> is automatic: re-uploading a statement you've
              already committed (or one that overlaps a previous upload) marks the overlapping rows as duplicates and
              skips them on commit, so it's safe to re-upload if you're not sure whether a statement was already
              processed.
            </p>
          </Section>

          <Section id="categorization" title="Categorization">
            <p>
              Every transaction is run through a priority-ordered set of rules — first match wins. Your own rules
              (visible under <strong className="text-text">Rules</strong>) always take precedence over the built-in
              word bank (<strong className="text-text">Default Rules</strong>), which is read-only and reconciled
              automatically as the app is updated.
            </p>
            <p>
              A rule matches on a substring of the transaction description and assigns a category — or, for an{' '}
              <strong className="text-text">exclusion rule</strong>, marks the transaction as excluded from totals
              instead (useful for self-transfers between your own accounts). You can create a rule directly from a
              transaction in the staging review screen ("Save as rule"), or from scratch under Rules.
            </p>
            <p>
              If nothing matches, a PayNow-shaped transaction is flagged{' '}
              <span className="text-[11px] font-semibold px-1.5 py-0.5 rounded" style={{ background: 'oklch(30% 0.07 70)', color: 'oklch(82% 0.13 70)' }}>
                needs review
              </span>{' '}
              in its own Paynow category rather than falling into a generic bucket — a phone number or UEN alone
              can't tell the app who was paid. Everything else that doesn't match anything lands in the hidden
              "Others" category.
            </p>
            <p>
              Already committed transactions can be re-scanned against the current rule set at any time with the{' '}
              <strong className="text-text">Recategorize</strong> button on the dashboard — handy after adding a new
              rule, since it only affects future uploads otherwise.
            </p>
          </Section>

          <Section id="dashboard" title="Dashboard & Filters">
            <p>
              The date range and account pickers at the top of the dashboard stay pinned while you scroll, so you can
              adjust them without jumping back to the top. The month-range picker supports single-click (one month)
              or click-and-drag (a range), plus "Latest month" and "All time" shortcuts.
            </p>
            <p>
              The transaction feed below can be searched (matches both the cleaned display name and the raw bank
              description) and filtered by category. Excluded transactions are dimmed but still listed by default —
              toggle <Kbd>Show excluded</Kbd> off to hide them entirely.
            </p>
            <p>
              Click the pencil icon on any row to edit its category, display name, or exclusion status by hand — a
              manual edit always sticks until you either change it again or run Recategorize.
            </p>
          </Section>

          <Section id="charts" title="Reading the Charts">
            <p>
              <strong className="text-text">Cash Flow</strong> shows inflow vs. outflow per month, always displaying
              a minimum of 6 and a maximum of 12 months of context regardless of how narrow or wide your selected
              range is. Hover a column for the exact figures.
            </p>
            <p>
              <strong className="text-text">Spend Velocity</strong> compares your selected range's cumulative
              spending pace against the immediately preceding period of equal length, day by day — useful for
              spotting whether you're on track to spend more or less than usual before the period even ends. Hover
              anywhere on the chart for a crosshair with both series' values.
            </p>
            <p>
              <strong className="text-text">Category Breakdown</strong> is a donut chart — hover a segment or its
              legend entry (either direction) to see that category's exact amount and share of total outflow.
            </p>
            <p>
              <strong className="text-text">Top Merchants</strong> and <strong className="text-text">Top Paynow
              Contacts</strong> live in the same card as Category Breakdown, switchable by tab.
            </p>
          </Section>

          <Section id="contacts" title="Contacts & PayNow">
            <p>
              A contact maps a PayNow identifier (phone number, UEN, or account number) to a name and a default
              category, so future transfers to that person or business categorize themselves automatically instead
              of sitting in "needs review". Add one from scratch under <strong className="text-text">Contacts</strong>,
              or the quicker way — "Save as contact mapping" directly from a flagged row in the staging review
              screen.
            </p>
            <p>
              Bulk-import identifiers from a 3-column CSV (Name, Identifier, Category) via{' '}
              <strong className="text-text">Import CSV</strong> on the Contacts page. An identifier already mapped to
              someone is left as-is rather than reassigned.
            </p>
          </Section>

          <Section id="settings" title="Settings & Data">
            <p>
              Your accent color, the database's on-disk location, and its size/schema version all live under{' '}
              <strong className="text-text">Settings</strong>. <strong className="text-text">Change Database
              Path</strong> moves the actual SQLite file to a new folder — handy for relocating it into a
              synced/backed-up directory.
            </p>
            <p>
              The Danger Zone offers two levels of destructive action: scoped deletes (clear just your rules,
              contacts, or transactions — each requires typing <Kbd>DELETE</Kbd> to confirm) and{' '}
              <strong className="text-text">Nuclear Reset</strong>, which wipes everything and starts fresh. Deleting
              rules or contacts never touches the built-in default rule bank; deleting transactions leaves your
              accounts in place so you can re-upload without re-provisioning them.
            </p>
          </Section>
        </div>
      </div>
    </div>
  )
}
