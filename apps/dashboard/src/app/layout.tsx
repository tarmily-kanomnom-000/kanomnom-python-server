import type { Metadata, Viewport } from "next";
import "./globals.css";
import { karla } from "@/app/fonts";
import { MenuBar } from "@/components/menu-bar";

export const metadata: Metadata = {
  title: "Ka-Nom Nom Dashboard",
  description: "Internal dashboard for managing Ka-Nom Nom data and workflows.",
  manifest: "/manifest.json",
};

export const viewport: Viewport = {
  themeColor: "#111827",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className={`${karla.className} bg-neutral-100`}>
        <div className="flex min-h-screen flex-col">
          <MenuBar />
          <div className="flex-1">{children}</div>
        </div>
      </body>
    </html>
  );
}
