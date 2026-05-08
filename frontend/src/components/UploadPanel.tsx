import { FileUp, Play } from "lucide-react";
import type { ChangeEvent } from "react";
import type { ScanMode } from "../types";

interface UploadPanelProps {
  file: File | null;
  scanMode: ScanMode;
  isRunning: boolean;
  onFileChange: (file: File | null) => void;
  onScanModeChange: (scanMode: ScanMode) => void;
  onRun: () => void;
}

export function UploadPanel({
  file,
  scanMode,
  isRunning,
  onFileChange,
  onScanModeChange,
  onRun,
}: UploadPanelProps) {
  function handleFileInput(event: ChangeEvent<HTMLInputElement>) {
    onFileChange(event.target.files?.[0] ?? null);
  }

  return (
    <section className="uploadPanel" aria-label="Upload controls">
      <label className="fileDrop">
        <input
          type="file"
          accept="application/pdf"
          onChange={handleFileInput}
          disabled={isRunning}
        />
        <span className="fileDropIcon" aria-hidden="true">
          <FileUp size={24} strokeWidth={1.9} />
        </span>
        <span className="fileDropText">
          <strong>{file?.name ?? "Choose a PDF"}</strong>
          <span>PDF only</span>
        </span>
      </label>

      <div className="segmentedControl" aria-label="Scan mode">
        <button
          type="button"
          className={scanMode === "focused" ? "active" : ""}
          onClick={() => onScanModeChange("focused")}
          disabled={isRunning}
        >
          Focused
        </button>
        <button
          type="button"
          className={scanMode === "deep" ? "active" : ""}
          onClick={() => onScanModeChange("deep")}
          disabled={isRunning}
        >
          Deep Scan
        </button>
      </div>

      <button
        type="button"
        className="runButton"
        onClick={onRun}
        disabled={!file || isRunning}
      >
        <Play size={18} fill="currentColor" strokeWidth={2} />
        <span>{isRunning ? "Running" : "Run"}</span>
      </button>
    </section>
  );
}
