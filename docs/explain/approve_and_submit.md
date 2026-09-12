# approve_and_submit

`approve_and_submit` reads the packet a user is trying to approve — its version, its status, and
the evidence matrix it was built from — together with the role of the user making the request. It
decides whether that request is actually allowed to proceed: the packet must be the latest version
and in `ready-for-review` with every requirement satisfied, and the requesting user must hold the
`authorized-billing-user` role, or the submission is refused outright (a `viewer-01` persona can
read a case but never approve one). Once allowed, the step moves the case from `ready-for-review`
through `approved` to `submitted` in one request, uploading the letter, cited attachments, and
policy snapshot to the payer and creating the appeal with an idempotency key of
`appeal-<caseId>-v<version>`, so pressing the button twice — or any retry — returns the same
confirmation instead of filing a second appeal. In production this step would replace the mock
REST API with the payer's real portal or clearinghouse submission channel, behind the same
`PayerAdapter` interface.
