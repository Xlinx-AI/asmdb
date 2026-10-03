.intel_syntax noprefix
.text
.globl asmdb_scores
.type asmdb_scores,@function
asmdb_scores:
    test rdx, rdx
    jz .done
    mov r9, rdi
    xor r10d, r10d
.row:
    vxorps ymm0, ymm0, ymm0
    vxorps ymm2, ymm2, ymm2
    xor r11d, r11d
.vec16:
    lea rax, [r11 + 16]
    cmp rax, rcx
    ja .vec8
    vmovups ymm1, YMMWORD PTR [r9 + r11*4]
    vmulps ymm1, ymm1, YMMWORD PTR [rsi + r11*4]
    vaddps ymm0, ymm0, ymm1
    vmovups ymm3, YMMWORD PTR [r9 + r11*4 + 32]
    vmulps ymm3, ymm3, YMMWORD PTR [rsi + r11*4 + 32]
    vaddps ymm2, ymm2, ymm3
    add r11, 16
    jmp .vec16
.vec8:
    vaddps ymm0, ymm0, ymm2
    lea rax, [r11 + 8]
    cmp rax, rcx
    ja .reduce
    vmovups ymm1, YMMWORD PTR [r9 + r11*4]
    vmulps ymm1, ymm1, YMMWORD PTR [rsi + r11*4]
    vaddps ymm0, ymm0, ymm1
    add r11, 8
.reduce:
    vextractf128 xmm1, ymm0, 1
    vaddps xmm0, xmm0, xmm1
    vhaddps xmm0, xmm0, xmm0
    vhaddps xmm0, xmm0, xmm0
.tail:
    cmp r11, rcx
    jae .store
    vmovss xmm1, DWORD PTR [r9 + r11*4]
    vmulss xmm1, xmm1, DWORD PTR [rsi + r11*4]
    vaddss xmm0, xmm0, xmm1
    inc r11
    jmp .tail
.store:
    vmovss DWORD PTR [r8 + r10*4], xmm0
    lea r9, [r9 + rcx*4]
    inc r10
    cmp r10, rdx
    jb .row
    vzeroupper
.done:
    ret
.section .note.GNU-stack,"",@progbits
