"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import {
  ClaimListItem,
  ClaimStatus,
  STATUS_LABEL,
  listClaims,
} from "@/lib/api";

function StatusChip({ status }: { status: ClaimStatus }) {
  const styles: Record<ClaimStatus, string> = {
    compliant: "bg-emerald-100 text-emerald-700",
    non_compliant: "bg-red-100 text-red-700",
    processing: "bg-amber-100 text-amber-700",
    pending: "bg-slate-100 text-slate-600",
    failed: "bg-slate-200 text-slate-700",
  };
  const icon =
    status === "compliant" ? "✓" : status === "non_compliant" ? "✗" : "…";
  return (
    <span className={`px-3 py-1 rounded-full text-xs font-medium ${styles[status]}`}>
      {icon} {STATUS_LABEL[status]}
    </span>
  );
}

export default function Home() {
  const [claims, setClaims] = useState<ClaimListItem[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listClaims()
      .then(setClaims)
      .catch((e) => setError(e.message));
  }, []);

  return (
    <div className="space-y-8">
      <section className="bg-white rounded-2xl border border-slate-200 p-8 text-center">
        <h1 className="text-2xl font-bold text-slate-800">
          التحقق من امتثال المطالبات الحكومية
        </h1>
        <p className="mt-2 text-slate-500">
          ارفع مطالبة مقدمة من شركة ليتم فحصها آلياً مقابل الأنظمة واللوائح.
        </p>
        <Link
          href="/upload"
          className="inline-block mt-6 bg-emerald-600 hover:bg-emerald-700 text-white font-medium px-8 py-3 rounded-xl transition"
        >
          رفع مطالبة جديدة
        </Link>
      </section>

      <section>
        <h2 className="text-lg font-bold text-slate-700 mb-4">آخر المطالبات</h2>
        {error && (
          <p className="text-red-600 text-sm">تعذّر الاتصال بالخادم: {error}</p>
        )}
        {!claims && !error && <p className="text-slate-400">جارٍ التحميل…</p>}
        {claims && claims.length === 0 && (
          <p className="text-slate-400">لا توجد مطالبات بعد.</p>
        )}
        <div className="space-y-3">
          {claims?.map((c) => (
            <Link
              key={c.id}
              href={`/claims/${c.id}`}
              className="flex items-center justify-between bg-white rounded-xl border border-slate-200 px-5 py-4 hover:border-emerald-300 transition"
            >
              <div>
                <div className="font-medium text-slate-800">
                  {c.company_name || c.file}
                </div>
                <div className="text-xs text-slate-400 mt-1">
                  مطالبة #{c.id} ·{" "}
                  {new Date(c.created_at).toLocaleDateString("ar-SA")}
                  {c.violation_count > 0 && ` · ${c.violation_count} مخالفة`}
                </div>
              </div>
              <StatusChip status={c.status} />
            </Link>
          ))}
        </div>
      </section>
    </div>
  );
}
