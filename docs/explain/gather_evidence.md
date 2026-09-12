# gather_evidence

`gather_evidence` reads FHIR R4 resources from the mock hospital EHR for the patient and encounter
named in the claim map: it reads the Encounter and Patient directly, searches Coverage,
Condition, ServiceRequest, Procedure, DiagnosticReport, Observation, DocumentReference, and
MedicationRequest by patient, and fetches the Binary text behind every DocumentReference that
falls inside the lookback window. It decides, first, two more identity checks that only become
possible once the Encounter and Coverage are in hand — the encounter's date and subject, and
Coverage.subscriberId, must match the remittance and claim map, or the case stops at
`needs-review` with no further reads — then which payer policy applies (selected by payer ID, the
plan type read off Coverage, the billing state from the 837, procedure code, and date of service),
and finally which fetched records actually count as evidence: only those dated within the
policy's lookback window around the date of service are marked included, with every exclusion and
its reason recorded so the count of what was left out is never hidden. In production this step
would replace the mock FHIR server with SMART Backend Services (OAuth2 client_credentials) against
the hospital's real FHIR R4 endpoint.
