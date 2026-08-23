# UI/UX & User Flow Specification

## 1. Core User Journeys

### First-Time Onboarding

1. **App Launch:** User executes `uvx expenditure-tracker`. The local server launches and automatically opens `[http://127.0.0.1:8000](http://127.0.0.1:8000)` in the default browser.
2. **Zero-State Dashboard:** Displays an onboarding hero banner: *"Drag & Drop DBS, OCBC, or UOB Statements to Start"*.
3. **Initial Upload:** User drops e-statements into the dropzone.
4. **Auto Account Provisioning:** Account details (bank name, masked account number) are extracted from headers, creating account profiles automatically before landing on the **Staging Review** screen.

### Statement Ingestion & Staging

1. **Universal Dropzone:** Dragging a file over any screen activates a global visual overlay (`.pdf`, `.csv`).
2. **In-Memory Decryption Prompt:** If an encrypted PDF is detected, a modal requests the unlock password. Processing occurs strictly in local RAM; the password is never persisted.
3. **Pre-Commit Staging Review:** Users inspect parsed entries, verify skipped duplicate totals, and fix unparsed `Others > PayNow` rows before committing data to the database.

---

## 2. Detailed Screen Specifications

### Screen A: Post-Mortem Dashboard

* **Filters:** Global controls for Month/Year and Account selection.
* **Metric Cards:** Net Expenditure, Total Inflow, PayNow vs. Card Spend Split.
* **Analytics Widgets:**
1. **Cash Flow Bar Chart:** Monthly Inflow vs. Outflow totals.
2. **Category Breakdown Donut Chart:** Interactive spend distribution.
3. **Spend Velocity Line Chart:** Cumulative spend pace for current vs. previous month.
4. **Top Merchants & PayNow Contacts:** Ranked list of top vendors and transfer recipients.


* **Transaction Feed Table:**
* **Refund/Reversal Badge:** Transactions netted out against a refund display an interactive link icon. Clicking it opens a drawer showing the original transaction and its corresponding refund line.
* **Exclusion Toggle:** Filter option to include or hide transactions flagged as excluded.



### Screen B: Staging & Pre-Commit Review

* **Batch Summary Badges:** Displays `New Extracted`, `Duplicates Skipped`, and `New Accounts Provisioned`.
* **Interactive Staging Grid:** Unparsed rows (`Others > PayNow`) are highlighted in amber. Clicking a row triggers an inline popover allowing users to assign a category and optionally convert it into a rule or contact mapping.
* **Commit Bar:** Includes buttons for `"Discard Batch"` and `"Commit [X] Transactions"`.

### Screen C: Contacts & PayNow Directory

* **Contact Directory:** Table displaying Contact Name, Linked Identifiers (Phone Numbers, UENs, Bank Accounts), Default Category, and Historical Spend.
* **Multi-Identifier Entry:** Adding or editing a contact allows mapping multiple phone numbers or UENs under a single entity name.
* **CSV Import:** Action button to upload a contact mapping CSV (`Name, Identifier, Category`).

### Screen D: Categorization & Exclusion Rules

* **Priority Rule List:** Draggable list view displaying rules ordered by execution priority (higher priority rules evaluate first).
* **Exclusion Rules:** Rules configured to ignore specific transaction patterns from dashboard analytics (e.g., specific internal transfers or non-budgeted spend). Includes a custom `Exclusion Reason` field.
* **Rule Builder Modal:** Configure matching logic: `IF [Raw Description] CONTAINS [Pattern] THEN SET [Category] AND [Priority]`.

### Screen E: Settings & Storage Management

* **Database Path Management:** Displays the current SQLite database path and file size.
* **Relocation Workflow:** Clicking `"Change Database Path"` opens a warning dialog displaying the database size and confirming that the file will be migrated to the new location.
* **Data Erasure:** Includes a `"Nuclear Reset"` button that requires explicit text confirmation before purging local database files.
