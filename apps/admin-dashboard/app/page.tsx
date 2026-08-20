import { ApiStatus } from "@dakar-wifi/ui";

const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export default function HomePage() {
  return (
    <main className="mx-auto flex max-w-4xl flex-col gap-6 px-6 py-10">
      <header className="flex items-center gap-4">
        <img
          src="/logo-ville-dakar.png"
          alt="Ville de Dakar"
          width="200"
          height="88"
          className="h-12 w-auto"
        />
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Dakar WiFi — Back-office</h1>
          <p className="text-sm text-muted">Administration municipale</p>
        </div>
      </header>

      <div className="flex h-1.5 overflow-hidden rounded-full" aria-hidden="true">
        <span className="flex-1 bg-brand" />
        <span className="flex-1 bg-gold" />
        <span className="flex-1 bg-danger" />
      </div>

      <nav className="rounded-xl border border-black/8 bg-white p-4 shadow-[0_4px_16px_rgba(0,45,102,0.06)]">
        <h2 className="mb-3 font-bold">Exploitation</h2>
        <a className="font-medium text-brand underline" href="/sites">
          Sites et points d’accès
        </a>
      </nav>

      <section className="rounded-xl border border-black/8 bg-white p-4 shadow-[0_4px_16px_rgba(0,45,102,0.06)]">
        <h2 className="mb-3 font-bold">État du service</h2>
        <ApiStatus apiBaseUrl={apiBaseUrl} />
      </section>

      <section className="rounded-xl border border-black/8 bg-white p-4 shadow-[0_4px_16px_rgba(0,45,102,0.06)]">
        <h2 className="mb-3 font-bold">Accès</h2>
        <ul className="flex flex-col gap-2 text-sm">
          <li>
            <a className="font-medium text-brand underline" href={`${apiBaseUrl}/admin/`}>
              Administration Django
            </a>
          </li>
          <li>
            <a className="font-medium text-brand underline" href={`${apiBaseUrl}/api/v1/docs/`}>
              Documentation de l’API (OpenAPI)
            </a>
          </li>
        </ul>
      </section>
    </main>
  );
}
