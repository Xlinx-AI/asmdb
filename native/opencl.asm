BITS 64
default rel
section .rdata
local_size: dq 64
section .text
%ifidn __OUTPUT_FORMAT__,win64
global asmdb_cl_enqueue
asmdb_cl_enqueue:
    mov rax, r9
    sub rsp, 72
    mov [rsp + 32], r8
    xor r9d, r9d
    mov [rsp + 40], r9
    mov [rsp + 48], r9
    mov [rsp + 56], r9
    mov [rsp + 64], r9
    lea r10, [local_size]
    mov [rsp + 40], r10
    mov r8d, 1
    call rax
    add rsp, 72
    ret
%else
global asmdb_cl_enqueue:function
asmdb_cl_enqueue:
    mov rax, rcx
    mov r8, rdx
    mov edx, 1
    xor ecx, ecx
    xor r9d, r9d
    sub rsp, 24
    mov [rsp], r9
    mov [rsp + 8], r9
    mov [rsp + 16], r9
    lea r9, [local_size]
    call rax
    add rsp, 24
    ret
section .note.GNU-stack noalloc noexec nowrite progbits
%endif
