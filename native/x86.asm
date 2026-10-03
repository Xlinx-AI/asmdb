BITS 32
section .text
global asmdb_scores:function
asmdb_scores:
    push ebp
    mov ebp, esp
    push ebx
    push esi
    push edi
    mov esi, [ebp+8]
    mov edi, [ebp+12]
    mov ecx, [ebp+16]
    xor ebx, ebx
.row:
    cmp ebx, ecx
    jae .done
    fldz
    xor edx, edx
.inner:
    cmp edx, [ebp+20]
    jae .store
    fld dword [esi + edx*4]
    fmul dword [edi + edx*4]
    faddp st1, st0
    inc edx
    jmp .inner
.store:
    mov eax, [ebp+24]
    fstp dword [eax + ebx*4]
    mov eax, [ebp+20]
    lea esi, [esi + eax*4]
    inc ebx
    jmp .row
.done:
    pop edi
    pop esi
    pop ebx
    pop ebp
    ret
