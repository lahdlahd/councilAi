import type { Metadata } from "next";
import { IBM_Plex_Mono, IBM_Plex_Sans, IBM_Plex_Serif } from "next/font/google";
import "./globals.css";

// An engineered, institutional type system — IBM Plex was designed as a corporate
// typeface family, which reads "enterprise trading software" rather than crypto.
const sans = IBM_Plex_Sans({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-plex-sans",
});
const mono = IBM_Plex_Mono({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  variable: "--font-plex-mono",
});
const serif = IBM_Plex_Serif({
  subsets: ["latin"],
  weight: ["400", "600"],
  variable: "--font-plex-serif",
});

export const metadata: Metadata = {
  title: "Council — Autonomous AI Investment Committee",
  description: "Five AI agents analyze live markets, debate, vote, and decide — in the open.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${sans.variable} ${mono.variable} ${serif.variable}`}>
      <body className="font-sans antialiased">{children}</body>
    </html>
  );
}
