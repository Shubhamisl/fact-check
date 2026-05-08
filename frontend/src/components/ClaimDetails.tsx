import type { ClaimVerdict } from "../types";

interface ClaimDetailsProps {
  verdict: ClaimVerdict;
}

export function ClaimDetails({ verdict }: ClaimDetailsProps) {
  return (
    <div className="claimDetails">
      <div>
        <h3>Reasoning</h3>
        <p>{verdict.reasoning}</p>
      </div>

      {verdict.corrected_fact ? (
        <div>
          <h3>Corrected fact</h3>
          <p>{verdict.corrected_fact}</p>
        </div>
      ) : null}

      <div>
        <h3>Sources</h3>
        {verdict.sources.length > 0 ? (
          <ul className="sourceList">
            {verdict.sources.map((source) => (
              <li key={`${source.url}-${source.title}`}>
                <a href={source.url} target="_blank" rel="noreferrer">
                  {source.title}
                </a>
                <p>{source.snippet}</p>
              </li>
            ))}
          </ul>
        ) : (
          <p>No sources returned for this claim.</p>
        )}
      </div>
    </div>
  );
}
