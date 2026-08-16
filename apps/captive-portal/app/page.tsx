import { ApiStatus } from "@dakar-wifi/ui";

const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export default function HomePage() {
  return (
    <main className="mx-auto flex min-h-dvh max-w-md flex-col gap-6 px-5 py-8">
      <header className="flex items-center gap-3">
        {/* Neutral placeholder: no logo is invented before the City supplies one (§2.2). */}
        <div
          className="size-12 shrink-0 rounded-lg bg-[var(--color-brand)]"
          role="img"
          aria-label="Emplacement du logo officiel"
        />
        <div>
          <h1 className="text-xl font-bold">Dakar WiFi</h1>
          <p className="text-sm text-[var(--color-muted)]">Réseau DAKAR-WIFI</p>
        </div>
      </header>

      <section
        className="rounded-lg border-2 border-amber-500 bg-amber-50 p-4"
        aria-labelledby="phase-notice"
      >
        <h2 id="phase-notice" className="font-bold text-amber-900">
          Squelette — Phase 1
        </h2>
        <p className="mt-1 text-sm text-amber-900">
          Cet écran valide les fondations techniques. L’inscription par OTP arrive en phase 3, le
          choix d’offre et le paiement en phase 4.
        </p>
      </section>

      <section className="rounded-lg border border-black/10 p-4" aria-labelledby="service-status">
        <h2 id="service-status" className="mb-3 font-bold">
          État du service
        </h2>
        <ApiStatus apiBaseUrl={apiBaseUrl} />
      </section>

      <footer className="mt-auto text-xs text-[var(--color-muted)]">
        Ville de Dakar — plateforme en cours de développement
      </footer>
    </main>
  );
}
