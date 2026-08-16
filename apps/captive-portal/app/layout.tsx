import type { Metadata, Viewport } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Dakar WiFi",
  description: "Accès Wi-Fi public de la Ville de Dakar",
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  // Captive mini-browsers must not zoom the layout away.
  maximumScale: 5,
  themeColor: "#0b6b5b",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="fr">
      <body className="min-h-dvh antialiased">{children}</body>
    </html>
  );
}
