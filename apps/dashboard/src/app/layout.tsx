import type { Metadata, Viewport } from "next";
import "./globals.css";
import { karla } from "@/app/fonts";
import { Providers } from "@/app/providers";
import { MenuBar } from "@/components/menu-bar";
import { GrocyOfflineBootstrap } from "@/components/pwa/grocy-offline-bootstrap";
import { ServiceWorkerRegistration } from "@/components/pwa/service-worker-registration";

export const metadata: Metadata = {
  title: "Ka-Nom Nom Dashboard",
  description: "Internal dashboard for managing Ka-Nom Nom data and workflows.",
  manifest: "/manifest.json",
  icons: {
    icon: "/logo.webp",
    apple: "/logo.webp",
  },
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
        <Providers>
          <GrocyOfflineBootstrap />
          <ServiceWorkerRegistration />
          <div className="flex min-h-screen flex-col">
            <MenuBar />
            <div className="flex-1">{children}</div>
          </div>
        </Providers>
      </body>
    </html>
  );
}
