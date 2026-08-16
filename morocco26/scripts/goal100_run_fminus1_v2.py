#!/usr/bin/env python3
"""Execute F-1 with the corrected vectorized legal allocator V2."""
from __future__ import annotations

import goal100_run_fminus1 as engine
from goal100_fminus1_vector_allocator_v2 import vectorized_allocate

# Replace only the batched implementation. The scalar legal oracle, frozen
# protocol, random seeds, latent draws and all statistical rules are unchanged.
engine.vectorized_allocate = vectorized_allocate


if __name__ == "__main__":
    engine.main()
