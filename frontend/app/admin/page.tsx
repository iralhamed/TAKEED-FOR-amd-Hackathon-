"use client";

import { useEffect, useState } from "react";
import { KbStats, buildKb, getKbStats } from "@/lib/api";

export default function AdminPage() {
  const [stats, setStats] = useState<KbStats | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [building, setBuilding] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  function load() {
    getKbStats()
      .then(setStats)
      .catch((e) => setError(e.message));
  }

  useEffect(load, []);

  async function build() {
    setBuilding(true);
    setMessage(null);
    try {
      const { embedded } = await buildKb();
      setMessage(
        embedded > 0
          ? `تم توليد المتجهات لـ ${embedded} مادة.`
          : "قاعدة المعرفة محدّثة — لا توجد مواد بانتظار المعالجة."
      );
      load();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBuilding(false);
    }
  }

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      <h1 className="text-xl font-bold text-slate-800">لوحة الإدارة</h1>
      <p className="text-sm text-slate-500">
        إدارة قاعدة المعرفة النظامية (الأنظمة واللوائح المرقمنة).
      </p>

      {error && <p className="text-red-600 text-sm">خطأ: {error}</p>}

      <div className="bg-white rounded-2xl border border-slate-200 p-6">
        <h2 className="font-bold text-slate-700 mb-4">حالة قاعدة المعرفة</h2>
        {!stats ? (
          <p className="text-slate-400">جارٍ التحميل…</p>
        ) : (
          <div className="grid grid-cols-2 gap-4">
            <div className="bg-slate-50 rounded-xl p-4 text-center">
              <div className="text-3xl font-bold text-slate-800">
                {stats.total}
              </div>
              <div className="text-xs text-slate-500 mt-1">مادة نظامية</div>
            </div>
            <div className="bg-slate-50 rounded-xl p-4 text-center">
              <div className="text-3xl font-bold text-emerald-700">
                {stats.embedded}
              </div>
              <div className="text-xs text-slate-500 mt-1">
                مادة مُفهرسة (متجهات)
              </div>
            </div>
          </div>
        )}
        {stats && stats.sources.length > 0 && (
          <div className="mt-4 text-xs text-slate-500">
            المصادر: {stats.sources.join("، ")}
          </div>
        )}
      </div>

      <div className="bg-white rounded-2xl border border-slate-200 p-6">
        <h2 className="font-bold text-slate-700 mb-2">بناء قاعدة المعرفة</h2>
        <p className="text-sm text-slate-500 mb-4">
          توليد المتجهات (embeddings) للمواد التي لم تُفهرس بعد. رقمنة الأنظمة
          الجديدة (عبر Claude) تُشغَّل من واجهة الأوامر للتحكم في الكلفة.
        </p>
        <button
          onClick={build}
          disabled={building}
          className="bg-emerald-600 hover:bg-emerald-700 disabled:bg-slate-300 text-white px-6 py-2.5 rounded-xl"
        >
          {building ? "جارٍ البناء…" : "بناء قاعدة المعرفة"}
        </button>
        {message && (
          <p className="mt-3 text-sm text-emerald-700">{message}</p>
        )}
      </div>
    </div>
  );
}
