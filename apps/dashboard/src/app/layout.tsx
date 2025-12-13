import type { Metadata } from "next";
import "./globals.css";
import { karla } from "@/app/fonts";

export const metadata: Metadata = {
  title: "Ka-Nom Nom Dashboard",
  description: "Internal dashboard for managing Ka-Nom Nom data and workflows.",
  manifest: "/manifest.json",
  themeColor: "#111827",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className={`${karla.className} min-h-screen bg-neutral-100`}>
        {children}
      </body>
    </html>
  );
}
