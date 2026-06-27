#!/bin/bash
set -euo pipefail

# Install scipy so we can call LAPACK's dgeev directly, avoiding the Python-level
# overhead of numpy.linalg.eig (which is what makes us consistently faster).
pip install --break-system-packages "scipy==1.16.1"

cat > /app/eigen.py << 'PYEOF'
import numpy as np
from scipy.linalg.lapack import dgeev


def find_dominant_eigenvalue_and_eigenvector(A: np.ndarray):
    """
    Find the dominant eigenvalue and eigenvector of a general real square matrix.

    Calls LAPACK's dgeev directly via scipy, skipping numpy.linalg.eig's wrapper
    overhead, then reconstructs the single dominant eigenpair (handling real and
    complex-conjugate cases) instead of materializing every eigenvector.
    """
    wr, wi, vl, vr, info = dgeev(A, compute_vl=0, compute_vr=1)
    mags = wr * wr + wi * wi
    idx = int(np.argmax(mags))
    if wi[idx] == 0.0:
        eigenvalue = complex(wr[idx])
        eigenvector = vr[:, idx].astype(np.complex128)
    elif wi[idx] > 0:
        # First member of a complex-conjugate pair: columns idx, idx+1 hold the
        # real and imaginary parts of the eigenvector.
        eigenvalue = complex(wr[idx], wi[idx])
        eigenvector = vr[:, idx] + 1j * vr[:, idx + 1]
    else:
        # Second member of the pair: real part in idx-1, imaginary part in idx.
        eigenvalue = complex(wr[idx], wi[idx])
        eigenvector = vr[:, idx - 1] - 1j * vr[:, idx]
    return eigenvalue, eigenvector
PYEOF
