# ingest

`ingest` reads one 835 remittance file from the clearinghouse inbox: the raw bytes that
`RemitInbox` lists and downloads from the mock SFTP container's `outbound/835` directory, then
tokenizes and parses into an X12 835 envelope with one or more `CLP` claim loops. It decides, in
order, whether the envelope and its balancing are valid at all (malformed files are rejected and
recorded, never silently dropped), whether this exact file content has already been processed (a
SHA-256 of the bytes dedupes repeat delivery so the same remittance never creates a case twice),
and then, per `CLP` claim, which of three lanes it belongs to: a paid claim needs no action, a
CARC 50 denial with group code CO is a medical-necessity denial worth working and gets a case, and
any other denial is labelled and left untouched. In production this step would replace the mock
SFTP container with a real clearinghouse SFTP or API connection — the same `RemitInbox` interface,
pointed at a live feed instead of a fixture uploaded by the demo's "Simulate incoming remit"
button.
