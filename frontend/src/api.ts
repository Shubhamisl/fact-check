import type { FactCheckReport, ScanMode } from "./types";

export const API_BASE =
  import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

export interface FactCheckJob {
  status: "queued" | "running" | "complete" | "failed";
  progress: number;
  report?: FactCheckReport;
  error?: string;
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
    throw new Error(payload.detail ?? "Fact-check failed");
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
    throw new Error(payload.detail ?? "Could not start job");
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
    throw new Error(payload.detail ?? "Could not read job");
  }

  return response.json();
}
