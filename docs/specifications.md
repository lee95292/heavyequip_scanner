# Scanner specifications catalog

Authenticated read-only `제원표` tab. Source snapshot: `20261018T1735-local-820`.

## Scope

820 inventory records (790 individual-model inventory entries and 30 application variants); these are not a globally deduplicated count of base machines. Caterpillar inventory includes configurations and assemblies. 245,294 canonical facts and structured equipment, conditions, tables, warnings, source references, and page reviews. Catalog-reviewed means **partial** review, never exhaustive completeness. Source market, revision, configuration, raw values/units and conflicts remain visible.

The importer builds an immutable compact server-side index and gzip model files. The browser receives at most 60 model summaries or 60 detail rows/fragments per request, never the original ~550 MB aggregate exports. Large structured records are split into 12,000-character fragments without omitting their content. Model detail decoding is asynchronous with a bounded LRU. No database migration or email action occurs.

## Reproducible import

1. Freeze the source export with `SNAPSHOT_MANIFEST.json`. `model_index.json`, both JSONL aggregates, and every model data file must match their SHA-256 entries.
2. Run `python3 scripts/build-specifications.py /path/to/frozen-export /path/to/staging/<snapshot-id>`.
3. Copy the built `<snapshot-id>` directory under `dashboard/data/specifications/` (never `public/` or `dist/`).
4. Run `python3 scripts/install-specifications.py dashboard/data/specifications <snapshot-id>`. It verifies all built hashes and selects the version with an atomic pointer replacement. Same-version reinstallation is safe. Roll back by reinstalling the prior retained version. The server picks up changed pointers without a process restart.

Snapshot data stays outside Git; the source manifest SHA-256 and deployed built manifest are retained with the release backup. To recreate the same data, retain the frozen source snapshot and importer version together. Never modify an active snapshot in place; build a distinct new snapshot ID.

## Search semantics and exclusions

- Identity is SHA-256(manufacturer + NUL + relative model Markdown path), truncated to 24 hex characters, collision-checked.
- Numeric filters use interval overlap with any eligible configuration. Multiple filters can match different configurations; the UI explicitly says so and offers the matching individual fact rows for review. Do not use this as proof that one purchasable configuration satisfies all limits.
- Raw source units are preserved. Deterministic conversion only supports explicit recognized units. Unknown/blank/nonnumeric values never become zero. Ambiguous decimal separators, inferred units and inequalities are not used.
- Explicit other-model rows (`applicable_to_record_model=false`), component/assembly host capacities, OCR/uncertain/suspect/pending values, source-conflict/unit-conflict/reference-ambiguity/blank states and nonempty `original_fact.conflict_ids` are excluded from numeric facets. They remain in detail.
- Operating weight excludes axle/shipping/increment/tipping-load fields. Net/gross/rated engine power remain distinct. Specialized dimensional conditions are excluded from general reach/depth facets.
- Category normalization is derived from model metadata and official source titles/product URLs. Original category is shown. Unknown category remains labeled.

## Security and testing

Register `registerSpecifications(app)` **after** `app.use('/api', requireDashboardAuth)`. GET-only routes: `/api/specifications` and `/api/specifications/:id`. No upload or mutation endpoint. Identifiers, query types, bounds, snapshot IDs, sections, and page limits are validated. No requested filesystem path is accepted. Built manifest/index/model integrity is verified; invalid data fails closed. URLs accept only http(s), with no user-info credentials. React escapes all facts; no HTML or Markdown renderer is used.

Run `python3 scripts/test-specifications-import.py` and `node --test dashboard/server/specifications.test.cjs`. For an installed dataset set `SPECIFICATIONS_TEST_ROOT=dashboard/data/specifications`. Run existing dashboard Node tests and `npm run build` before release. Verify authenticated and unauthenticated production responses, repeated filtering/close/reopen, empty/error states, and responsive layout. No credentials should appear in logs or artifacts.
