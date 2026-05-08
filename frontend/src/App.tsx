import { Download, FileText, ShieldCheck } from "lucide-react";
import { useState } from "react";
import { runFactCheck } from "./api";
import { ProgressRail } from "./components/ProgressRail";
import { ResultsTable } from "./components/ResultsTable";
import { UploadPanel } from "./components/UploadPanel";
import { VerdictSummary } from "./components/VerdictSummary";
import type { FactCheckReport, ScanMode } from "./types";

export default function App() {
  const [file, setFile] = useState<File | null>(null);
  const [scanMode, setScanMode] = useState<ScanMode>("focused");
  const [report, setReport] = useState<FactCheckReport | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isRunning, setIsRunning] = useState(false);

  async function handleRun() {
    if (!file || isRunning) {
      return;
    }

    setError(null);
    setIsRunning(true);

    try {
      const nextReport = await runFactCheck(file, scanMode);
      setReport(nextReport);
    } catch (runError) {
      setReport(null);
      setError(
        runError instanceof Error
          ? runError.message
          : "Fact-check failed. Please try again.",
      );
    } finally {
      setIsRunning(false);
    }
  }

  function handleDownloadJson() {
    if (!report) {
      return;
    }

    const blob = new Blob([JSON.stringify(report, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");

    link.href = url;
    link.download = "fact-check-report.json";
    link.click();

    window.setTimeout(() => URL.revokeObjectURL(url), 0);
  }

  return (
    <main className="appShell">
      <header className="topBar">
        <div className="brandMark" aria-label="Fact-Check Agent">
          <ShieldCheck size={22} strokeWidth={2.1} />
          <span>Fact-Check Agent</span>
        </div>
        <span className={`statusPill ${isRunning ? "running" : ""}`}>
          {isRunning ? "Running" : "Ready"}
        </span>
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
          <UploadPanel
            file={file}
            scanMode={scanMode}
            isRunning={isRunning}
            onFileChange={setFile}
            onScanModeChange={setScanMode}
            onRun={handleRun}
          />
          <ProgressRail isRunning={isRunning} />
        </aside>

        <section className="resultsPane" aria-label="Fact-check results">
          {error ? <div className="errorBox">{error}</div> : null}

          {!report && !error ? (
            <div className="emptyState">
              <FileText size={38} strokeWidth={1.7} />
              <h2>No report yet</h2>
              <p>
                Choose a PDF and run the pipeline to inspect verdicts,
                corrections, confidence, and sources.
              </p>
            </div>
          ) : null}

          {report ? (
            <div className="reportStack">
              <div className="reportHeader">
                <div>
                  <span className="eyebrow">Report</span>
                  <h2>{report.file_name}</h2>
                  <p>{report.scan_mode === "deep" ? "Deep Scan" : "Focused"} mode</p>
                </div>
                <button
                  type="button"
                  className="downloadButton"
                  onClick={handleDownloadJson}
                >
                  <Download size={18} strokeWidth={2} />
                  <span>JSON</span>
                </button>
              </div>
              <VerdictSummary summary={report.summary} />
              <ResultsTable claims={report.claims} />
            </div>
          ) : null}
        </section>
      </section>
    </main>
  );
}
