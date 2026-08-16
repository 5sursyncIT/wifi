"use client";

import { createApiClient, type PublicSite } from "@dakar-wifi/api-client";
import { useEffect, useMemo, useState } from "react";

import { SiteMap } from "./site-map";

const ACCESS_MODE_LABEL: Record<string, string> = {
  free: "Gratuit",
  paid: "Payant",
  sponsored: "Sponsorisé",
  hybrid: "Hybride",
};

type State =
  | { kind: "loading" }
  | { kind: "ready"; sites: PublicSite[] }
  | { kind: "error" };

export function SitesView({ apiBaseUrl }: { apiBaseUrl: string }) {
  const [state, setState] = useState<State>({ kind: "loading" });
  const [mode, setMode] = useState<string>("all");

  useEffect(() => {
    let cancelled = false;
    createApiClient({ baseUrl: apiBaseUrl })
      .publicHotspots()
      .then((data) => {
        if (!cancelled) setState({ kind: "ready", sites: data.sites });
      })
      .catch(() => {
        if (!cancelled) setState({ kind: "error" });
      });
    return () => {
      cancelled = true;
    };
  }, [apiBaseUrl]);

  // Memoised so the derived lists below keep a stable reference between renders.
  const sites = useMemo(() => (state.kind === "ready" ? state.sites : []), [state]);
  const filtered = useMemo(
    () => (mode === "all" ? sites : sites.filter((site) => site.access_modes.includes(mode))),
    [sites, mode],
  );
  const modes = useMemo(
    () => [...new Set(sites.flatMap((site) => site.access_modes))].sort(),
    [sites],
  );

  if (state.kind === "loading") return <p>Chargement des sites…</p>;
  if (state.kind === "error") {
    return <p className="font-medium text-red-700">API injoignable. Vérifiez qu’elle est démarrée.</p>;
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center gap-2">
        <label htmlFor="mode" className="text-sm font-medium">
          Mode d’accès
        </label>
        <select
          id="mode"
          value={mode}
          onChange={(event) => setMode(event.target.value)}
          className="rounded border border-black/20 bg-white px-3 py-2 text-sm"
        >
          <option value="all">Tous ({sites.length})</option>
          {modes.map((value) => (
            <option key={value} value={value}>
              {ACCESS_MODE_LABEL[value] ?? value}
            </option>
          ))}
        </select>
      </div>

      <SiteMap sites={filtered} />

      <div className="overflow-x-auto rounded-lg border border-black/10 bg-white">
        <table className="w-full min-w-[36rem] text-sm">
          <caption className="sr-only">Sites Wi-Fi publiés</caption>
          <thead className="border-b border-black/10 text-left">
            <tr>
              <th scope="col" className="p-3">Site</th>
              <th scope="col" className="p-3">Adresse</th>
              <th scope="col" className="p-3">Modes</th>
              <th scope="col" className="p-3">Bornes</th>
              <th scope="col" className="p-3">État</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((site) => (
              <tr key={site.name} className="border-b border-black/5 last:border-0">
                <td className="p-3 font-medium">{site.name}</td>
                <td className="p-3">{site.address}</td>
                <td className="p-3">
                  {site.access_modes.map((m) => ACCESS_MODE_LABEL[m] ?? m).join(", ")}
                </td>
                <td className="p-3">{site.hotspot_count}</td>
                <td className="p-3">{site.status}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
