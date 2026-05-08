import { Fragment, useState } from "react";
import type { ClaimVerdict, VerdictLabel } from "../types";
import { ClaimDetails } from "./ClaimDetails";

interface ResultsTableProps {
  claims: ClaimVerdict[];
}

function verdictTone(verdict: VerdictLabel) {
  if (verdict === "Verified") {
    return "verified";
  }

  if (verdict === "Inaccurate") {
    return "inaccurate";
  }

  return "unsupported";
}

export function ResultsTable({ claims }: ResultsTableProps) {
  const [expandedClaimId, setExpandedClaimId] = useState<string | null>(null);

  function toggleClaim(claimId: string) {
    setExpandedClaimId((current) => (current === claimId ? null : claimId));
  }

  return (
    <div className="tableShell">
      <table className="resultsTable">
        <thead>
          <tr>
            <th>Verdict</th>
            <th>Claim</th>
            <th>Correction</th>
            <th>Confidence</th>
            <th>Sources</th>
          </tr>
        </thead>
        <tbody>
          {claims.map((claimVerdict) => {
            const claimId = claimVerdict.claim.id;
            const isExpanded = expandedClaimId === claimId;

            return (
              <Fragment key={claimId}>
                <tr
                  className={isExpanded ? "expanded" : ""}
                  onClick={() => toggleClaim(claimId)}
                  tabIndex={0}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" || event.key === " ") {
                      event.preventDefault();
                      toggleClaim(claimId);
                    }
                  }}
                >
                  <td data-label="Verdict">
                    <span
                      className={`verdictBadge ${verdictTone(
                        claimVerdict.verdict,
                      )}`}
                    >
                      {claimVerdict.verdict}
                    </span>
                  </td>
                  <td data-label="Claim">
                    <div className="claimCell">
                      <strong>{claimVerdict.claim.text}</strong>
                      <span>
                        {claimVerdict.claim.topic} - Page{" "}
                        {claimVerdict.claim.page_number ?? "n/a"}
                      </span>
                    </div>
                  </td>
                  <td data-label="Correction">
                    {claimVerdict.corrected_fact ?? "No correction"}
                  </td>
                  <td data-label="Confidence">{claimVerdict.confidence}</td>
                  <td data-label="Sources">{claimVerdict.sources.length}</td>
                </tr>
                {isExpanded ? (
                  <tr className="detailsRow">
                    <td colSpan={5}>
                      <ClaimDetails verdict={claimVerdict} />
                    </td>
                  </tr>
                ) : null}
              </Fragment>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
