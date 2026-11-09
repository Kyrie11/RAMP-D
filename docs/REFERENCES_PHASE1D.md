# Phase 1D mathematical reference notes

The uploaded `aaai2027.bib` contains the paper's reachability and robust
invariance references (including Li et al. 2021, Brown et al. 2023, and
Schäfer et al. 2023), but it does not contain a dedicated continuous OBB / swept
collision-detection reference.

For Phase 1D, the following open tutorial was checked:

- Matthias Teschner, Marie-Paule Cani, Ron Fedkiw, Robert Bridson, Stéphane
  Redon, Pascal Volino, and Gabriel Zachmann, **Collision Handling and its
  Applications**, Eurographics 2006 Tutorial. The rigid-body section by
  Stéphane Redon discusses conservative continuous overlap tests for AABBs
  and OBBs, interval evaluation of separating-axis inequalities, and temporal
  subdivision when interval bounds are too conservative.
  https://diglib.eg.org/server/api/core/bitstreams/8b33a171-7075-4f14-a872-4c6e5ed90a33/content

The source explains that a conservative bounding-volume test may declare
possible overlap even when no overlap exists, and that a strict interval
separation bound over the full interval is sufficient to rule out overlap. It
also discusses interval overestimation under large rotations and the use of
time subdivision. This matches the conservative result semantics in this
implementation: strict separation may be proved; overlap of outer enclosures
remains unresolved.

This implementation does **not** reproduce a complete continuous OBB-OBB
SAT algorithm for arbitrary uncertain motions. It maps the entire validated
state box to a swept spatial projection enclosure and tests a finite set of
fixed axes. This is a sufficient outer-set separation test, not a complete
collision detector.

No additional paper upload is required for Phase 1D. Before Phase 2, the full
PDFs of Brown et al. (2023), *Computing Controlled Invariant Sets of Nonlinear
Control-Affine Systems*, and Schäfer et al. (2023), *Scalable Computation of
Robust Control Invariant Sets of Nonlinear Systems*, would be useful for
cross-checking invariant-set approximation assumptions and algorithms. They
are not dependencies of the current geometry module.
