import type { Metadata } from "next";
import { Suspense } from "react";
import AppShell from "./components/AppShell";
import "./globals.css";

export const metadata: Metadata = {
  title: "Reclaim (synthetic demo)",
  description: "Evidence-first denial recovery — SYNTHETIC DEMO DATA only.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <Suspense fallback={null}>
          <AppShell>{children}</AppShell>
        </Suspense>
      </body>
    </html>
  );
}
