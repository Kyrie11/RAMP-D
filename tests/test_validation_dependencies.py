from pathlib import Path


def test_phase2_validation_does_not_require_manuscript_or_bibliography():
    script = (Path(__file__).parents[1] / "scripts" / "validate_phase1d.sh").read_text()
    # Phase 2 delegates to Phase 1D. The manuscript files may still be hashed
    # for provenance when present, but their absence must not abort validation.
    assert "for name in ('CMakeLists.txt','pyproject.toml','PROGRESS.json')" in script
    assert "if p.is_file():" in script
    assert "AnonymousSubmission2027_Phase2.tex','aaai2027_Phase2.bib" in script
