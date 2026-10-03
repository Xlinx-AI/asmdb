import tempfile

import numpy as np

from asmdb import ASMDB

rng = np.random.default_rng(7)
vectors = rng.normal(size=(5000, 128)).astype(np.float32)
with tempfile.TemporaryDirectory() as td:
    db = ASMDB.build(td, vectors, n_clusters=32)
    q = vectors[123] + 0.03 * rng.normal(size=128)
    print(db.info())
    print(db.search(q, k=5, nprobe=3))
    db.close()
