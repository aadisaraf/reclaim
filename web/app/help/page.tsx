import { HelpIcon } from "../components/icons";

export default function HelpPage() {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-lg)", maxWidth: 680 }}>
      <div style={{ display: "flex", alignItems: "center", gap: "var(--space-sm)" }}>
        <HelpIcon size={20} />
        <h1 style={{ fontSize: "var(--text-lg)", margin: 0 }}>Help</h1>
      </div>

      <div className="card">
        <p style={{ marginTop: 0 }}>
          Reclaim is an evidence-first denial recovery demo. Every patient, claim, payer, and
          document on this instance is synthetic — there is no real PHI anywhere in this app, and
          there is no upload path for it. Every screen and generated PDF says
          &ldquo;SYNTHETIC DEMO DATA&rdquo; for that reason.
        </p>
        <p>
          The pipeline runs nine steps per denied claim: ingest the remittance, fetch the original
          claim, resolve identity with six hard checks, gather only in-window clinical evidence,
          fetch the payer&rsquo;s decision, build a verified evidence matrix against the payer&rsquo;s
          policy, draft a cited appeal letter, wait for a human to approve and submit it, then track
          the payer&rsquo;s response.
        </p>
      </div>

      <div className="card">
        <h2 style={{ fontSize: "var(--text-base)", marginTop: 0 }}>The demo walkthrough</h2>
        <ol style={{ paddingLeft: "var(--space-lg)", margin: 0, display: "flex", flexDirection: "column", gap: "var(--space-sm)" }}>
          <li>From the queue, click <strong>Simulate incoming remit</strong> to deliver a sample 835.</li>
          <li>Open the case and check the <strong>Identity</strong> tab — six checks must all pass before anything else runs.</li>
          <li>The <strong>Evidence</strong> tab shows exactly what was fetched, and what was excluded and why.</li>
          <li>The <strong>Matrix</strong> tab shows each policy requirement and the verified citation behind it.</li>
          <li>The <strong>Packet</strong> tab is the drafted appeal — every sentence traces to a citation.</li>
          <li>Switch persona to <code className="code-value">billing-approver-01</code> and click <strong>Approve and submit</strong>.</li>
        </ol>
      </div>

      <div className="card">
        <h2 style={{ fontSize: "var(--text-base)", marginTop: 0 }}>Presenter controls</h2>
        <p style={{ marginBottom: 0 }}>
          The <strong>Missing-evidence toggle</strong> (queue page) hides one piece of clinical
          evidence so you can see the &ldquo;needs more evidence&rdquo; path. <strong>Reset demo</strong>{" "}
          clears every case and appeal so you can run the walkthrough again from a clean state.
        </p>
      </div>
    </div>
  );
}
