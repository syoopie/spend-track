import { type ReactNode, useState } from 'react'
import { useCategories } from '../api/hooks'
import type { CategoryDirection, Rule } from '../api/types'
import { Button } from './Button'
import { categoryOptionElements } from './CategoryOptions'
import { Checkbox } from './Checkbox'
import { Field, Input } from './Field'
import { Modal } from './Modal'
import { Select } from './Select'

// Rough client-side preview of the backend's fallback (engine/rules.py:
// `display_label or match_pattern.title()`) - not required to match Python's
// str.title() byte-for-byte, since it's only ever shown as a placeholder
// hint here, never actually sent or applied.
function titleCase(text: string): string {
  return text.toLowerCase().replace(/(^|\s)\S/g, (c) => c.toUpperCase())
}

export interface RuleFormSubmitValues {
  match_pattern: string
  target_category: string | null
  is_exclusion_rule: boolean
  exclusion_reason: string | null
  direction?: CategoryDirection
  priority: number | null
  display_label: string | null
}

// Originally Rules.tsx-only (create/edit a persistent rule from the Rules
// page). Pulled out into its own file so the pre-commit review dialog's
// "Create Rule" action (ReviewDialog.tsx) can open this exact same form
// instead of its own smaller, differently-laid-out inline one - one visual
// design for "make a rule" instead of two that drift apart over time.
//
// The two callers still submit differently underneath (Rules.tsx creates/
// updates a rule directly; a review dialog creates one AND reruns it over
// the rest of the open batch, with its own undo mechanism) - `onSubmit` is
// how that stays the caller's problem rather than this component's.
// `mode="quick"` hides exclusion-rule/priority, which only Rules.tsx's
// direct-to-/rules endpoint supports - the batch quick-create endpoint a
// review dialog calls through only ever takes a pattern/category/label.
export function RuleFormModal({
  rule,
  initialPattern,
  initialCategory,
  initialDisplayLabel,
  mode = 'full',
  onPatternChange,
  patternHint,
  onSubmit,
  saving = false,
  onClose,
}: {
  rule?: Rule
  initialPattern?: string
  initialCategory?: string
  initialDisplayLabel?: string | null
  mode?: 'full' | 'quick'
  // Fired on every keystroke in the pattern field - lets a caller (a review
  // dialog, to show its own live "matches N transactions" preview) track
  // the in-progress value without this component lifting all of its form
  // state out to a controlled prop.
  onPatternChange?: (pattern: string) => void
  // Rendered directly under the pattern field - the review dialog's live
  // match-count preview slots in here; Rules.tsx leaves it unset.
  patternHint?: ReactNode
  onSubmit: (body: RuleFormSubmitValues) => Promise<void>
  saving?: boolean
  onClose: () => void
}) {
  const categoriesQ = useCategories()
  const [pattern, setPattern] = useState(rule?.match_pattern ?? initialPattern ?? '')
  const [category, setCategory] = useState(rule?.target_category ?? initialCategory ?? '')
  const [displayLabel, setDisplayLabel] = useState(rule?.display_label ?? initialDisplayLabel ?? '')
  const [priority, setPriority] = useState<number | ''>(rule?.priority ?? '')
  const [isExclusion, setIsExclusion] = useState(rule?.is_exclusion_rule ?? false)
  const [exclusionReason, setExclusionReason] = useState(rule?.exclusion_reason ?? '')
  // Only meaningful (and sent to the backend) for an exclusion rule - a
  // category rule's direction is always just the direction of whichever
  // category it assigns, so the backend derives that on its own rather
  // than trusting a second, independently-editable copy of the same fact
  // that could drift out of sync with the category picked below.
  const [exclusionDirection, setExclusionDirection] = useState<CategoryDirection>(rule?.direction ?? 'outflow')

  async function handleSave() {
    if (!pattern.trim()) return
    await onSubmit({
      match_pattern: pattern.trim(),
      target_category: isExclusion ? null : category || categoriesQ.data?.[0]?.name || 'Others',
      is_exclusion_rule: isExclusion,
      exclusion_reason: isExclusion ? exclusionReason.trim() || null : null,
      direction: isExclusion ? exclusionDirection : undefined,
      priority: priority === '' ? null : priority,
      display_label: isExclusion ? null : displayLabel.trim() || null,
    })
    onClose()
  }

  return (
    <Modal onClose={onClose} width={460} title={rule ? 'Edit Rule' : 'New Rule'}>
      {/* No negative top margin here (there used to be one, to tuck this
          closer under the title) - Modal's body wrapper is overflow-y-auto
          with no top padding, so a negative margin on its first child
          rendered above the scroll container's own top edge and got
          silently clipped instead of just looking tighter. */}
      <div className="text-xs text-muted mb-4">
        Applies to every transaction whose description contains the text below.
      </div>

      <div className="flex flex-col gap-3.5">
        <div>
          <Field label="Description contains">
            <Input
              autoFocus
              value={pattern}
              onChange={(e) => {
                setPattern(e.target.value)
                onPatternChange?.(e.target.value)
              }}
              placeholder="e.g. NETFLIX"
            />
          </Field>
          {patternHint}
        </div>

        {mode === 'full' && (
          <label className="flex items-center gap-2 cursor-pointer text-md">
            <Checkbox checked={isExclusion} onChange={setIsExclusion} />
            Exclude these transactions instead of categorizing them
          </label>
        )}

        <div className="h-px bg-border" />

        {!isExclusion && (
          <div>
            <div className="text-xs text-muted mb-1">Category</div>
            <Select value={category} onChange={(e) => setCategory(e.target.value)} className="w-full">
              <option value="">Select category…</option>
              {categoryOptionElements(categoriesQ.data)}
            </Select>
          </div>
        )}

        {!isExclusion && (
          <Field
            label="Display name (optional)"
            hint='Shown instead of the raw bank description for matching transactions. Leave blank to just title-case the pattern above.'
          >
            <Input
              value={displayLabel}
              onChange={(e) => setDisplayLabel(e.target.value)}
              placeholder={pattern.trim() ? titleCase(pattern.trim()) : 'e.g. Netflix'}
            />
          </Field>
        )}

        {mode === 'full' && isExclusion && (
          <div className="flex flex-col gap-3.5">
            <Field label="Exclusion reason">
              <Input
                value={exclusionReason}
                onChange={(e) => setExclusionReason(e.target.value)}
                placeholder="e.g. Self-transfer between own accounts"
              />
            </Field>
            <div>
              <div className="text-xs text-muted mb-1">Applies to</div>
              <Select
                value={exclusionDirection}
                onChange={(e) => setExclusionDirection(e.target.value as CategoryDirection)}
                className="w-full"
              >
                <option value="outflow">Outflow transactions only</option>
                <option value="inflow">Inflow transactions only</option>
              </Select>
              <div className="text-2xs text-muted-2 mt-1">
                An exclusion rule has no category to imply a direction from, so this must be picked explicitly -
                otherwise a pattern like a self-transfer's description could exclude both legs of an unrelated
                transaction pair.
              </div>
            </div>
          </div>
        )}

        {mode === 'full' && (
          <div className="flex items-center justify-between gap-3">
            <div>
              <div className="text-xs text-muted">Priority</div>
              <div className="text-2xs text-muted-2">Lower numbers are evaluated first</div>
            </div>
            <Input
              fullWidth={false}
              type="number"
              value={priority}
              onChange={(e) => setPriority(e.target.value === '' ? '' : Number(e.target.value))}
              placeholder="auto"
              className="w-20 text-right"
            />
          </div>
        )}
      </div>

      <div className="flex justify-end gap-2.5 mt-5">
        <Button onClick={onClose}>Cancel</Button>
        <Button variant="primary" onClick={handleSave} disabled={saving || !pattern.trim()}>
          {rule ? 'Save Changes' : 'Save Rule'}
        </Button>
      </div>
    </Modal>
  )
}
