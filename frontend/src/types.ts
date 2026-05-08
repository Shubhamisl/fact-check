export type ScanMode = "focused" | "deep";

export type VerdictLabel = "Verified" | "Inaccurate" | "False / Unsupported";

export type ConfidenceLabel = "High" | "Medium" | "Low";

export interface ExtractedClaim {
  id: string;
  text: string;
  page_number: number | null;
  claim_type: string;
  topic: string;
  importance: "high" | "medium" | "low";
}

export interface EvidenceSource {
  title: string;
  url: string;
  snippet: string;
  published_date: string | null;
  query: string;
}

export interface ClaimVerdict {
  claim: ExtractedClaim;
  verdict: VerdictLabel;
  corrected_fact: string | null;
  confidence: ConfidenceLabel;
  reasoning: string;
  sources: EvidenceSource[];
  search_queries: string[];
}

export interface FactCheckReport {
  file_name: string;
  scan_mode: ScanMode;
  summary: Record<string, number>;
  claims: ClaimVerdict[];
}
