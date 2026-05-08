import type { FactCheckReport, ScanMode } from "./types";

export const API_BASE =
  import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

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
