export const API_BASE = (
  process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000"
).replace(/\/+$/, "");

export type ClaimListItem = {
  id: number;
  status: ClaimStatus;
  file: string;
  company_name: string | null;
  created_at: string;
  violation_count: number;
};

export type ClaimStatus =
  | "pending"
  | "processing"
  | "compliant"
  | "non_compliant"
  | "failed";

export type Violation = {
  law_id: number;
  title: string;
  chapter: string | null;
  page: number | null;
  type: string;
  reason: string;
  severity: "low" | "medium" | "high";
  evidence: string;
  article_text: string;
};

export type Report = {
  status: "compliant" | "non_compliant";
  claim_summary: {
    company_name?: string;
    subject?: string;
    amount?: string;
    date?: string;
  };
  violations: Violation[];
  recommendation: string;
  retrieved_law_ids: number[];
};

export type ClaimDetail = {
  id: number;
  status: ClaimStatus;
  file: string;
  company_name: string | null;
  created_at: string;
  parsed_chars: number;
  extracted: Record<string, string> | null;
  report: Report | null;
  violations: { law_id: number; reason: string; severity: string }[];
};

async function json<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    throw new Error(detail.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

export async function listClaims(): Promise<ClaimListItem[]> {
  return json(await fetch(`${API_BASE}/api/claims`, { cache: "no-store" }));
}

export async function getClaim(id: number): Promise<ClaimDetail> {
  return json(await fetch(`${API_BASE}/api/claims/${id}`, { cache: "no-store" }));
}

export async function uploadClaim(file: File): Promise<{ id: number }> {
  const form = new FormData();
  form.append("file", file);
  return json(
    await fetch(`${API_BASE}/api/claims/upload`, { method: "POST", body: form })
  );
}

export async function checkClaim(id: number): Promise<{ id: number }> {
  return json(
    await fetch(`${API_BASE}/api/claims/${id}/check`, { method: "POST" })
  );
}

export type KbStats = { total: number; embedded: number; sources: string[] };

export async function getKbStats(): Promise<KbStats> {
  return json(await fetch(`${API_BASE}/api/laws/stats`, { cache: "no-store" }));
}

export async function buildKb(): Promise<{ embedded: number }> {
  return json(await fetch(`${API_BASE}/api/admin/build`, { method: "POST" }));
}

export const STATUS_LABEL: Record<ClaimStatus, string> = {
  pending: "بانتظار الفحص",
  processing: "جارٍ الفحص",
  compliant: "متوافقة",
  non_compliant: "غير متوافقة",
  failed: "فشل الفحص",
};
