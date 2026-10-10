# Frozen July snapshot verification

The bundled archive preserves fourteen original raw JSONs and the acquisition manifest; hashes, licence and attribution are in `data/snapshots/README.md`.

Build/audit verify raw-byte identity. Analysis/figures rebuild monthly and quarterly raw relations and compare them to parquet using bidirectional `EXCEPT ALL`. All three charts use a shared split loader checking finite rounded CSV identity, unique keys, coverage, weights and contributions before formatting full-precision rates once. This independently rejects same-period numeric drift without persisted seals.

Batch promotion restores prior bytes after ordinary replacement exceptions; it is not crash atomicity, concurrent-reader isolation or power-loss durability.

After installing `requirements.txt`, run `python tests/offline_ci.py`: restore frozen inputs, build, execute substantive tests with no skips or empty runs, replay audit/analysis/figures, compare seven CSVs against committed bytes, check report/site mirrors and run eight smoke checks. Hosted Linux execution remains a separate publication gate. PNG byte equality is a same-environment property, not cross-platform certification.

Raw July headline: current-price value +1.457842393%, chained volume -1.281062808%. Nineteen recomputable release rows match; three unavailable rows remain `not_recomputed`. Tolerance is 0.051 pp on full-precision differences. Watches +11.1 and Mini-Marts -1.5 labels round once in both palettes.

Reference PDFs were not freshly authenticated. Native keyboard/screen-reader/mobile certification and deployed Pages verification remain unperformed. The existing Tableau dashboard is an unchanged July snapshot; parity against the repaired local extract remains unverified.
