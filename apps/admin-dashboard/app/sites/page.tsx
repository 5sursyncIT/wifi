import { SitesView } from "./sites-view";

const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export const metadata = {
  title: "Sites — Dakar WiFi",
};

export default function SitesPage() {
  return (
    <main className="mx-auto flex max-w-5xl flex-col gap-6 px-6 py-10">
      <header className="flex items-center gap-4">
        <img
          src="/logo-ville-dakar.png"
          alt="Ville de Dakar"
          width="200"
          height="88"
          className="h-10 w-auto"
        />
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Sites et points d’accès</h1>
          <p className="text-sm text-muted">
            Sites publiés et géolocalisés. La configuration se fait dans l’administration
            Django tant que les écrans dédiés ne sont pas livrés.
          </p>
        </div>
      </header>

      <div className="flex h-1.5 overflow-hidden rounded-full" aria-hidden="true">
        <span className="flex-1 bg-brand" />
        <span className="flex-1 bg-gold" />
        <span className="flex-1 bg-danger" />
      </div>

      <SitesView apiBaseUrl={apiBaseUrl} />
    </main>
  );
}
