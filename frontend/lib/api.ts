import type { AnalysisSnapshot, ProviderStatus } from "../types/analysis";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000/api/v1";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error(`API request failed (${response.status})`);
  }

  return (await response.json()) as T;
}

export function fetchLatestAnalysis(): Promise<AnalysisSnapshot> {
  return request<AnalysisSnapshot>("/analysis/latest");
}

export function generateAnalysis(): Promise<AnalysisSnapshot> {
  return request<AnalysisSnapshot>("/analysis/generate", { method: "POST" });
}

export function fetchProviderStatus(probe = false): Promise<ProviderStatus> {
  const query = probe ? "?probe=true" : "";
  return request<ProviderStatus>(`/providers/status${query}`);
}

export function setPriceOverride(price: number, source = "goldbach_context_menu"): Promise<{ status: string }> {
  return request<{ status: string }>("/price/override", {
    method: "POST",
    body: JSON.stringify({ price, source }),
  });
}
