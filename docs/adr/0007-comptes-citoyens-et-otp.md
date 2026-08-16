# ADR-0007 — Comptes citoyens et propriété du parcours OTP

- Statut : Acceptée
- Date : 2026-08-16
- Source : cahier des charges §8.1, §9, §10.3 ; [spike OpenWISP](../phase0/06-spike-openwisp.md)

## Contexte

Deux questions se posent au démarrage de la Phase 3.

**1. Qui envoie et vérifie l'OTP ?** Le spike a montré qu'openwisp-radius expose déjà
`account/phone/token/` et `account/phone/verify/` : une inscription par téléphone
complète, prête à l'emploi.

**2. Un citoyen est-il un utilisateur Django ?** Le §9 décrit une entité `User` porteuse
de `phone_e164`, `preferred_language`, `status`, `verified_at`. Le §10.3 parle
séparément d'« utilisateurs internes ». Ce sont deux populations distinctes.

## Décision

**L'OTP reste sous la maîtrise de la plateforme métier.** Le parcours citoyen — envoi,
vérification, limitation d'abus, consentement — est implémenté dans `core-api` derrière
une interface `SmsProvider`. L'OTP d'openwisp-radius n'est pas utilisé.

**Les citoyens et le personnel interne sont deux modèles distincts.** `Citizen` porte le
compte citoyen (concept `User` du §9) ; le personnel interne reste sur `auth.User` de
Django, avec ses groupes et permissions.

## Pourquoi

Le §8.1 impose des règles qu'un fournisseur externe ne peut pas porter à notre place :
limitation par numéro, adresse IP, appareil **et** période ; blocage progressif en cas
d'abus ; acceptation des conditions **versionnée et horodatée** ; export et suppression
du compte sur demande. Le §13.4 exige en plus un journal d'audit, et la question 16 du
§22 un suivi du coût des SMS — impossible sans posséder l'envoi.

Le compte citoyen est par ailleurs la clé de voûte des commandes, paiements et droits
d'accès (§9) : le déléguer à un système externe reviendrait à faire dépendre toute la
chaîne financière de la disponibilité d'OpenWISP.

Séparer les deux populations apporte un bénéfice de sécurité direct : un citoyen ne peut
pas hériter par accident d'une permission d'administration, puisqu'il n'existe pas dans
le système de permissions de Django. Cela évite aussi de changer `AUTH_USER_MODEL` sur un
projet déjà migré, opération coûteuse et risquée.

## Conséquences

- `Citizen` s'authentifie par téléphone + OTP et reçoit des jetons courts ; il n'a ni mot
  de passe, ni accès à l'administration Django.
- Une classe d'authentification DRF dédiée porte les jetons citoyens, distincte de
  l'authentification de session du personnel.
- L'adaptateur réseau crée l'utilisateur RADIUS correspondant **après** vérification du
  numéro (§11.1). Le citoyen reste la source de vérité côté métier.
- L'OTP d'openwisp-radius reste disponible si une intégration future l'exige ; ce choix
  est réversible tant que le portail parle à notre API et non à la sienne.
- Le nom `Citizen` remplace le `User` du §9 pour éviter toute confusion avec `auth.User`.
  Le §9 autorise l'évolution des noms tant que les concepts sont conservés.
