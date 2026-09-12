# build_matrix

`build_matrix` reads the applicable payer policy's requirements, each naming the evidence types
that can satisfy it, together with the full set of evidence gathered and included by
`gather_evidence`. It decides whether each requirement is actually satisfied, but not by trusting
the LLM's word for it: the LLM proposes a status, a citation, and a verbatim excerpt per
requirement, and a separate deterministic verifier then checks every proposed citation
independently — that the cited resource was really fetched for this case, falls inside the
lookback window, is of a type the requirement allows, and that the excerpt is an exact substring
of that resource's own text or fields — before any citation is accepted as verified. A citation
that fails any of those checks is discarded and triggers one high-effort retry with the rejection
reasons attached; a requirement still unmet after that is marked missing, which blocks the case
from drafting a letter and instead opens a targeted evidence-request task. In production this step
would replace synthetic demo data with real PHI going to the LLM provider, which means it also
requires a Business Associate Agreement (BAA) and zero-data-retention contract terms with that
provider before this call could ever run for real.
