import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import "./ui.css";
import { AuthProvider } from "@/components/AuthContext";
import { GoogleOAuthProvider } from "@react-oauth/google";
import { CursorGlow } from "@/components/CursorGlow";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Taxyn | AI-Powered Indian Compliance Document Automation",
  description: "Extract structured data from Invoices, GST Returns, and Bank Statements with 99% accuracy.",
};

// Load from environment variable (ensure it starts with NEXT_PUBLIC_ in your frontend/.env)
const GOOGLE_CLIENT_ID = process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID || "";

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className={`${geistSans.variable} ${geistMono.variable}`}>
        <GoogleOAuthProvider clientId={GOOGLE_CLIENT_ID}>
          <AuthProvider>
            <CursorGlow />
            <div className="app-content">{children}</div>
          </AuthProvider>
        </GoogleOAuthProvider>
      </body>
    </html>
  );
}
