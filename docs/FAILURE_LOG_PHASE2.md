# Phase 2 development failure log

1. **A predecessor-chain fixture initially expected cells to be removed even
   though it supplied a valid common action.** The test, not the algorithm,
   was wrong: a cell with a safe successor into a retained cell is a valid
   predecessor. The fixture was corrected so the intermediate cell has no
   candidate action, then the upstream cell is removed on the next fixed-point
   iteration. This validates the simultaneous monotone elimination semantics.
2. **Certificate replay compared JSON lists to in-memory tuples.** The
   serializer emits JSON arrays; replay now canonicalizes control vectors to
   lists before comparing. No numerical tolerance was introduced.
3. **Vehicle profile initially bundled a friction coefficient with chassis
   geometry.** This was corrected: friction is a tire-road scenario parameter
   and is left unset in the CommonRoad geometry profile. Requesting the bicycle
   friction parameters without an explicit scenario coefficient now raises.
4. **Belief-cell splitting could be confused with an observation split.** The
   refinement API keeps the same cell/policy-node ID, creates two closed boxes
   whose union equals the parent, and invalidates all old transition witnesses.
   It never invents an observation branch.
5. **A finite abstract fixed point could be mistaken for the concrete
   S-infinity certificate.** The API, JSON certificate, docs, and tests now
   hard-code `certified=false` and `FINITE_ABSTRACTION_ONLY`. A tampered
   certificate claiming concrete certification is rejected.
6. **Uploaded bibliography contained a duplicate `kaelbling1998planning` key.**
   The original two entries were identical; the Phase 2 bibliography copy keeps
   one canonical entry and adds the three vehicle-geometry references. No
   existing citation key was renamed.
