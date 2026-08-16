import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Dakar WiFi — Back-office",
  description: "Administration de la plateforme Wi-Fi public de la Ville de Dakar",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="fr">
      <body className="min-h-dvh antialiased">{children}</body>
    </html>
  );
}
