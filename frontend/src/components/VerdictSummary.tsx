import type { FactCheckReport } from "../types";

interface VerdictSummaryProps {
  summary: FactCheckReport["summary"];
}

export function VerdictSummary({ summary }: VerdictSummaryProps) {
  const items = [
    { label: "Total", value: summary.total, tone: "total" },
    { label: "Verified", value: summary.verified, tone: "verified" },
    { label: "Inaccurate", value: summary.inaccurate, tone: "inaccurate" },
    {
      label: "Unsupported",
      value: summary.false_or_unsupported,
      tone: "unsupported",
    },
  ];

  return (
    <section className="verdictSummary" aria-label="Verdict summary">
      {items.map((item) => (
        <div className={`summaryMetric ${item.tone}`} key={item.label}>
          <span>{item.label}</span>
          <strong>{item.value}</strong>
        </div>
      ))}
    </section>
  );
}
