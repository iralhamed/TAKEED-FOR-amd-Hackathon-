"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import {
  ClaimDetail,
  Violation,
  checkClaim,
  getClaim,
} from "@/lib/api";

const SEVERITY: Record<string, { label: string; cls: string }> = {
  high: { label: "عالية", cls: "bg-red-100 text-red-700" },
  medium: { label: "متوسطة", cls: "bg-amber-100 text-amber-700" },
  low: { label: "منخفضة", cls: "bg-slate-100 text-slate-600" },
};

function Field({ label, value }: { label: string; value?: string | null }) {
  if (!value) return null;
  return (
    <div>
      <span className="text-slate-400">{label}: </span>
      <span className="text-slate-700">{value}</span>
    </div>
  );
}

function ViolationCard({ v, index }: { v: Violation; index: number }) {
  const sev = SEVERITY[v.severity] ?? SEVERITY.medium;
  return (
    <div className="bg-white rounded-xl border border-slate-200 p-5">
      <div className="flex items-start justify-between gap-3">
        <h3 className="font-bold text-slate-800">
          {index + 1}. {v.type}
        </h3>
        <span className={`px-2.5 py-1 rounded-full text-xs font-medium ${sev.cls}`}>
          الخطورة: {sev.label}
        </span>
      </div>
      <p className="mt-3 text-sm text-slate-700 leading-relaxed">
        <span className="text-slate-400">السبب: </span>
        {v.reason}
      </p>
      {v.evidence && (
        <p className="mt-2 text-sm text-slate-500 bg-slate-50 rounded-lg p-3 border-r-2 border-slate-300">
          «{v.evidence}»
        </p>
      )}
      <div className="mt-3 flex flex-wrap gap-x-6 gap-y-1 text-xs text-slate-500">
        <span>المادة: {v.title}</span>
        {v.chapter && <span>الباب: {v.chapter}</span>}
        {v.page != null && <span>الصفحة: {v.page}</span>}
      </div>
    </div>
  );
}

export default function ReportPage() {
  const params = useParams<{ id: string }>();
  const id = Number(params.id);
  const [claim, setClaim] = useState<ClaimDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [checking, setChecking] = useState(false);

  const load = useCallback(() => {
    getClaim(id)
      .then(setClaim)
      .catch((e) => setError(e.message));
  }, [id]);

  useEffect(load, [load]);

  async function runCheck() {
    setChecking(true);
    try {
      await checkClaim(id);
      load();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setChecking(false);
    }
  }

  if (error) return <p className="text-red-600">خطأ: {error}</p>;
  if (!claim) return <p className="text-slate-400">جارٍ التحميل…</p>;

  const report = claim.report;
  const compliant = report?.status === "compliant";

  return (
    <div className="space-y-6">
      <Link href="/" className="text-sm text-slate-400 hover:text-emerald-700">
        ← العودة للرئيسية
      </Link>

      {!report ? (
        <div className="bg-white rounded-2xl border border-slate-200 p-8 text-center">
          <p className="text-slate-600 mb-4">لم يتم فحص هذه المطالبة بعد.</p>
          <button
            onClick={runCheck}
            disabled={checking}
            className="bg-emerald-600 hover:bg-emerald-700 disabled:bg-slate-300 text-white px-6 py-2.5 rounded-xl"
          >
            {checking ? "جارٍ الفحص…" : "فحص الآن"}
          </button>
        </div>
      ) : (
        <>
          {/* Status banner */}
          <div
            className={`rounded-2xl p-6 border ${
              compliant
                ? "bg-emerald-50 border-emerald-200"
                : "bg-red-50 border-red-200"
            }`}
          >
            <div className="flex items-center justify-between flex-wrap gap-3">
              <div className="flex items-center gap-3">
                <span className="text-3xl">{compliant ? "🟢" : "🔴"}</span>
                <div>
                  <div
                    className={`text-xl font-bold ${
                      compliant ? "text-emerald-700" : "text-red-700"
                    }`}
                  >
                    {compliant ? "متوافقة" : "غير متوافقة"}
                  </div>
                  <div className="text-sm text-slate-500">
                    عدد المخالفات: {report.violations.length}
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Claim summary */}
          <div className="bg-white rounded-2xl border border-slate-200 p-6">
            <h2 className="font-bold text-slate-700 mb-3">بيانات المطالبة</h2>
            <div className="grid sm:grid-cols-2 gap-y-2 gap-x-6 text-sm">
              <Field label="الجهة" value={report.claim_summary.company_name} />
              <Field label="الموضوع" value={report.claim_summary.subject} />
              <Field label="المبلغ" value={report.claim_summary.amount} />
              <Field label="التاريخ" value={report.claim_summary.date} />
            </div>
          </div>

          {/* Violations */}
          {report.violations.length > 0 && (
            <div className="space-y-3">
              <h2 className="font-bold text-slate-700">المخالفات</h2>
              {report.violations.map((v, i) => (
                <ViolationCard key={i} v={v} index={i} />
              ))}
            </div>
          )}

          {/* Recommendation */}
          <div className="bg-sky-50 border border-sky-200 rounded-2xl p-6">
            <h2 className="font-bold text-sky-800 mb-2">التوصية</h2>
            <p className="text-sm text-sky-900 leading-relaxed">
              {report.recommendation}
            </p>
          </div>
        </>
      )}
    </div>
  );
}
