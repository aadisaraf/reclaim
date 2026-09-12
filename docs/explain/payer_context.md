# payer_context

`payer_context` reads the payer's own record of the denial: the decision endpoint on the mock
Northstar Health API returns the decision, decision date, reason code and text, allowed submission
channels, and the stated appeal deadline, and the step downloads and stores the denial letter PDF
behind that decision. It decides which deadline is the true one to act on — the payer's own
`appealDeadline` is always the deadline of record, but the step independently computes the
policy's appeal window (decision date plus the policy's `appealWindowDays`) as a cross-check, and
if the two disagree it raises a visible warning rather than silently trusting either one; it also
turns that deadline into "days left" against the fixed demo date. A payer claim ID the payer
doesn't recognize sends the case to `needs-review` instead of guessing. In production this step
would replace the mock Northstar Health API with a payer-specific `PayerAdapter` implementation
per payer, each wrapping that payer's own real REST or EDI integration behind the same interface.
