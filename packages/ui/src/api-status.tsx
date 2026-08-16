"use client";

import { createApiClient, type HealthResponse } from "@dakar-wifi/api-client";
import { useEffect, useState } from "react";

type State = { kind: "loading" } | { kind: "ok"; health: HealthResponse } | { kind: "error" };

/**
 * Live connectivity check against the real API.
 *
 * Never renders placeholder data: a screen that only shows static values would
 * violate rule 14 of the cahier des charges.
 */
export function ApiStatus({ apiBaseUrl }: { apiBaseUrl: string }) {
  const [state, setState] = useState<State>({ kind: "loading" });

  useEffect(() => {
    let cancelled = false;
    createApiClient({ baseUrl: apiBaseUrl })
      .health()
      .then((health) => {
        if (!cancelled) setState({ kind: "ok", health });
      })
      .catch(() => {
        if (!cancelled) setState({ kind: "error" });
      });
    return () => {
      cancelled = true;
    };
  }, [apiBaseUrl]);

  if (state.kind === "loading") {
    return <p aria-live="polite">Vérification du service…</p>;
  }

  if (state.kind === "error") {
    return (
      <p className="font-medium text-red-700" role="status">
        Service injoignable. Vérifiez que l’API est démarrée.
      </p>
    );
  }

  const { status, environment, version, checks } = state.health;
  return (
    <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm" role="status">
      <dt className="opacity-70">État</dt>
      <dd className="font-medium">{status}</dd>
      <dt className="opacity-70">Environnement</dt>
      <dd className="font-medium">{environment}</dd>
      <dt className="opacity-70">Version</dt>
      <dd className="font-medium">{version}</dd>
      <dt className="opacity-70">Base / cache</dt>
      <dd className="font-medium">
        {checks.database} / {checks.cache}
      </dd>
    </dl>
  );
}
