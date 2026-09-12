# track

`track` reads the payer's appeal status endpoint for every case in `submitted` status, polled by
the background poller on a fixed interval rather than on demand. It decides whether the status the
payer reports has actually changed since the last check — the demo payer moves an appeal from
"received" to "in-review" roughly 30 seconds after submission — and only when a real transition
happens does it update the case status and write an audit event; polls that report no change leave
the case and its history untouched, so the audit trail records what happened, not how often it was
checked. In production this step would replace one live poll per case with the OpenAI Batch API,
so tracking a large backlog of appeals can be done cost-efficiently in bulk rather than issuing a
separate synchronous status request for every open case.
