#ifdef __APPLE__
.text
.globl _asmdb_cl_enqueue
_asmdb_cl_enqueue:
#else
.text
.globl asmdb_cl_enqueue
.type asmdb_cl_enqueue, %function
asmdb_cl_enqueue:
#endif
    sub sp, sp, #32
    str x30, [sp, #16]
    str xzr, [sp]
    mov x9, x3
    mov x4, x2
    mov x2, #1
    mov x3, #0
    mov x10, #64
    str x10, [sp, #8]
    add x5, sp, #8
    mov x6, #0
    mov x7, #0
    blr x9
    ldr x30, [sp, #16]
    add sp, sp, #32
    ret
#ifndef __APPLE__
.section .note.GNU-stack,"",%progbits
#endif
