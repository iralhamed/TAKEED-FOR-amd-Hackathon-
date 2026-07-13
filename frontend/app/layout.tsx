import type { Metadata } from "next";
import { Cairo } from "next/font/google";
import Link from "next/link";
import "./globals.css";

const cairo = Cairo({ subsets: ["arabic", "latin"], variable: "--font-cairo" });

export const metadata: Metadata = {
  title: "تأكيد — منصة التحقق من امتثال المطالبات",
  description: "أداة مساعدة لمراجعة امتثال المطالبات الحكومية للأنظمة واللوائح",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="ar" dir="rtl">
      <body
        className={`${cairo.variable} font-sans bg-slate-50 text-slate-800 min-h-screen flex flex-col`}
      >
        <header className="bg-white border-b border-slate-200">
          <div className="mx-auto max-w-5xl w-full px-6 py-4 flex items-center justify-between">
            <Link href="/" className="flex items-center gap-2">
              <span className="text-2xl font-bold text-emerald-700">تأكيد</span>
              <span className="text-sm text-slate-400 hidden sm:inline">
                التحقق من امتثال المطالبات
              </span>
            </Link>
            <nav className="flex items-center gap-5 text-sm">
              <Link href="/" className="hover:text-emerald-700">
                الرئيسية
              </Link>
              <Link href="/admin" className="text-slate-500 hover:text-emerald-700">
                لوحة الإدارة
              </Link>
            </nav>
          </div>
        </header>
        <main className="mx-auto max-w-5xl w-full px-6 py-8 flex-1">{children}</main>
        <footer className="mx-auto max-w-5xl w-full px-6 py-8 text-center text-xs text-slate-400">
          أداة لدعم اتخاذ القرار — القرار النهائي يعود للموظف المختص.
        </footer>
      </body>
    </html>
  );
}
