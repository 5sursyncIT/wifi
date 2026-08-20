# Design

Identité visuelle du portail captif et du back-office Dakar WiFi, dérivée des
armoiries officielles de la Ville de Dakar et du site [mairiedakar.sn](https://mairiedakar.sn/).

## Palette

| Rôle | Valeur | Source |
|---|---|---|
| Brand (actions, chrome) | `#004090` | Émail bleu du blason |
| Brand dark | `#002d66` | Ombre du bleu |
| Or | `#e8d20c` | Triangle central |
| Danger | `#c8101e` | Écu du phare |
| OK | `#157a38` | Lauriers / chevrons |
| Surface | `#eef2f8` | Papier froid, soleil extérieur |
| Encre | `#1c2838` | Wordmark du lockup |

Ruban civic en tête de page : bleu / or / rouge, dans cet ordre.

## Typographie

Pile système uniquement (ADR-0005, budget portail). Pas de webfont municipale
tant qu'un fichier n'est pas fourni.

## Logo

- Lockup horizontal transparent : `/logo-ville-dakar.png`
- Armoiries carrées (favicon) : `/armoiries-ville-dakar.png`

Les fichiers se remplacent dans `public/` sans changer le code (§2.2).

## Composants

Bouton primaire : bleu royal, texte blanc, ombre portée légère.
Cartes d'offre : fond blanc, ombre bleutée.
Bandeaux info / succès / erreur : `panel-info`, `panel-ok`, `panel-error`.
