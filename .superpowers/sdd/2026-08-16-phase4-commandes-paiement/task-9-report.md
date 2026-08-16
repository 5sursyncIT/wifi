Status: Complete
Commits: feat: portal purchase journey with push wait, bounded polling and receipt
Tests: portal 9/9; backend ciblé 17/17; lint, typecheck et mypy OK
Build: Astro OK; JavaScript 0,1 Ko gzip; marge budget 149,9 Ko
Seed: make seed OK; catalogue à 5 offres publiées
Concerns: aucune
Report: .superpowers/sdd/2026-08-16-phase4-commandes-paiement/task-9-report.md
Round 1: transient getOrder failures now reschedule polling until the deadline.
Receipt errors keep the success screen visible and expose a controlled French alert.
Tests round 1: captive portal 10/10; build and 150 Ko budget OK.
Commit round 1: fix: keep portal purchase polling through transient network errors
