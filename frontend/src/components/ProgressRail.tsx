import type { CSSProperties } from "react";

const STAGES = [
  "Extract text",
  "Read scanned pages",
  "Extract claims",
  "Search evidence",
  "Finalize report",
];

interface ProgressRailProps {
  isRunning: boolean;
}

export function ProgressRail({ isRunning }: ProgressRailProps) {
  return (
    <section
      className={`progressRail ${isRunning ? "isRunning" : ""}`}
      aria-label="Fact-check progress"
      aria-busy={isRunning}
    >
      {STAGES.map((stage, index) => (
        <div
          className="progressStage"
          key={stage}
          style={{ "--stage-index": index } as CSSProperties}
        >
          <span className="stageDot" aria-hidden="true" />
          <span>{stage}</span>
        </div>
      ))}
    </section>
  );
}
