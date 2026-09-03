import {
  BarChart3,
  BookOpen,
  CheckCheck,
  FileUp,
  Filter,
  Info,
  ListChecks,
  Settings as SettingsIcon,
  ShieldAlert,
  SlidersHorizontal,
  Sparkles,
  Users,
  type LucideIcon,
} from 'lucide-react'
import type { ReactNode } from 'react'
import { useSettings } from '../api/hooks'
import { Card } from '../components/Card'
import { PageShell } from '../components/PageShell'

const SECTIONS: { id: string; label: string; icon: LucideIcon }[] = [
  { id: 'overview', label: 'Overview', icon: BookOpen },
  { id: 'uploading', label: 'Uploading Statements', icon: FileUp },
  { id: 'categorization', label: 'Categorization', icon: SlidersHorizontal },
  { id: 'dashboard', label: 'Dashboard & Filters', icon: Filter },
  { id: 'charts', label: 'Reading the Charts', icon: BarChart3 },
  { id: 'contacts', label: 'Contacts & PayNow', icon: Users },
  { id: 'settings', label: 'Settings & Data', icon: SettingsIcon },
]

function Section({ id, title, icon: Icon, children }: { id: string; title: string; icon: LucideIcon; children: ReactNode }) {
  return (
    <section id={id} className="scroll-mt-9">
      <div className="flex items-center gap-2.5 mb-2.5 pb-2 border-b border-border">
        <div className="w-6 h-6 rounded-md bg-accent/12 flex items-center justify-center shrink-0">
          <Icon size={13} className="text-accent" />
        </div>
        <h2 className="text-base font-bold font-display">{title}</h2>
      </div>
      <div className="text-md text-muted leading-relaxed flex flex-col gap-3">{children}</div>
    </section>
  )
}

function Kbd({ children }: { children: ReactNode }) {
  return <code className="font-mono text-xs bg-input px-1.5 py-0.5 rounded text-text-2">{children}</code>
}

// A term/explanation pair per row, instead of the same fact buried mid-paragraph.
// The point of the whole page is to be skimmable back-to-front, and a bolded
// left column is what makes "where's the bit about passwords?" a glance rather
// than a read. Single column below sm - a 164px term column stops being a column
// once the explanation next to it wraps to three lines. Rows are separated by
// their own bottom rule rather than the list carrying a border-y: a Facts block
// that opens a section would otherwise draw a second line a few px under the
// section header's own divider.
function Facts({ items }: { items: { term: string; children: ReactNode }[] }) {
  return (
    <dl className="flex flex-col">
      {items.map((item) => (
        <div
          key={item.term}
          className="grid gap-x-4 gap-y-0.5 py-2.5 sm:grid-cols-[164px_1fr] border-b border-divider last:border-b-0"
        >
          <dt className="text-md font-semibold text-text">{item.term}</dt>
          <dd className="text-md text-muted">{item.children}</dd>
        </div>
      ))}
    </dl>
  )
}

// Numbered badges matching the priority badges on the Rules page - livelier than
// a bare <ol>, and the categorization ladder it renders *is* a priority order.
function Steps({ items }: { items: ReactNode[] }) {
  return (
    <div className="flex flex-col gap-2">
      {items.map((step, i) => (
        <div key={i} className="flex items-start gap-2.5">
          <div className="w-5 h-5 rounded-md bg-input text-accent text-2xs font-bold flex items-center justify-center shrink-0 mt-0.5">
            {i + 1}
          </div>
          <div className="pt-0.5">{step}</div>
        </div>
      ))}
    </div>
  )
}

// The overview's three-step loop as tiles rather than a sentence describing a
// sequence - it's the one thing on this page a first-time reader should absorb
// without reading anything.
function StepCards({ items }: { items: { icon: LucideIcon; title: string; body: string }[] }) {
  return (
    <div className="grid gap-2.5 sm:grid-cols-3">
      {items.map(({ icon: Icon, title, body }, i) => (
        <Card key={title} padding="p-3.5" className="flex flex-col gap-1.5">
          <div className="flex items-center gap-2">
            <div className="w-5 h-5 rounded-md bg-input text-accent text-2xs font-bold flex items-center justify-center shrink-0">
              {i + 1}
            </div>
            <Icon size={13} className="text-muted-2" />
            <div className="text-md font-semibold text-text">{title}</div>
          </div>
          <div className="text-md text-muted leading-relaxed">{body}</div>
        </Card>
      ))}
    </div>
  )
}

// Semantic surface tokens per docs/ui-conventions.md - never hand-derived here.
const NOTE_TONES = {
  info: { bg: 'var(--color-input)', border: 'var(--color-border)', fg: 'var(--color-text-2)' },
  ai: { bg: 'var(--color-ai-surface)', border: 'var(--color-ai-surface-border)', fg: 'var(--color-ai-text)' },
  danger: { bg: 'var(--color-danger-surface)', border: 'var(--color-danger-surface-border)', fg: 'var(--color-danger-text)' },
} as const

function Note({
  tone = 'info',
  icon: Icon,
  title,
  children,
}: {
  tone?: keyof typeof NOTE_TONES
  icon: LucideIcon
  title: string
  children: ReactNode
}) {
  const { bg, border, fg } = NOTE_TONES[tone]
  return (
    <div className="rounded-2lg px-3.5 py-3 flex items-start gap-2.5" style={{ background: bg, border: `1px solid ${border}` }}>
      <Icon size={13} className="shrink-0 mt-0.5" style={{ color: fg }} />
      <div className="flex flex-col gap-1 min-w-0">
        <div className="text-md font-semibold" style={{ color: fg }}>
          {title}
        </div>
        <div className="text-md text-muted leading-relaxed">{children}</div>
      </div>
    </div>
  )
}

function NoteList({ items }: { items: ReactNode[] }) {
  return (
    <ul className="flex flex-col gap-1.5">
      {items.map((item, i) => (
        <li key={i} className="flex items-start gap-2">
          <span className="w-1 h-1 rounded-full bg-muted-2 shrink-0 mt-2" />
          <span className="min-w-0">{item}</span>
        </li>
      ))}
    </ul>
  )
}

function NeedsReviewBadge() {
  return (
    <span
      className="text-2xs font-semibold px-1.5 py-0.5 rounded"
      style={{ background: 'var(--color-warning-badge-bg)', color: 'var(--color-warning-text)' }}
    >
      needs review
    </span>
  )
}

export function Guide() {
  // Never a retyped list. This paragraph claimed DBS and OCBC were unsupported
  // for as long as they have been supported, which is what a hand-maintained
  // copy of `parsing_implemented` does to you.
  const supportedBanks = useSettings().data?.supported_banks ?? []
  return (
    <PageShell
      title="User Guide"
      subtitle="How the pieces fit together — upload, categorize, review, repeat."
      icon={BookOpen}
      maxWidth="max-w-3xl"
    >
      {/* A plain table of contents, not a nav bar - this is a document to
          read top to bottom, not a set of screens to switch between. */}
      <nav className="mb-8 pb-6 border-b border-border">
        <div className="text-2xs font-semibold uppercase tracking-wide text-muted-2 mb-2.5">Contents</div>
        <ol className="grid grid-cols-2 gap-x-6 gap-y-1.5 text-md">
          {SECTIONS.map((s, i) => (
            <li key={s.id}>
              <a href={`#${s.id}`} className="group flex items-center gap-2 text-muted hover:text-text">
                <span className="font-mono text-2xs text-muted-2 group-hover:text-accent">
                  {String(i + 1).padStart(2, '0')}
                </span>
                <span className="group-hover:underline">{s.label}</span>
              </a>
            </li>
          ))}
        </ol>
      </nav>

      <div className="flex flex-col gap-7">
        <Section id="overview" title="Overview" icon={BookOpen}>
          <p>Statement PDFs in, a categorized and searchable spending history out. The loop is three steps:</p>
          <StepCards
            items={[
              { icon: FileUp, title: 'Upload', body: 'Drop in one or more statement PDFs.' },
              { icon: ListChecks, title: 'Review', body: 'Check how each transaction was categorized, fix what looks wrong.' },
              { icon: CheckCheck, title: 'Commit', body: 'The batch joins your history and the dashboard updates.' },
            ]}
          />
          <Note icon={Info} title="Everything stays on this machine">
            Nothing is uploaded anywhere. Your transactions live in a single database file on your own disk — its
            exact path is on the <strong className="text-text">Settings</strong> page. The one exception is AI
            categorization with a cloud provider, which is off unless you turn it on yourself.
          </Note>
        </Section>

        <Section id="uploading" title="Uploading Statements" icon={FileUp}>
          <p>
            Click <strong className="text-text">Upload Bank Statement</strong> in the sidebar, or drag a PDF
            anywhere onto the app.
          </p>
          <Facts
            items={[
              {
                term: "What's supported",
                children: (
                  <>
                    {supportedBanks.length > 0 ? `${supportedBanks.join(', ')} ` : 'The banks listed under Region '}
                    e-statements parse today, account and credit card alike. Anything else is reported as an
                    unrecognized format rather than silently misparsed. If yours is missing,{' '}
                    <strong className="text-text">Help add your bank</strong> at the bottom of the sidebar turns one
                    of your own statements into a sample a parser can be written against, with your details taken
                    out first.
                  </>
                ),
              },
              {
                term: 'Several at once',
                children:
                  'Select multiple PDFs and they merge into one review batch — different months and a mix of account and card statements are all fine together.',
              },
              { term: 'Password-protected', children: "You'll be prompted for the password before the PDF is parsed." },
              {
                term: 'One batch at a time',
                children:
                  'Commit or discard a pending review before uploading again. A banner at the top of the app follows you around until you do.',
              },
              {
                term: 'Duplicates',
                children:
                  "Re-uploading a statement you've already committed is safe — overlapping rows are detected and skipped on commit, so you never need to remember which months are already in.",
              },
            ]}
          />
        </Section>

        <Section id="categorization" title="Categorization" icon={SlidersHorizontal}>
          <p>Each transaction is checked against the following, in order. First match wins:</p>
          <Steps
            items={[
              <>
                <strong className="text-text">Your own rules</strong>, in the order they're listed on the{' '}
                <strong className="text-text">Rules</strong> page.
              </>,
              <>
                <strong className="text-text">The built-in merchant list</strong> (
                <strong className="text-text">Default Rules</strong>) — read-only, kept up to date as the app is
                updated, and always ranked below your own rules so it can never override one.
              </>,
              <>
                <strong className="text-text">Credit card bill payments</strong>, which are excluded from spending
                so the card's own purchases aren't counted twice. Only applies once a card statement is known —
                otherwise the payment stays visible as real outflow.
              </>,
              <>
                <strong className="text-text">Your contacts</strong> — a saved PayNow identifier categorizes the
                transfer as whatever that contact's default category is.
              </>,
              <>
                <strong className="text-text">Nothing matched.</strong> A PayNow-shaped transaction is flagged{' '}
                <NeedsReviewBadge /> in its own Paynow category, since a phone number or UEN alone can't say who
                was paid. Anything else lands in "Others" (or "Other Income" for money in).
              </>,
            ]}
          />
          <Facts
            items={[
              {
                term: 'What a rule matches',
                children:
                  'Any part of the transaction description, assigned to a category you pick. Matching is case-insensitive.',
              },
              {
                term: 'Exclusion rules',
                children:
                  'Mark a match as excluded from totals instead of categorizing it — useful for transfers between your own accounts.',
              },
              {
                term: 'Making one',
                children: (
                  <>
                    From a transaction in the review screen — which also re-categorizes anything else still in that
                    batch that matches — or from scratch under <strong className="text-text">Rules</strong>.
                  </>
                ),
              },
              {
                term: 'Recategorize',
                children: (
                  <>
                    A new rule only affects future uploads. The{' '}
                    <strong className="text-text">Recategorize</strong> button on the dashboard re-scans everything
                    you've already committed against the current rules.
                  </>
                ),
              },
            ]}
          />
          <Note tone="ai" icon={Sparkles} title="AI suggestions are opt-in and off by default">
            <NoteList
              items={[
                <>
                  <strong className="text-text">What it does:</strong> once enabled under{' '}
                  <strong className="text-text">Settings</strong>, whatever the rules leave in "Others" goes to a
                  model for a suggested category, label, and rule.
                </>,
                <>
                  <strong className="text-text">You still decide:</strong> suggestions arrive pre-filled in the
                  review screen to accept or reject. Nothing is applied silently, and a rejected one can be
                  restored later.
                </>,
                <>
                  <strong className="text-text">Where it runs:</strong> a local{' '}
                  <a
                    href="https://ollama.com"
                    target="_blank"
                    rel="noreferrer"
                    className="text-accent no-underline hover:underline"
                  >
                    Ollama
                  </a>{' '}
                  model by default, so nothing leaves this device — install Ollama, pull a model, and point Settings
                  at it. An OpenAI-compatible or Anthropic provider instead sends those transactions' descriptions
                  and amounts to that company's servers.
                </>,
              ]}
            />
          </Note>
        </Section>

        <Section id="dashboard" title="Dashboard & Filters" icon={Filter}>
          <Facts
            items={[
              {
                term: 'Range & account',
                children:
                  'Both pickers stay pinned while you scroll. Click one month, drag across several for a range, or use the "Latest month" and "All time" shortcuts.',
              },
              {
                term: 'Search',
                children: 'Matches both the cleaned-up display name and the raw description printed on the statement.',
              },
              {
                term: 'Excluded rows',
                children: (
                  <>
                    Dimmed but still listed by default — turn <Kbd>Show excluded</Kbd> off to hide them entirely.
                  </>
                ),
              },
              {
                term: 'Editing by hand',
                children:
                  'The pencil icon on any row edits its category, display name, or exclusion. A manual edit sticks until you change it again or run Recategorize.',
              },
            ]}
          />
        </Section>

        <Section id="charts" title="Reading the Charts" icon={BarChart3}>
          <Facts
            items={[
              {
                term: 'Cash Flow',
                children:
                  'Money in vs. money out per month, always showing 6–12 months of context however narrow your selected range is. Hover a column for exact figures.',
              },
              {
                term: 'Spend Velocity',
                children:
                  "Your selected range's spending pace against the period just before it, day by day — so you can see whether you're on track to overspend before the month is even over. Hover for a crosshair with both values.",
              },
              {
                term: 'Category Breakdown',
                children:
                  "A donut of where the outflow went. Hover a segment or its legend entry — either direction works — for that category's amount and share.",
              },
              {
                term: 'Top Merchants',
                children: 'Who you paid most in the selected range. Shares a card with Category Breakdown, switchable by tab.',
              },
              {
                term: 'Top Paynow Contacts',
                children: 'The same, for people and businesses paid by PayNow transfer.',
              },
            ]}
          />
        </Section>

        <Section id="contacts" title="Contacts & PayNow" icon={Users}>
          <p>
            A contact maps a PayNow identifier — phone number, UEN, or account number — to a name and a default
            category. Future transfers to that person or business then categorize themselves, instead of arriving
            as <NeedsReviewBadge /> for you to sort out by hand.
          </p>
          <Facts
            items={[
              {
                term: 'Adding one',
                children: (
                  <>
                    "Save as contact mapping" straight from a flagged row in the review screen, or from scratch on
                    the <strong className="text-text">Contacts</strong> page — where existing ones can be edited too.
                  </>
                ),
              },
              {
                term: 'Bulk import',
                children: (
                  <>
                    <strong className="text-text">Import CSV</strong> on the Contacts page takes three columns —
                    name, identifier, category — with an optional header row:
                    <div className="font-mono text-xs bg-input rounded-md px-2.5 py-1.5 mt-1.5 text-text-2 overflow-x-auto whitespace-pre">
                      {'Jane Tan,91234567,Paynow\nKopitiam Uncle,201912345K,Food & Drink'}
                    </div>
                  </>
                ),
              },
              {
                term: 'Already mapped',
                children:
                  'An identifier that already belongs to someone is left alone rather than reassigned. A new identifier for a name you already have is added to that existing contact.',
              },
            ]}
          />
        </Section>

        <Section id="settings" title="Settings & Data" icon={SettingsIcon}>
          <Facts
            items={[
              { term: 'Appearance', children: 'Pick the accent color used throughout the app.' },
              {
                term: 'Region',
                children: 'Which country, currency, transfer scheme, and banks this build is set up for.',
              },
              {
                term: 'Database',
                children: (
                  <>
                    Where your data file sits, how big it is, and its schema version.{' '}
                    <strong className="text-text">Change Database Path</strong> physically moves the file — handy
                    for putting it somewhere synced or backed up.
                  </>
                ),
              },
              {
                term: 'Backups',
                children: (
                  <>
                    <strong className="text-text">Download Backup</strong> saves a single zip holding your database,
                    your settings, and a note explaining how to restore them — on this computer or a different one.
                    Your AI provider key is left out on purpose (a backup often ends up in cloud storage), so
                    re-enter it after restoring. The database inside is ordinary SQLite: any SQLite browser can open
                    it, so your data is never locked in here.
                  </>
                ),
              },
              {
                term: 'Danger Zone',
                children: (
                  <>
                    Clear just your rules, contacts, or transactions — or{' '}
                    <strong className="text-text">Nuclear Reset</strong>, which wipes everything and starts fresh.
                  </>
                ),
              },
            ]}
          />
          <Note tone="danger" icon={ShieldAlert} title="What a delete actually takes with it">
            Deleting rules or contacts never touches the built-in default rules, and deleting transactions keeps
            your accounts so you can re-upload without setting them up again. The two that can't be undone by
            ordinary use — <strong className="text-text">Delete All Transactions</strong> and{' '}
            <strong className="text-text">Nuclear Reset</strong> — ask you to type <Kbd>DELETE</Kbd> first; the
            lighter ones just ask for a confirmation.
          </Note>
        </Section>
      </div>
    </PageShell>
  )
}
