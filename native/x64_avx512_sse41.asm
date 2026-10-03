BITS 64
default rel
section .text
%include "abi.inc"
asmdb_scores:
    ENTER_SCORES
    test rdx, rdx
    jz .done
    push rbp
    mov rbp, rsp
    sub rsp, 64
    mov r9, rdi
    xor r10d, r10d
.row:
    vxorps zmm0, zmm0, zmm0
    vxorps zmm2, zmm2, zmm2
    xor r11d, r11d
.vec32:
    lea rax, [r11 + 32]
    cmp rax, rcx
    ja .vec16
    vmovups zmm1, [r9 + r11*4]
    vmulps zmm1, zmm1, [rsi + r11*4]
    vaddps zmm0, zmm0, zmm1
    vmovups zmm3, [r9 + r11*4 + 64]
    vmulps zmm3, zmm3, [rsi + r11*4 + 64]
    vaddps zmm2, zmm2, zmm3
    add r11, 32
    jmp .vec32
.vec16:
    vaddps zmm0, zmm0, zmm2
    lea rax, [r11 + 16]
    cmp rax, rcx
    ja .reduce
    vmovups zmm1, [r9 + r11*4]
    vmulps zmm1, zmm1, [rsi + r11*4]
    vaddps zmm0, zmm0, zmm1
    add r11, 16
.reduce:
    vmovups [rsp], zmm0
    vmovups ymm1, [rsp]
    vaddps ymm1, ymm1, [rsp + 32]
    vextractf128 xmm2, ymm1, 1
    vaddps xmm0, xmm1, xmm2
    vhaddps xmm0, xmm0, xmm0
    vhaddps xmm0, xmm0, xmm0
.tail:
    cmp r11, rcx
    jae .store
    vmovss xmm1, [r9 + r11*4]
    vmulss xmm1, xmm1, [rsi + r11*4]
    vaddss xmm0, xmm0, xmm1
    inc r11
    jmp .tail
.store:
    vmovss [r8 + r10*4], xmm0
    lea r9, [r9 + rcx*4]
    inc r10
    cmp r10, rdx
    jb .row
    vzeroupper
    leave
.done:
    LEAVE_SCORES
