BITS 64
default rel
section .text
%include "abi.inc"
asmdb_scores:
    ENTER_SCORES
    test rdx, rdx
    jz .done
    mov r9, rdi
    xor r10d, r10d
.row:
    xorps xmm0, xmm0
    xor r11d, r11d
.inner:
    cmp r11, rcx
    jae .store
    movss xmm1, [r9 + r11*4]
    mulss xmm1, [rsi + r11*4]
    addss xmm0, xmm1
    inc r11
    jmp .inner
.store:
    movss [r8 + r10*4], xmm0
    lea r9, [r9 + rcx*4]
    inc r10
    cmp r10, rdx
    jb .row
.done:
    LEAVE_SCORES
