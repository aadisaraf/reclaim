# resolve_identity

`resolve_identity` reads six paired fields off the 835 remittance and the parsed 837 claim: claim
ID, member ID, date of service, payer ID, rendering provider NPI, and procedure code, plus (once
the six agree) the corresponding entry in the static `claim-map.json`, which is the only place
this hospital claim ID is linked to a patient, encounter, and diagnosis. It decides whether this
is definitively the same patient, encounter, and claim before any clinical record is ever touched:
if all six checks pass, the case moves to `claim-matched` and the claim-map entry becomes
available to `gather_evidence`; if even one check fails, or the claim map has no entry for this
claim, the case moves to `needs-review` naming the exact failing field, and the step makes zero
EHR requests, which the audit log can prove. Nothing here ever matches on a patient's name — only
identifiers are compared, which is why the gate can run before touching the chart at all. In
production this step would replace the static claim map with the enterprise Master Patient Index
(MPI) or a real claim-to-encounter mapping service, so the identifiers are resolved against a
live system of record instead of a checked-in JSON file.
