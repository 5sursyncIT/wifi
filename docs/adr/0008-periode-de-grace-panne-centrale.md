# ADR-0008 — Période de grâce en cas de panne du système central

- Statut : Acceptée
- Date : 2026-08-20
- Source : cahier des charges v1.2, §4.3

## Contexte

Le cahier des charges demande, **avant la Phase 5**, de documenter si une continuité
d'exploitation locale est possible lorsque le système central (API métier, OpenWISP)
est injoignable : autorisations déjà valides, durée de grâce, dépendance au matériel.

Aucune passerelle ni point d'accès de production n'est encore choisi. Le laboratoire
Phase 5 utilise un NAS fictif (`0.0.0.0/0`) et un overlay Docker, pas une borne réelle.

## Décision

La continuité locale en cas de panne centrale **n'est pas une exigence du pilote**.
C'est un point d'étude, comme le §4.3 le formule.

Jusqu'à la validation modèle par modèle (§6.1) :

1. Un droit déjà actif côté RADIUS reste utilisable tant que la session NAS n'est pas
   coupée et que le quota du groupe n'est pas épuisé. Aucune « grâce » supplémentaire
   n'est promise au-delà de ce que la passerelle et FreeRADIUS font déjà.
2. Une **nouvelle** activation (gratuit ou payant) exige que l'API métier et OpenWISP
   soient joignables. L'outbox retarde l'activation, elle ne l'accorde pas hors-ligne.
3. UniFi/Ubiquiti et les passerelles OpenWrt seront évaluées séparément quand un
   modèle sera retenu. Le résultat (faisable / non faisable, durée de grâce) sera
   consigné en mise à jour de cet ADR, pas inventé aujourd'hui.

## Conséquences

- Le pilote ne vend pas de service « ça marche même si Dakar est coupée ».
- Les exploitants doivent traiter une panne OpenWISP comme un arrêt des nouvelles
  sessions, pas comme une coupure des sessions déjà autorisées — sous réserve du
  matériel.
- R12 du registre des risques reste ouvert jusqu'à l'essai sur borne réelle
  (DW-P5-05).

## Alternatives écartées

- **Promettre une grâce de N minutes sans matériel** : ce serait une invention
  contraire à la règle 5 et au §4.3 (« dépend fortement des capacités des passerelles »).
- **Reporter l'ADR après la Phase 5** : le cahier des charges l'exigeait avant.
  Cette décision fige le non-engagement en attendant les essais terrain.
