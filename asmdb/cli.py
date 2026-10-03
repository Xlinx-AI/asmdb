from __future__ import annotations

import argparse
import json

import numpy as np

from .db import ASMDB
from .native import backend_info


def main():
    ap = argparse.ArgumentParser(prog="asmdb")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("backend")
    p = sub.add_parser("info")
    p.add_argument("db")
    p = sub.add_parser("search")
    p.add_argument("db")
    p.add_argument("query_npy")
    p.add_argument("-k", type=int, default=10)
    p.add_argument("--nprobe", type=int, default=2)
    p.add_argument("--backend", choices=("cpu", "opencl"), default="cpu")
    p.add_argument("--device", type=int, default=0)
    args = ap.parse_args()
    if args.cmd == "backend":
        print(json.dumps(backend_info().__dict__, indent=2))
    elif args.cmd == "info":
        with ASMDB(args.db) as db:
            print(json.dumps(db.info(), indent=2))
    elif args.cmd == "search":
        q = np.load(args.query_npy, allow_pickle=False)
        with ASMDB(args.db, backend=args.backend, device=args.device) as db:
            print(json.dumps(db.search(q, k=args.k, nprobe=args.nprobe), indent=2))
