import { ApiStatus } from "@dakar-wifi/ui";

const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export default function HomePage() {
  return (
    <main className="mx-auto flex max-w-4xl flex-col gap-6 px-6 py-10">
      <header>
        <h1 className="text-2xl font-bold">Dakar WiFi — Back-office</h1>
        <p className="text-sm opacity-70">Administration municipale</p>
      </header>

      <section className="rounded-lg border-2 border-amber-500 bg-amber-50 p-4">
        <h2 className="font-bold text-amber-900">Squelette — Phase 1</h2>
        <p className="mt-1 text-sm text-amber-900">
          Les écrans d’exploitation (sites, zones, offres, finance) arrivent à partir de la phase 2.
          L’authentification interne passe pour l’instant par l’administration Django.
        </p>
      </section>

      <section className="rounded-lg border border-black/10 bg-white p-4">
        <h2 className="mb-3 font-bold">État du service</h2>
        <ApiStatus apiBaseUrl={apiBaseUrl} />
      </section>

      <section className="rounded-lg border border-black/10 bg-white p-4">
        <h2 className="mb-3 font-bold">Accès</h2>
        <ul className="flex flex-col gap-2 text-sm">
          <li>
            <a className="text-[var(--color-brand)] underline" href={`${apiBaseUrl}/admin/`}>
              Administration Django
            </a>
          </li>
          <li>
            <a className="text-[var(--color-brand)] underline" href={`${apiBaseUrl}/api/v1/docs/`}>
              Documentation de l’API (OpenAPI)
            </a>
          </li>
        </ul>
      </section>
    </main>
  );
}
