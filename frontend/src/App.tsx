import { FileText, ShieldCheck } from "lucide-react";

export default function App() {
  return (
    <main className="appShell">
      <header className="topBar">
        <div className="brandMark" aria-label="Fact-Check Agent">
          <ShieldCheck size={22} strokeWidth={2.1} />
          <span>Fact-Check Agent</span>
        </div>
        <span className="statusPill">Ready</span>
      </header>

      <section className="workspace" aria-label="Analyst workbench">
        <aside className="controlPanel">
          <div className="panelIcon" aria-hidden="true">
            <FileText size={24} strokeWidth={1.9} />
          </div>
          <h1>PDF fact-check</h1>
          <p>
            Upload a source document, choose a scan depth, and review extracted
            claims against evidence from the verification pipeline.
          </p>
        </aside>

        <section className="resultsPane" aria-label="Fact-check results">
          <div className="emptyState">Upload a PDF to begin.</div>
        </section>
      </section>
    </main>
  );
}
