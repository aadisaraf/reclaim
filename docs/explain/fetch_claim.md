# fetch_claim

`fetch_claim` reads the original 837P claim for the case's hospital claim ID from the claim
archive: `ClaimArchive.get_837` downloads the matching file from the mock SFTP-backed archive,
which stands in for the hospital's own pre-adjudication claim record. It decides whether that
837 exists at all, and if it does, whether it tokenizes and parses cleanly and passes X12
validation (correct envelope, SE count, required segments) before anything downstream is allowed
to trust it — a missing file, a parse failure, or a validation failure all send the case straight
to `needs-review` naming the original claim as the problem, with no identity check or clinical
data request ever attempted. This gate matters because every later step, starting with
`resolve_identity`, compares the remittance against this 837, so an unverified 837 would poison
every check built on top of it. In production this step would replace the mock SFTP-backed
archive with the hospital's real claim archive or billing system, queried directly instead of
through a pre-seeded fixture file.
