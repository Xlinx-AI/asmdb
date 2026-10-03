%ifidn __OUTPUT_FORMAT__,win64
global asmdb_scores
%macro ENTER_SCORES 0
    push rdi
    push rsi
    mov rdi, rcx
    mov rsi, rdx
    mov rdx, r8
    mov rcx, r9
    mov r8, [rsp + 56]
%endmacro
%macro LEAVE_SCORES 0
    pop rsi
    pop rdi
    ret
%endmacro
%else
global asmdb_scores:function
%macro ENTER_SCORES 0
%endmacro
%macro LEAVE_SCORES 0
    ret
%endmacro
%endif
