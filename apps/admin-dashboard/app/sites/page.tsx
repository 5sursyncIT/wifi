import { SitesView } from "./sites-view";

const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export const metadata = {
  title: "Sites — Dakar WiFi",
};

export default function SitesPage() {
  return (
    <main className="mx-auto flex max-w-5xl flex-col gap-6 px-6 py-10">
      <header>
        <h1 className="text-2xl font-bold">Sites et points d’accès</h1>
        <p className="text-sm opacity-70">
          Sites publiés et géolocalisés. La configuration se fait dans l’administration
          Django tant que les écrans dédiés ne sont pas livrés.
        </p>
      </header>

      <SitesView apiBaseUrl={apiBaseUrl} />
    </main>
  );
}
