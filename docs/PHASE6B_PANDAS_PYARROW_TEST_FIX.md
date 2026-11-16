# Phase 6B test fix: pandas / fake-pyarrow import order

## Failure

The server's `test_av2_parquet_reader_projects_used_columns_and_hashes_source_once`
failed while importing pandas:

```text
AttributeError: module 'pyarrow' has no attribute '__version__'
```

This was caused by the test installing a deliberately minimal fake `pyarrow`
module in `sys.modules` **before** importing pandas. Recent pandas releases
inspect `pyarrow.__version__` during pandas initialization. The fake module only
implemented the `pyarrow.parquet.ParquetFile` surface needed by the adapter test;
it was not intended to emulate the complete pyarrow package.

## Root cause classification

- Production parser: no change required.
- pandas / pyarrow installation: no version change required.
- Fault: test-fixture isolation / import ordering.
- Data semantics, Parquet column projection and SHA-256 behavior: unchanged.

## Fix

The test now provides minimal `pandas` and `pyarrow` module stubs. The fake
`pandas.read_parquet(path, columns=..., engine=...)` records the adapter call
and returns the synthetic AV2 rows. The fake `pyarrow.parquet.ParquetFile`
exposes only the schema names. This test is intended to verify the adapter's
projection and hashing contract, not pandas' internal compatibility layer or
the pyarrow decoder.

Real pandas/pyarrow integration remains covered by the server-side Phase 6B
real-data validation script.

## Verification

Executed:

```bash
python scripts/validate_phase6c_a_dependency_free.py
```

Result:

```text
51 passed
```

This dependency-free suite does not replace the regular server-side pytest and
native MPFR/CTest acceptance.
