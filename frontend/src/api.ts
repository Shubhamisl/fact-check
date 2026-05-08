import type { FactCheckReport, ScanMode } from "./types";

export const API_BASE =
  import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

export interface FactCheckJob {
  status: "queued" | "running" | "complete" | "failed";
  progress: number;
  report?: FactCheckReport;
  error?: string;
  error_details?: {
    type?: string;
    message?: string;
    cause_type?: string;
    cause_message?: string;
  };
}

function errorMessageFromPayload(payload: { detail?: unknown }): string {
  if (typeof payload.detail === "string") {
    return payload.detail;
  }
  if (
    payload.detail &&
    typeof payload.detail === "object" &&
    "message" in payload.detail
  ) {
    const detail = payload.detail as {
      message?: string;
      debug?: { type?: string; message?: string };
    };
    const debugText = detail.debug
      ? ` (${detail.debug.type ?? "Error"}: ${detail.debug.message ?? ""})`
      : "";
    return `${detail.message ?? "Fact-check failed"}${debugText}`;
  }
  return "Fact-check failed";
}

export function formatJobError(job: FactCheckJob): string {
  const base = job.error ?? "Fact-check failed. Please try again.";
  if (!job.error_details) {
    return base;
  }

  const type = job.error_details.type ?? "Error";
  const message = job.error_details.message ?? "";
  const cause =
    job.error_details.cause_type || job.error_details.cause_message
      ? `; cause ${job.error_details.cause_type ?? "Error"}: ${
          job.error_details.cause_message ?? ""
        }`
      : "";
  return `${base} (${type}: ${message}${cause})`;
}

export async function runFactCheck(
  file: File,
  scanMode: ScanMode,
): Promise<FactCheckReport> {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("scan_mode", scanMode);

  const response = await fetch(`${API_BASE}/api/fact-check`, {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    const payload = await response
      .json()
      .catch(() => ({ detail: "Fact-check failed" }));
    throw new Error(errorMessageFromPayload(payload));
  }

  return response.json();
}

export async function createFactCheckJob(
  file: File,
  scanMode: ScanMode,
  signal?: AbortSignal,
): Promise<string> {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("scan_mode", scanMode);

  const response = await fetch(`${API_BASE}/api/jobs`, {
    method: "POST",
    body: formData,
    signal,
  });

  if (!response.ok) {
    const payload = await response
      .json()
      .catch(() => ({ detail: "Could not start job" }));
    throw new Error(errorMessageFromPayload(payload));
  }

  const payload = (await response.json()) as { job_id?: string };
  if (!payload.job_id) {
    throw new Error("Could not start job");
  }

  return payload.job_id;
}

export async function getFactCheckJob(
  jobId: string,
  signal?: AbortSignal,
): Promise<FactCheckJob> {
  const response = await fetch(`${API_BASE}/api/jobs/${jobId}`, { signal });

  if (!response.ok) {
    const payload = await response
      .json()
      .catch(() => ({ detail: "Could not read job" }));
    throw new Error(errorMessageFromPayload(payload));
  }

  return response.json();
}
