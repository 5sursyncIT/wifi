# ADR-0004 — Paiement par push serveur comme parcours nominal

- Statut : Acceptée
- Date : 2026-08-16
- Source : cahier des charges v1.1, §8.5 « Contrainte du mini-navigateur captif »

## Contexte

Le paiement a lieu majoritairement dans le mini-navigateur captif (CNA) d'Android/iOS,
qui ne peut pas ouvrir d'application tierce (deep link Wave/Orange Money) et dont la
fermeture interrompt le parcours. Une redirection classique vers une page de paiement
est donc structurellement fragile dans ce contexte.

## Décision

- Le parcours nominal est le **paiement par push initié côté serveur** : l'API demande au
  prestataire de déclencher la validation directement sur le téléphone du client ;
  le portail affiche un écran d'attente avec sondage du statut de la commande.
- La redirection vers une page hébergée est le **parcours de repli**, avec incitation à
  ouvrir le navigateur complet.
- L'interface `PaymentProvider` modélise les deux parcours dès la Phase 4 ;
  le `MockPaymentProvider` simule succès, refus, timeout et fermeture du mini-navigateur.
- La confirmation reste exclusivement webhook signé ou vérification serveur-à-serveur
  (règle 10 du cahier des charges) — le push ne change rien à cette règle.

## Conséquences

- La capacité push réelle de chaque prestataire est un **critère de sélection** vérifié
  en sandbox avant tout engagement (Phase 7, question 19 du §22).
- L'écran d'attente et le sondage de statut font partie du socle UX du portail (Phase 4).
- Le walled garden doit couvrir les domaines de repli (redirection) par zone (§13.2).

## Alternatives écartées

- **Redirection comme parcours principal** : taux d'échec élevé en CNA, sessions perdues.
- **Détection du CNA pour forcer le navigateur complet** : peu fiable, dégrade le parcours
  de tous les usagers ; conservée uniquement comme incitation dans le parcours de repli.
