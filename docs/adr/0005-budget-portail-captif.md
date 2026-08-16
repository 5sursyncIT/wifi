# ADR-0005 — Budget JavaScript du portail captif

- Statut : **Proposée — décision requise du commanditaire**
- Date : 2026-08-16
- Source : cahier des charges v1.1 §12.1, §14

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

En attente. Le garde-fou CI est provisoirement réglé à **175 Ko** : il ne valide pas la
cible, il empêche la dérive du code applicatif au-delà du plancher constaté.

La décision doit être prise **avant la Phase 2**, qui construit les premiers écrans réels
du portail : changer de stack après coup coûterait la réécriture de ces écrans.

## Conséquences

- Le §12.1 du cahier des charges porte une cible aujourd'hui non tenue ; l'écart est
  documenté ici plutôt que masqué par un relèvement silencieux du seuil.
- Le risque R17 (mini-navigateurs captifs) est aggravé par ce poids ; voir le registre
  des risques.
- Si l'option 2 est retenue, l'ADR-0002 devra être amendé.
