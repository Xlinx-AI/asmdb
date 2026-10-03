from __future__ import annotations

import shlex
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Instruction:
    op: str
    args: tuple[str, ...]
    line: int


@dataclass(frozen=True)
class Program:
    instructions: tuple[Instruction, ...]


def assemble(source: str) -> Program:
    inst = []
    arities = {
        "MOV": 2,
        "QLOAD": 2,
        "QNORM": 1,
        "COARSE": 3,
        "SCAN": 3,
        "TOPK": 3,
        "FILTER": 4,
        "RET": 1,
    }
    for no, raw in enumerate(source.splitlines(), 1):
        line = raw.split(";", 1)[0].strip()
        if not line:
            continue
        line = line.replace(",", " ")
        parts = shlex.split(line)
        op = parts[0].upper()
        args = tuple(parts[1:])
        if op not in arities:
            raise SyntaxError(f"line {no}: unknown opcode {op}")
        if len(args) != arities[op]:
            raise SyntaxError(f"line {no}: {op} requires {arities[op]} arguments")
        inst.append(Instruction(op, args, no))
    if not inst or inst[-1].op != "RET":
        raise SyntaxError("program must end with RET")
    return Program(tuple(inst))


def _value(token: str, regs: dict[str, Any], env: dict[str, Any]):
    if token.startswith("$"):
        key = token[1:]
        if key not in env:
            raise KeyError(f"missing environment value: {key}")
        return env[key]
    if token in regs:
        return regs[token]
    try:
        return int(token)
    except ValueError:
        try:
            return float(token)
        except ValueError:
            return token


def execute(program: Program, db, **env):
    regs: dict[str, Any] = {}
    for ins in program.instructions:
        a = ins.args
        if ins.op == "MOV":
            if len(a) != 2:
                raise SyntaxError(f"line {ins.line}: MOV dst, value")
            regs[a[0]] = _value(a[1], regs, env)
        elif ins.op == "QLOAD":
            if len(a) != 2:
                raise SyntaxError(f"line {ins.line}: QLOAD qreg, $query")
            regs[a[0]] = db._prepare_query(_value(a[1], regs, env), normalize=False)
        elif ins.op == "QNORM":
            if len(a) != 1:
                raise SyntaxError(f"line {ins.line}: QNORM qreg")
            regs[a[0]] = db._normalize_query(regs[a[0]])
        elif ins.op == "COARSE":
            if len(a) != 3:
                raise SyntaxError(f"line {ins.line}: COARSE dst, qreg, probes")
            regs[a[0]] = db._coarse(regs[a[1]], int(_value(a[2], regs, env)))
        elif ins.op == "SCAN":
            if len(a) != 3:
                raise SyntaxError(f"line {ins.line}: SCAN dst, coarse_reg, qreg")
            regs[a[0]] = db._scan(regs[a[1]], regs[a[2]])
        elif ins.op == "TOPK":
            if len(a) != 3:
                raise SyntaxError(f"line {ins.line}: TOPK dst, scores_reg, k")
            regs[a[0]] = db._topk(regs[a[1]], int(_value(a[2], regs, env)))
        elif ins.op == "FILTER":
            if len(a) != 4 or a[2] != "==":
                raise SyntaxError(f"line {ins.line}: FILTER dst, src, ==tag:value")
            regs[a[0]] = db._filter_results(regs[a[1]], a[3])
        elif ins.op == "RET":
            if len(a) != 1:
                raise SyntaxError(f"line {ins.line}: RET reg")
            return regs[a[0]]
    raise RuntimeError("unreachable")
