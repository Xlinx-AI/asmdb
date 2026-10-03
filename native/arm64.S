#ifdef __APPLE__
.text
.globl _asmdb_scores
_asmdb_scores:
#else
.text
.globl asmdb_scores
.type asmdb_scores, %function
asmdb_scores:
#endif
    cbz x2, 5f
    lsl x5, x3, #2
1:
    mov x6, x0
    mov x7, x1
    mov x8, x3
    movi v0.4s, #0
2:
    cmp x8, #4
    b.lo 3f
    ldr q1, [x6], #16
    ldr q2, [x7], #16
    fmul v1.4s, v1.4s, v2.4s
    fadd v0.4s, v0.4s, v1.4s
    sub x8, x8, #4
    b 2b
3:
    faddp v0.4s, v0.4s, v0.4s
    faddp s0, v0.2s
    cbz x8, 4f
6:
    ldr s1, [x6], #4
    ldr s2, [x7], #4
    fmul s1, s1, s2
    fadd s0, s0, s1
    subs x8, x8, #1
    b.ne 6b
4:
    str s0, [x4], #4
    add x0, x0, x5
    subs x2, x2, #1
    b.ne 1b
5:
    ret
#ifndef __APPLE__
.section .note.GNU-stack,"",%progbits
#endif
