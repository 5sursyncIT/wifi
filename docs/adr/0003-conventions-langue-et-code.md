# ADR-0003 — Conventions de langue et de code

- Statut : Acceptée
- Date : 2026-08-16
- Décideur : commanditaire (validation du 2026-08-16)

## Contexte

Le cahier des charges est en français, mais ses entités (`User`, `Order`, `Entitlement`…)
sont nommées en anglais. Une convention unique est nécessaire avant la première ligne de code.

## Décision

| Élément | Langue |
|---|---|
| Identifiants (code, tables, colonnes, endpoints, variables) | **Anglais** |
| Messages de commit | **Anglais** (Conventional Commits : `feat:`, `fix:`, `chore:`…) |
| Commentaires techniques dans le code | **Anglais** |
| Documentation (`docs/`), ADR, README | **Français** |
| Interfaces utilisateur (portail, back-office) | **Français** (i18n prête pour wolof/anglais) |
| Textes d'erreur API destinés aux usagers | **Français**, localisables |

## Conséquences

- Cohérence avec le modèle de données du §9 et les bibliothèques de l'écosystème.
- Les clés i18n sont en anglais, les traductions FR sont la référence fonctionnelle.
- La documentation reste accessible aux parties prenantes municipales.

## Alternatives écartées

- **Tout en français** : friction permanente avec les frameworks et risque de mélange.
- **Tout en anglais** : documentation moins accessible au commanditaire.
