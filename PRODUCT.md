# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Citoyens dakarois qui s'authentifient sur un portail captif, souvent en extérieur,
sur un Android d'entrée de gamme et un mini-navigateur Wi-Fi. Agents municipaux
et partenaires qui administrent sites, offres, finance et incidents.

## Product Purpose

Donner un accès Wi-Fi public (gratuit, payant ou par coupon) sous souveraineté
de la Ville de Dakar, avec OTP, conditions versionnées et activation réseau.

## Positioning

La Ville est l'opérateur du service ; OpenWISP reste un système externe
(adaptateur, pas un fork). Le portail ne fait jamais confiance à une zone, un
prix ou une offre venant de l'URL.

## Operating Context

Portail captif Astro (`apps/captive-portal`), API Django, back-office Next.js.
Identité officielle : [mairie de Dakar](https://mairiedakar.sn/). Cahier des
charges v1.2. Scène d'usage : place publique, soleil, une main.

## Capabilities and Constraints

- Budget JS initial 150 Ko gzip, polices système uniquement (ADR-0005, §12.1).
- Logo et couleurs fournis par la Ville, pas inventés (§2.2).
- i18n fr / wo / en ; le français est la référence fonctionnelle.
- Phase 7 (paiements réels) bloquée tant que les sandboxes ne sont pas validées.

## Brand Commitments

- Nom : Dakar WiFi. SSID : DAKAR-WIFI.
- Armoiries et lockup officiels de la Ville de Dakar (fichiers fournis le
  20 août 2026) : `apps/captive-portal/public/logo-ville-dakar.png`.
- Référence d'identité : https://mairiedakar.sn/
- Palette extraite des armoiries : bleu royal, or, rouge phare, vert laurier.
  *(inféré des assets officiels, pas d'une charte PDF.)*

## Evidence on Hand

Logos officiels livrés par le commanditaire. Pas de charte graphique PDF ni
de polices institutionnelles à auto-héberger.

## Product Principles

1. Reconnaissable comme un service de la Ville, pas comme une app privée.
2. Lisible au soleil, actionnable d'une main, en trois écrans maximum.
3. Le français d'abord ; wolof et anglais sans allonger le parcours.
4. Ne jamais inventer un logo, un tarif ou une preuve municipale.

## Accessibility & Inclusion

Contraste AA, zoom autorisé dans le mini-navigateur, cibles tactiles larges,
parcours compréhensible sans texte long (pictogrammes, i18n courte).
