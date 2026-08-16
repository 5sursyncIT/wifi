# ADR-0005 — Budget JavaScript du portail captif

- Statut : **Acceptée** — option 2 retenue par le commanditaire le 2026-08-16
- Date : 2026-08-16
- Source : cahier des charges v1.1 §12.1, §14
- Amende : [ADR-0002](0002-stack-monorepo.md)

## Contexte

Le §12.1 fixe un budget de **150 Ko de JavaScript initial compressé** pour le portail
captif, au service d'une exigence fonctionnelle : rester utilisable sur un Android
d'entrée de gamme et un réseau lent, dans un mini-navigateur captif.

La mesure a été faite en Phase 1 sur le build réel (script
[`scripts/check-bundle-budget.mjs`](../../scripts/check-bundle-budget.mjs), qui lit le HTML
prérendu et somme le gzip de tous les scripts référencés) :

| Contenu de la page | Scripts | Poids gzip |
|---|---:|---:|
| Page réelle (en-tête, statut API, pied de page) | 7 | **169,9 Ko** |
| Page réduite à un seul `<h1>`, aucun composant client | 6 | **169,0 Ko** |

Le code applicatif pèse donc moins de 1 Ko : **les 169 Ko sont le plancher structurel
de Next.js 16 + React 19**. Aucun réglage de configuration ne le supprime — l'App Router
expédie son runtime client pour l'hydratation même sans composant `"use client"`.

La cible de 150 Ko est donc inatteignable avec la stack recommandée au §5.2,
avant même d'avoir écrit un seul écran fonctionnel.

## Options

1. **Réviser la cible du §12.1** vers ~200 Ko et assumer le surcoût réseau.
   Coût : sur un lien 3G lent (~400 kbit/s utiles), 170 Ko représentent environ
   3 à 4 secondes de téléchargement JavaScript, avant exécution sur un processeur d'entrée
   de gamme. L'exigence « moins de 2 secondes » du §12.1 devient hors d'atteinte.

2. **Changer la stack du seul portail captif** (le back-office reste sur Next.js).
   Le portail est une surface réduite : quelques écrans, des formulaires, un statut.
   Un rendu serveur avec JavaScript minimal (gabarits Django servis par l'API métier,
   ou Astro/Preact) situe le poids initial entre 10 et 40 Ko.
   Coût : deux chaînes front-end à maintenir, `packages/ui` non partageable entre les deux.

3. **Statu quo** : conserver Next.js et le budget à 150 Ko, en acceptant que le
   contrôle CI soit rouge en permanence. Non retenu — un contrôle qui échoue toujours
   cesse d'être lu.

## Décision

**Option 2.** Le portail captif passe sur **Astro** en sortie statique ; le back-office
reste sur Next.js. Décision prise avant la Phase 2, avant donc l'écriture des premiers
écrans réels — les changer de stack après coup aurait coûté leur réécriture.

Mesures après migration, même méthode et même script qu'avant :

| Application | JavaScript initial | Page complète | Budget |
|---|---:|---:|---|
| Portail captif (Astro) | **0,6 Ko gzip** | 3,9 Ko gzip | 150 Ko — tenu |
| Back-office (Next.js 16) | 171,7 Ko gzip | 4,5 Ko gzip | non soumis |

Le portail est passé de 169,9 Ko à 0,6 Ko de JavaScript. Astro n'expédie aucun runtime
de framework : la page est du HTML, et le seul script est le code métier compilé
(l'appel au healthcheck), intégré en ligne dans le HTML.

## Règles qui découlent de la décision

- Le portail reste en sortie statique. Toute interactivité s'écrit d'abord en TypeScript
  simple ; une île de framework (Preact) n'est introduite que si un écran le justifie
  réellement, et l'ajout se mesure avec le script de budget.
- Le back-office n'est pas soumis au budget du §12.1 : usage bureau, réseau d'entreprise.
- `packages/api-client` reste partagé par les deux applications — c'est lui qui porte la
  sécurité de type sur le contrat. `packages/ui` (React) ne sert plus que le back-office.
- Le contrôle CI du budget est réglé sur la cible réelle de 150 Ko, plus sur un garde-fou.

## Conséquences

- Deux chaînes front-end coexistent dans le dépôt. Coût accepté : le portail est de loin
  la plus simple des deux, et sa simplicité est précisément l'objectif.
- Le risque R18 est ramené de « élevé » à « faible » ; R17 (mini-navigateurs captifs)
  reste ouvert, mais sans le handicap du poids.
- [ADR-0002](0002-stack-monorepo.md) est amendé en conséquence.
- La PWA du §3.2 reste réalisable : sortie statique et service worker sans contrainte.
