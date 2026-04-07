import "./globals.css";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Find Your Job",
  description: "Vercel frontend for the Find Your Job multi-agent platform."
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
