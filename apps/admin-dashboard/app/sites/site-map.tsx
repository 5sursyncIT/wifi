"use client";

import type { PublicSite } from "@dakar-wifi/api-client";
import { useEffect, useRef } from "react";

const ACCESS_MODE_COLOR: Record<string, string> = {
  free: "#0b6b5b",
  paid: "#8a4b0b",
  sponsored: "#4b3f8a",
  hybrid: "#0b5b8a",
};

function markerColor(site: PublicSite): string {
  return ACCESS_MODE_COLOR[site.access_modes[0] ?? ""] ?? "#4a5c58";
}

/**
 * OpenStreetMap view of the published sites (cahier des charges §8.9).
 *
 * Leaflet and its cluster plugin touch `window`, so they are imported inside the
 * effect rather than at module scope, which keeps them out of the server render.
 */
export function SiteMap({ sites }: { sites: PublicSite[] }) {
  const container = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!container.current || sites.length === 0) return;

    let cleanup = () => {};
    let cancelled = false;

    void (async () => {
      const L = (await import("leaflet")).default;
      await import("leaflet.markercluster");
      await import("leaflet/dist/leaflet.css");
      await import("leaflet.markercluster/dist/MarkerCluster.css");
      await import("leaflet.markercluster/dist/MarkerCluster.Default.css");
      if (cancelled || !container.current) return;

      const map = L.map(container.current).setView([14.6928, -17.4467], 12);
      L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        attribution: "&copy; contributeurs OpenStreetMap",
        maxZoom: 19,
      }).addTo(map);

      // Clustering keeps the map readable as the pilot grows from 20 to 100+ sites.
      const cluster = L.markerClusterGroup();
      for (const site of sites) {
        const marker = L.circleMarker([Number(site.latitude), Number(site.longitude)], {
          radius: 9,
          color: markerColor(site),
          fillColor: markerColor(site),
          fillOpacity: 0.8,
          weight: 2,
        });
        marker.bindPopup(
          `<strong>${site.name}</strong><br>${site.address}<br>` +
            `${site.hotspot_count} borne(s) — ${site.status}`,
        );
        cluster.addLayer(marker);
      }
      map.addLayer(cluster);
      map.fitBounds(cluster.getBounds(), { padding: [40, 40], maxZoom: 15 });

      cleanup = () => map.remove();
    })();

    return () => {
      cancelled = true;
      cleanup();
    };
  }, [sites]);

  if (sites.length === 0) {
    return (
      <p className="rounded-lg border border-black/10 bg-white p-4 text-sm">
        Aucun site géolocalisé et publié. Renseignez les coordonnées dans l’administration.
      </p>
    );
  }

  return (
    <div
      ref={container}
      className="h-[420px] w-full rounded-lg border border-black/10"
      role="application"
      aria-label="Carte des sites Wi-Fi"
    />
  );
}
