# draft_packet

`draft_packet` reads the verified evidence matrix produced by `build_matrix` — only the rows and
citations that already passed independent verification are available to draft from. It decides how
to phrase the appeal letter's body as a list of statements, where every factual statement must
carry a citation back to a specific verified matrix requirement; an LLM drafts the wording, but a
deterministic verifier checks each statement's citations before the packet can exist at all, and
any statement that is uncited or that cites something not actually verified blocks the whole
packet rather than reaching a human with an unsupported claim in it. Only once every statement is
properly cited does the case move to `ready-for-review` with a new packet version, ready for a
person to read and approve. In production this step would replace the demo's persona picker with
real single-sign-on (SSO) roles for the human approval gate, so the identity of whoever is about
to review the packet is authenticated for real rather than selected from a list.
