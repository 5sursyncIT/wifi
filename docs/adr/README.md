# Registre des décisions d'architecture (ADR)

Chaque décision structurante est consignée dans un fichier numéroté, immuable une fois acceptée.
Une décision remplacée n'est pas supprimée : son statut passe à « Remplacée par ADR-XXXX ».

## Format

```markdown
# ADR-NNNN — Titre

- Statut : Proposée | Acceptée | Remplacée par ADR-XXXX
- Date : AAAA-MM-JJ

## Contexte
## Décision
## Conséquences
## Alternatives écartées
```

## Index

| ADR | Titre | Statut |
|---|---|---|
| [0001](0001-openwisp-systeme-externe.md) | OpenWISP comme système externe de référence | Acceptée |
| [0002](0002-stack-monorepo.md) | Stack technique et structure du monorepo | Acceptée |
| [0003](0003-conventions-langue-et-code.md) | Conventions de langue et de code | Acceptée |
| [0004](0004-paiement-push-nominal.md) | Paiement par push serveur comme parcours nominal | Acceptée |
| [0005](0005-budget-portail-captif.md) | Budget JavaScript du portail captif — portail sur Astro | Acceptée |
| [0006](0006-integration-openwisp.md) | Frontière d'intégration OpenWISP après le spike | **Proposée — décision requise avant la Phase 5** |
