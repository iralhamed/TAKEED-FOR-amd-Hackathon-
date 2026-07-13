"use client";

import { useRouter } from "next/navigation";
import { useRef, useState } from "react";
import { checkClaim, uploadClaim } from "@/lib/api";

const STAGES = [
  "رفع الملف",
  "استخراج النص من المستند",
  "البحث في الأنظمة ذات الصلة",
  "توليد تقرير الامتثال",
];

export default function UploadPage() {
  const router = useRouter();
  const [file, setFile] = useState<File | null>(null);
  const [dragging, setDragging] = useState(false);
  const [stage, setStage] = useState(-1); // -1 = idle
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const busy = stage >= 0;

  function pick(f: File | null | undefined) {
    if (!f) return;
    if (!f.name.toLowerCase().endsWith(".pdf")) {
      setError("يُقبل ملف PDF فقط.");
      return;
    }
    setError(null);
    setFile(f);
  }

  async function submit() {
    if (!file) return;
    setError(null);
    try {
      setStage(0);
      const { id } = await uploadClaim(file);
      setStage(2); // uploaded + parsed
      const advance = setTimeout(() => setStage(3), 2500);
      await checkClaim(id);
      clearTimeout(advance);
      router.push(`/claims/${id}`);
    } catch (e) {
      setError((e as Error).message);
      setStage(-1);
    }
  }

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      <h1 className="text-xl font-bold text-slate-800">رفع مطالبة جديدة</h1>

      {!busy && (
        <>
          <div
            onDragOver={(e) => {
              e.preventDefault();
              setDragging(true);
            }}
            onDragLeave={() => setDragging(false)}
            onDrop={(e) => {
              e.preventDefault();
              setDragging(false);
              pick(e.dataTransfer.files?.[0]);
            }}
            onClick={() => inputRef.current?.click()}
            className={`cursor-pointer rounded-2xl border-2 border-dashed p-12 text-center transition ${
              dragging
                ? "border-emerald-400 bg-emerald-50"
                : "border-slate-300 bg-white hover:border-emerald-300"
            }`}
          >
            <div className="text-4xl mb-3">📄</div>
            <p className="text-slate-600 font-medium">
              اسحب ملف المطالبة (PDF) هنا أو اضغط للاختيار
            </p>
            {file && (
              <p className="mt-3 text-sm text-emerald-700">
                الملف المحدد: {file.name}
              </p>
            )}
            <input
              ref={inputRef}
              type="file"
              accept="application/pdf"
              className="hidden"
              onChange={(e) => pick(e.target.files?.[0])}
            />
          </div>

          {error && <p className="text-red-600 text-sm">{error}</p>}

          <button
            onClick={submit}
            disabled={!file}
            className="w-full bg-emerald-600 hover:bg-emerald-700 disabled:bg-slate-300 text-white font-medium py-3 rounded-xl transition"
          >
            بدء الفحص
          </button>
        </>
      )}

      {busy && (
        <div className="bg-white rounded-2xl border border-slate-200 p-8">
          <p className="text-center text-slate-600 font-medium mb-6">
            جارٍ التحليل…
          </p>
          <ol className="space-y-4">
            {STAGES.map((label, i) => {
              const done = stage > i;
              const active = stage === i || (i <= stage);
              const current = i === stage || (i < stage);
              return (
                <li key={i} className="flex items-center gap-3">
                  <span
                    className={`flex items-center justify-center w-7 h-7 rounded-full text-sm ${
                      done
                        ? "bg-emerald-600 text-white"
                        : current
                        ? "bg-amber-400 text-white animate-pulse"
                        : "bg-slate-200 text-slate-400"
                    }`}
                  >
                    {done ? "✓" : i + 1}
                  </span>
                  <span
                    className={active ? "text-slate-800" : "text-slate-400"}
                  >
                    {label}
                  </span>
                </li>
              );
            })}
          </ol>
        </div>
      )}
    </div>
  );
}
