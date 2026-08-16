import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";

const inter = Inter({ subsets: ["latin"], variable: "--font-inter" });

export const metadata: Metadata = {
  title: "FinSentinel AI | Investigator Cockpit",
  description: "High-density investigation triage portal",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark">
      <body className={`${inter.variable} antialiased bg-slate-950 text-slate-50 overflow-hidden h-screen`}>
        {children}
      </body>
    </html>
  );
}
