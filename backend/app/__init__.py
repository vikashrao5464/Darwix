"""Darwix assessment backend."""
import os

# Qdrant imports NumPy. A small prototype does not need a BLAS thread per
# CPU core; keep simultaneous CLI/API/test processes within modest resources.
# An explicit operator setting takes precedence.
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
