# Reverse engineering misc
Collection of decomps used to figure out random codecs before being added to vgmstream.

Mostly useless but kept for historical(?) reasons and maybe to inspire neophytes.

You probably want to use IDA/Ghidra's decompiled pseudo-code rather than raw assembly, but sometimes it's good to double check.

Only a few cases since once you do a few it's mostly the same.

## finding decoding functions

A somewhat hard part of the process is finding the decoding function. IDA can search by fixed value, so a good idea is loking for values that are common in audio codecs. For example 32767 and -32768 (clamp values), or 24623, 27086, 29794 (IMA table values). Sometimes looking for debug strings helps too.


# ASF decoder
```
* decode N frames, mono version (there is another for stereo, basically the same)
sub_26E02269
  arg_0           = dword ptr  8
  arg_4           = dword ptr  0Ch
  arg_8           = dword ptr  10h
 
  push    ebp                       #prepare procedure stuff
  mov     ebp, esp  
  push    ebp      
  push    esi      
  push    edi      
  push    edx      
  push    ecx      
  push    ebx      
  push    eax      
  mov     eax, [ebp+arg_8]          #prepare data pointer stuff
  mov     dword_26E071E0, eax
  mov     esi, [ebp+arg_4]          
  mov     edi, [ebp+arg_0]
 
 loc_26E02281:
  movzx   ecx, byte ptr [esi]       #header = load unsigned from frame
  inc     esi                       #*data += 1 //skip header
  mov     ebx, ecx                  #mode = header
  and     ebx, 4                    #mode &= 4 // 0 or 1, used below to select the function
  shr     ecx, 4                    #shift = header >>= 4
 
                                    #off_26E071D8[2] = { mode0, mode4 } function pointers
  add     ebx, offset off_26E071D8  #get function pointer +0/1 depending on mode
  call    dword ptr [ebx]           #enter function to process all frame nibbles
  dec     dword_26E071E0            #decrease num_frames, probably?
  jnz     short loc_26E02281        #keep processing frames
 
  pop     eax                       #clean procedure stuff
  pop     ebx
  pop     ecx
  pop     edx
  pop     edi
  pop     esi
  pop     ebp
  leave
  retn    0Ch
 sub_26E02269    endp
 
**************************************
 
* Parse left/mono frame, mode0
  (there is another function for right block, loading ch1 hist)
sub_26E022A8
  add     ecx, 2                 #shift += 2
  movsx   eax, word ptr [edi-4]  #hist1 = load signed ch0-hist1 from buffer
  shl     eax, 6                 #hist1 <<= 6
  movsx   edx, byte ptr [esi]    #byte = load signed nibbles
  and     edx, 0FFFFFFF0h        #sample = (byte & 0xFFFFFFF0) //get high nibble (signed)
  shl     edx, cl                #sample <<= (shift & 0xFF)
  add     eax, edx               #sample += hist1
  sar     eax, 6                 #sample >>= 6
  mov     [edi], ax              #write (int16)sample (cast instead of clamp16)
  add     edi, 4                 #move sample buffer pointer
 
                                 #implicit: hist1 = sample, still in eax
  shl     eax, 6                 #hist1 <<= 6
  movzx   edx, byte ptr [esi]    #byte = load unsigned nibbles
  and     edx, 0Fh               #sample = (byte & 0x0F) //get low nibble (unsigned)
  shl     edx, 4                 #sample <<= 4 //low nibble to high nibble
  movsx   edx, dl                #sample = (int8)sample //move and sign-extend 8b into itself
  shl     edx, cl                #sample <<= (shift & 0xFF)
  add     eax, edx               #sample += hist1
  sar     eax, 6                 #sample >>= 6
  mov     [edi], ax              #write (int16)sample (cast instead of clamp16)
  add     edi, 4                 #move sample buffer pointer
 
  ...                            #same for all other nibbles
 
**************************************
 
* Parse left/mono frame, mode4
  (there is another function for right block, loading ch1 hist)
sub_26E025E0
  add     ecx, 2                 #shift += 2
  movsx   eax, word ptr [edi-4]  #hist1 = load signed ch0-hist1 from buffer
  shl     eax, 7                 #hist1 <<= 7
  mov     ebx, eax               #(move hist1 around)
  movsx   eax, word ptr [edi-8]  #hist2 = load signed ch0-hist2 from buffer
  neg     eax                    #hist2 = -hist2
  shl     eax, 6                 #hist2 <<= 6
  movsx   edx, byte ptr [esi]    #byte = load signed nibbles
  and     edx, 0FFFFFFF0h        #sample = (byte & 0xFFFFFFF0) //get high nibble (signed)
  shl     edx, cl                #sample <<= (shift & 0xFF)
  add     eax, edx               #sample += hist2 //hist2 is negative here, thus sample - hist2
  adc     eax, ebx               #sample += hist1
  sar     eax, 6                 #sample >>= 6
  mov     [edi], ax              #write (int16)sample (cast instead of clamp16)
  add     edi, 4                 #move sample buffer pointer
 
                                 #implicit: hist1 = sample, still in eax
  shl     eax, 7                 #hist1 <<= 7
  mov     ebx, eax               #(move hist1 around)
  movsx   eax, word ptr [edi-8]  #hist2 = load signed ch0-hist2 from buffer
  neg     eax                    #hist2 = -hist2
  shl     eax, 6                 #hist2 <<= 6
  movzx   edx, byte ptr [esi]    #byte = load signed nibbles
  and     edx, 0Fh               #sample = (byte & 0x0F) //get low nibble (unsigned)
  shl     edx, 4                 #sample <<= 4 //low nibble to high nibble
  movsx   edx, dl                #sample = (int8)sample //move and sign-extend 8b into itself
  shl     edx, cl                #sample <<= (shift & 0xFF)
  add     eax, edx               #sample += hist2 //hist2 is negative here, thus sample - hist2
  adc     eax, ebx               #sample += hist1
  sar     eax, 6                 #sample >>= 6
  mov     [edi], ax              #write (int16)sample (cast instead of clamp16)
  add     edi, 4                 #move sample buffer pointer
 
  ...                            #same for all other nibbles
```

# CKS CKB decoder
```
# MSADPCM with changed nibble and hist order, other stuff seems the same

sub_4125A0      proc near               ; CODE XREF: sub_4016F0+81↑p

var_1C          = dword ptr -1Ch
var_18          = dword ptr -18h
var_14          = dword ptr -14h
var_10          = dword ptr -10h
var_C           = dword ptr -0Ch
var_8           = dword ptr -8
var_4           = dword ptr -4
arg_0           = dword ptr  8
arg_4           = dword ptr  0Ch
arg_8           = dword ptr  10h
arg_C           = dword ptr  14h

              * push    edi                         # ? save ?
                push    esi                         # ? save ?
                push    ebp                         # 
                mov     ebp, esp                    # 
                sub     esp, 1Ch                    # ? samples_left -= 28
                mov     edx, [ebp+arg_0]            # load p_frame
                mov     eax, [ebp+arg_4]            # load p_next_frame //value: frame_size = 0x18
                add     eax, edx                    # p_next_frame += p_frame //
                push    ebx                         # ? save p_buffer
                mov     esi, [ebp+arg_8]            # ? load p_buffer?
                mov     [ebp+var_8], eax            # save p_next_frame
                mov     al, [edx]                   # coef_index = (uint8)*p_frame[0]
                mov     di, [edx+1]                 # scale = (uint16)*p_frame[1]
                mov     cx, [edx+3]                 # hist2 = (uint16)*p_frame[3] //msadpcm does hist1 first (ex: BGM_Drum_LP writes fff0,fe62 in header order)
                mov     bx, [edx+5]                 # hist1 = (uint16)*p_frame[5]
                add     edx, 5                      # p_frame += 5
                mov     [ebp+arg_0], edx            # (save p_frame)

                mov     edx, [ebp+arg_C]            # channels = 2
                mov     [esi], cx                   # *p_buffer = hist2
                mov     [ebp+var_1C], esi           # ? save p_buffer
                lea     esi, [esi+edx*2]            # p_buffer += channels*2 //move buffer depending on channels
                add     edx, edx                    # channels += channels //channels*2
                mov     [esi], bx                   # *p_buffer = hist1
                add     esi, edx                    # p_buffer += channels //

                movzx   eax, al                     # (coef_index &= 0xFF)
                mov     edx, [ebp+arg_0]            # (load p_frame)
                add     edx, 2                      # p_frame += 2 //AKA: p_frame at nibbles start

                mov     [ebp+arg_8], esi            # ? save p_buffer
                mov     [ebp+arg_0], edx            # ? save p_frame
                
                mov     esi, dword_463084[eax*8]    # coef1 = msadpcm_table[coef_index*8+0]
                mov     eax, dword_463088[eax*8]    # coef2 = msadpcm_table[coef_index*8+1]
                mov     [ebp+var_14], esi           # (save coef1)
                mov     [ebp+var_18], eax           # (save coef2) 
                cmp     edx, [ebp+var_8]            # if (p_frame > p_next_frame)
                jnb     loc_412709                  # TRUE: end frame
                lea     ebx, [ebx+0]                # FALS: nop???

loc_412610:                                         #(loop A)
                mov     [ebp+var_4], 0              # scale = 0

loc_412617:                                         #(loop B)
                movsx   ecx, cx                     # hist2 = signed(hist2)
                imul    ecx, eax                    # predicted = hist2 * coef2
                movsx   eax, bx                     # hist1 = signed(hist1)
                imul    eax, esi                    # predicted += hist1 * coef1
                add     eax, ecx                    # sample = hist1 + hist2

                mov     cl, byte ptr [ebp+var_4]    # ? load nibble_shift //(low first)
                cdq                                 # sign extend eax into edx
                and     edx, 0FFh                   # ?
                shl     cl, 2                       # nibble_shift <<= 2
                lea     esi, [edx+eax]              # ? predicted = ? + predicted
                sar     esi, 8                      # predicted >>= 8

              * mov     eax, [ebp+arg_0]            # (load p_frame)
                movzx   edx, byte ptr [eax]         # load (uint8)byte
                shr     edx, cl                     # nibble >>= nibble_shift
                and     edx, 0Fh                    # nibble &= 0xf
                movsx   ecx, di                     # scale = signed(scale)
                mov     [ebp+arg_4], edx            # (save nibble)
                test    dl, 8                       # if (nibble is ???)
                jz      short loc_412656            # 
                lea     eax, [edx-10h]              # load scale
                imul    eax, ecx                    # nibble *= scale
                jmp     short loc_41265B            # 

loc_412656:                             ; CODE XREF: sub_4125A0+AC↑j
                mov     eax, ecx                    # ? 
                imul    eax, edx                    # ?

                                                    #(clamp16)
loc_41265B:                                         
                add     esi, eax                    # predicted += nibble
                cmp     esi, 0FFFF8000h             # if (predicted < -32768)
                jge     short loc_41266C            # T: ignore
                mov     esi, 0FFFF8000h             # F:  predicted = -32768
                jmp     short loc_41267A            # 
loc_41266C:
                cmp     esi, 7FFFh                  # if (predicted > 32767)
                mov     eax, 7FFFh                  # (prepare)
                cmovg   esi, eax                    # F:  predicted = 32767
loc_41267A:                            
                mov     edi, [ebp+arg_8]            # (load p_buffer)
                mov     edx, [ebp+arg_C]            # (load channels)
                mov     [edi], si                   # *p_buffer = predicted
                lea     edi, [edi+edx*2]            # p_buffer += channels*2
              * mov     [ebp+arg_8], edi            # (save p_buffer)
                
                mov     edx, [ebp+arg_4]            # (load nibble)
                mov     eax, ds:dword_43BC38[edx*4] # step = msadpcm_steps[nibble]
                imul    eax, ecx                    # step *= scale
                cdq                                 # ? copy sign to edx
                and     edx, 0FFh                   # ?
                add     eax, edx                    # step += ?
                mov     edx, 10h                    # 
                sar     eax, 8                      # step >> 8
                movzx   eax, ax                     # ? adjust new scale to 0x10
                cmp     ax, 10h                     # 
                mov     [ebp+arg_4], eax            # 
                cmovl   eax, edx                    # 
                mov     [ebp+arg_4], eax            # 
                movzx   eax, bx                     # 
                mov     [ebp+var_10], eax           # 
                movzx   eax, si                     # 
                mov     [ebp+var_C], eax            # 
                mov     eax, [ebp+var_4]            # 
                inc     eax                         # 
                mov     [ebp+var_4], eax            # 
                cmp     eax, 2                      # 
                jge     short loc_4126E6            # 
                mov     di, word ptr [ebp+arg_4]    # 
                mov     bx, word ptr [ebp+var_C]    # 
                mov     cx, word ptr [ebp+var_10]   # 
                mov     esi, [ebp+var_14]           # (restore coef1)
                mov     eax, [ebp+var_18]           # (restore coef2)
                jmp     loc_412617                  # loopB next byte
; ---------------------------------------------------------------------------

loc_4126E6:                             ; CODE XREF: sub_4125A0+12D↑j
                mov     eax, [ebp+arg_0]            # 
                inc     eax                         # 
                mov     [ebp+arg_0], eax            # 
                cmp     eax, [ebp+var_8]            # 
                jnb     short loc_41270C            # 
                mov     di, word ptr [ebp+arg_4]    # 
                mov     bx, word ptr [ebp+var_C]    # 
                mov     cx, word ptr [ebp+var_10]   # 
                mov     esi, [ebp+var_14]           # (restore coef1)
                mov     eax, [ebp+var_18]           # (restore coef2)
                jmp     loc_412610                  # loopB next byte
; ---------------------------------------------------------------------------

loc_412709:                             ; CODE XREF: sub_4125A0+64↑j
                mov     edi, [ebp+arg_8]            # 

loc_41270C:                             ; CODE XREF: sub_4125A0+150↑j
                sub     edi, [ebp+var_1C]           # 
                sar     edi, 1                      # 
                mov     eax, edi                    # 
                pop     edi                         # 
                cdq                                 # 
                idiv    [ebp+arg_C]                 # 
                pop     esi                         # 
                pop     ebx                         # restore 
                mov     esp, ebp                    # 
                pop     ebp                         # 
                retn                                # 
sub_4125A0      endp                                # 
```

# WV6 IMA
 ```
 sub_4F14C0      proc near               ; CODE XREF: sub_4F1800+3D↓p
                                         ; sub_4F1800+69↓p ...

 arg_0           = dword ptr  4
 arg_4           = dword ptr  8
 arg_8           = dword ptr  0Ch
 arg_C           = dword ptr  10h

                 mov     edx, [esp+arg_C]                   #
                 test    edx, edx                           #
                 jz      locret_4F17D8                      #
                 mov     eax, [esp+arg_4]                   #
                 shr     edx, 1                             #
                 mov     [ecx+10h], edx                     #
                 mov     edx, [esp+arg_8]                   #
                 push    ebx                                #
                 shr     edx, 1                             #
                 push    ebp                                #
                 mov     [ecx+4], eax                       #
                 add     eax, edx                           #
                 push    esi                                #
                 mov     esi, [esp+0Ch+arg_0]               #
                 xor     edx, edx                           #
                 cmp     [ecx+28h], dl                      #
                 push    edi                                #
                 mov     [ecx], esi                         #
                 mov     [ecx+18h], eax                     #
                 mov     [ecx+1Ch], esi                     #
                 mov     edi, 7                             #
                 jz      loc_4F15AF                         #
                 mov     [ecx+28h], dl                      #
                 xor     edx, edx                           # 
                 mov     dl, [eax]                          #  
                 and     edx, 0Fh                           # 
                 inc     eax                                #
                 
                 mov     [ecx+18h], eax                     #       
                 mov     eax, edx                           # 
                 mov     [ecx+14h], edx                     #       
                 sar     eax, 2                             #
               * mov     ebp, 2                             #
                 and     eax, ebp                           # sample &=2 
                 mov     edx, 1                             #
                 sub     edx, eax                           #
                 mov     eax, [ecx+14h]                     #
                 and     eax, edi                           #
                 mov     [ecx+20h], edx                     #
                 mov     edx, [ecx+8]                       #
                 mov     [ecx+14h], eax                     #
                 mov     edx, [ecx+edx*4+2Ch]               #
                 imul    edx, eax                           #
                 mov     eax, edx                           #
                 sar     eax, 3                             #
                 sar     edx, 2                             #
                 add     eax, edx                           #
                 imul    eax, [ecx+20h]                     #
                 mov     edx, [ecx+0Ch]                     #
                 add     edx, eax                           # sample += sample
                 mov     [ecx+24h], eax                     
                 mov     eax, edx                           # (copy sample)

                                                            # (clamp)
               * mov     ebx, 7FFFh                         # (test = 32767)
                 cmp     eax, ebx                           # if(sample > 32767)
                 mov     [ecx+0Ch], edx                     # (save sample)
                 jle     short loc_4F1562                   # FALS: goto -32768
                 mov     [ecx+0Ch], ebx                     # TRUE: sample = 32767
                 jmp     short loc_4F1570                   # 
 ; ---------------------------------------------------------------------------

 loc_4F1562:                             ; CODE XREF: sub_4F14C0+9B↑j
                 cmp     eax, 0FFFF8000h                    # if(sample <= -32768)
                 jge     short loc_4F1570                   # 
                 mov     dword ptr [ecx+0Ch], 0FFFF8000h    # sample = -32768

 loc_4F1570:                             ; CODE XREF: sub_4F14C0+A0↑j
                                         ; sub_4F14C0+A7↑j
                 mov     ax, [ecx+0Ch]                      # ? load sample
                 mov     [esi], ax                          # ? save sample

                 mov     eax, [ecx+1Ch]                     # ? table stuff
                 mov     esi, [ecx+8]                       # 
                 add     eax, ebp                           # 
                 mov     [ecx+1Ch], eax                     # 
                 mov     eax, [ecx+14h]                     # 
                 mov     eax, [ecx+eax*4+190h]              # 
                 add     esi, eax                           # step_index += table
                 mov     edx, 1                             # 
                 mov     [ecx+8], esi                       # (save step_index)
                 mov     eax, esi                           # 
                 jns     short loc_4F15A3                   # if(step_index < 0)
                 mov     dword ptr [ecx+8], 0               # step_index = 0
                 jmp     short loc_4F15AF                   # 

 loc_4F15A3:                             ; CODE XREF: sub_4F14C0+D8↑j
                 cmp     eax, 58h                           # if(step_index > 88)
                 jle     short loc_4F15AF                   # FALS: ignore
                 mov     dword ptr [ecx+8], 58h             # TRUE: step_index = 88
                                                            #
 loc_4F15AF:                             ; CODE XREF: sub_4F14C0+44↑j
                                         ; sub_4F14C0+E1↑j ...
                 mov     eax, [ecx+10h]                     #
                 mov     esi, [esp+10h+arg_C]               #
                 lea     edx, [edx+eax*2]                   #
                 cmp     edx, esi                           #
                 mov     [esp+10h+arg_0], edx               #
                 jbe     short loc_4F15CB                   #
                 sub     edx, ebp                           #
                 dec     eax                                #
                 mov     [esp+10h+arg_0], edx               #
                 mov     [ecx+10h], eax                     #

 loc_4F15CB:                             ; CODE XREF: sub_4F14C0+FF↑j
                 mov     eax, [ecx+10h]
                 test    eax, eax
                 jz      loc_4F1727

                                                            # upper nibble
 loc_4F15D6:                             ; CODE XREF: sub_4F14C0+25D↓j
                 mov     edx, [ecx+18h]                     # load? p_frame
                 movzx   eax, byte ptr [edx]                # byte = (uint8)*p_frame
                 shr     eax, 4                             # byte >>= 4 //upper nibble
                 mov     [ecx+14h], eax                     # save unsigned nibble

                                                            #(bizarro get sign)
                 sar     eax, 2                             # nibble >>= 2
                 and     eax, ebp                           # nibble &= 2
                 mov     edx, 1                             # sign = 1
                 sub     edx, eax                           # sign -= nibble //should get sign
               * mov     [ecx+20h], edx                     # save sign

                 mov     eax, [ecx+14h]                     # load unsigned nibble
                 and     eax, edi                           # nibble &= 7
                 mov     edx, [ecx+8]                       # ? load step_index?
                 mov     [ecx+14h], eax                     # save nibble
                 mov     edx, [ecx+edx*4+2Ch]               # ? load step
                 
                 imul    edx, eax                           # step *= nibble
                 mov     eax, edx                           # delta = step
                 sar     eax, 3                             # delta >>= 3
                 sar     edx, 2                             # step >>= 2
                 add     eax, edx                           # delta += step
                 imul    eax, [ecx+20h]                     # delta *= sign
                                                            # AKA: (signed)(nibble*step>>3 + nibble*step>>2)

               * mov     esi, [ecx+0Ch]                     # load hist1
                 add     esi, eax                           # hist1 += delta
                 mov     [ecx+24h], eax                     # (save delta? useless)
                 mov     eax, esi                           # sample = hist

                 cmp     eax, ebx                           # clamp sample
                 mov     [ecx+0Ch], esi
                 jle     short loc_4F1627
                 mov     [ecx+0Ch], ebx
                 jmp     short loc_4F1635
 ; ---------------------------------------------------------------------------

 loc_4F1627:                             ; CODE XREF: sub_4F14C0+160↑j
                 cmp     eax, 0FFFF8000h
                 jge     short loc_4F1635
                 mov     dword ptr [ecx+0Ch], 0FFFF8000h

 loc_4F1635:                             ; CODE XREF: sub_4F14C0+165↑j
                                         ; sub_4F14C0+16C↑j
                 mov     eax, [ecx+1Ch]
                 mov     dx, [ecx+0Ch]
                 mov     [eax], dx
                 mov     edx, [ecx+1Ch]
                 mov     eax, [ecx+14h]
                 add     edx, ebp
                 mov     [ecx+1Ch], edx
                 mov     esi, edx
                 mov     edx, [ecx+eax*4+190h]
                 mov     eax, [ecx+8]
                 add     eax, edx
                 mov     [ecx+8], eax
                 jns     short loc_4F1666
                 mov     dword ptr [ecx+8], 0
                 jmp     short loc_4F1672
 ; ---------------------------------------------------------------------------

 loc_4F1666:                             ; CODE XREF: sub_4F14C0+19B↑j
                 cmp     eax, 58h
                 jle     short loc_4F1672
                 mov     dword ptr [ecx+8], 58h

 loc_4F1672:                             ; CODE XREF: sub_4F14C0+1A4↑j
                                         ; sub_4F14C0+1A9↑j
                 mov     eax, [ecx+18h]
                 xor     edx, edx
                 mov     dl, [eax]
                 and     edx, 0Fh
                 inc     eax
                 mov     [ecx+18h], eax
                 mov     eax, edx
                 mov     [ecx+14h], edx
                 sar     eax, 2
                 and     eax, ebp
                 mov     edx, 1
                 sub     edx, eax
                 mov     eax, [ecx+14h]
                 and     eax, edi
                 mov     [ecx+20h], edx
                 mov     edx, [ecx+8]
                 mov     [ecx+14h], eax
                 mov     edx, [ecx+edx*4+2Ch]
                 imul    edx, eax
                 mov     eax, edx
                 sar     eax, 3
                 sar     edx, 2
                 add     eax, edx
                 imul    eax, [ecx+20h]
                 mov     edx, [ecx+0Ch]
                 add     edx, eax
                 mov     [ecx+24h], eax
                 mov     eax, edx
                 cmp     eax, ebx
                 mov     [ecx+0Ch], edx
                 jle     short loc_4F16CA
                 mov     [ecx+0Ch], ebx
                 jmp     short loc_4F16D8
 ; ---------------------------------------------------------------------------

 loc_4F16CA:                             ; CODE XREF: sub_4F14C0+203↑j
                 cmp     eax, 0FFFF8000h
                 jge     short loc_4F16D8
                 mov     dword ptr [ecx+0Ch], 0FFFF8000h

 loc_4F16D8:                             ; CODE XREF: sub_4F14C0+208↑j
                                         ; sub_4F14C0+20F↑j
                 mov     ax, [ecx+0Ch]
                 mov     [esi], ax
                 mov     esi, [ecx+1Ch]
                 mov     edx, [ecx+14h]
                 add     esi, ebp
                 mov     [ecx+1Ch], esi
                 mov     eax, [ecx+edx*4+190h]
                 mov     edx, [ecx+8]
                 add     edx, eax
                 mov     [ecx+8], edx
                 mov     eax, edx
                 jns     short loc_4F1706
                 mov     dword ptr [ecx+8], 0
                 jmp     short loc_4F1712
 ; ---------------------------------------------------------------------------

 loc_4F1706:                             ; CODE XREF: sub_4F14C0+23B↑j
                 cmp     eax, 58h
                 jle     short loc_4F1712
                 mov     dword ptr [ecx+8], 58h

 loc_4F1712:                             ; CODE XREF: sub_4F14C0+244↑j
                                         ; sub_4F14C0+249↑j
                 mov     edx, [ecx+10h]
                 dec     edx
                 mov     eax, edx
                 test    eax, eax
                 mov     [ecx+10h], edx
                 jnz     loc_4F15D6
                 mov     edx, [esp+10h+arg_0]

 loc_4F1727:                             ; CODE XREF: sub_4F14C0+110↑j
                 cmp     edx, [esp+10h+arg_C]
                 jnb     loc_4F17D4
                 mov     edx, [ecx+18h]
                 mov     byte ptr [ecx+28h], 1
                 movzx   eax, byte ptr [edx]
                 shr     eax, 4
                 mov     [ecx+14h], eax
                 sar     eax, 2
                 and     eax, ebp
                 mov     edx, 1
                 sub     edx, eax
                 mov     eax, [ecx+14h]
                 and     eax, edi
                 mov     [ecx+20h], edx
                 mov     edx, [ecx+8]
                 mov     [ecx+14h], eax
                 mov     edx, [ecx+edx*4+2Ch]
                 mov     esi, [ecx+0Ch]
                 imul    edx, eax
                 mov     eax, edx
                 sar     eax, 3
                 sar     edx, 2
                 add     eax, edx
                 imul    eax, [ecx+20h]
                 add     esi, eax
                 mov     [ecx+24h], eax
                 mov     eax, esi
                 cmp     eax, ebx
                 mov     [ecx+0Ch], esi
                 jle     short loc_4F1786
                 mov     [ecx+0Ch], ebx
                 jmp     short loc_4F1794
 ; ---------------------------------------------------------------------------

 loc_4F1786:                             ; CODE XREF: sub_4F14C0+2BF↑j
                 cmp     eax, 0FFFF8000h
                 jge     short loc_4F1794
                 mov     dword ptr [ecx+0Ch], 0FFFF8000h

 loc_4F1794:                             ; CODE XREF: sub_4F14C0+2C4↑j
                                         ; sub_4F14C0+2CB↑j
                 mov     eax, [ecx+1Ch]
                 mov     dx, [ecx+0Ch]
                 mov     [eax], dx
                 mov     edx, [ecx+1Ch]
                 mov     eax, [ecx+14h]
                 add     edx, ebp
                 mov     [ecx+1Ch], edx
                 mov     edx, [ecx+eax*4+190h]
                 mov     eax, [ecx+8]
                 add     eax, edx
                 mov     [ecx+8], eax
                 jns     short loc_4F17C8
                 pop     edi
                 pop     esi
                 pop     ebp
                 mov     dword ptr [ecx+8], 0
                 pop     ebx
                 retn    10h
 ; ---------------------------------------------------------------------------

 loc_4F17C8:                             ; CODE XREF: sub_4F14C0+2F8↑j
                 cmp     eax, 58h
                 jle     short loc_4F17D4
                 mov     dword ptr [ecx+8], 58h

 loc_4F17D4:                             ; CODE XREF: sub_4F14C0+26B↑j
                                         ; sub_4F14C0+30B↑j
                 pop     edi
                 pop     esi
                 pop     ebp
                 pop     ebx

 locret_4F17D8:                          ; CODE XREF: sub_4F14C0+6↑j
                 retn    10h
 sub_4F14C0      endp
 ```

# XMD decoder (SH4 xbe)
```
sub_17AE0

 var_8           = dword ptr -8
 var_1           = byte ptr -1
 arg_0           = dword ptr  8
 arg_4           = dword ptr  0Ch

   push    ebp                  
   mov     ebp, esp
   sub     esp, 8
   push    ebx
   mov     [ebp+var_1], 7        
   mov     eax, [ebp+arg_4]     
   mov     ebx, [ebp+arg_0]     
   mov     cl, [eax]
   mov     [ebx], cl
   inc     eax
   inc     ebx
   mov     ch, [eax]
   mov     [ebx], ch
   inc     eax
   inc     ebx
   mov     dl, [eax]
   mov     [ebx], dl
   inc     eax
   inc     ebx
   mov     dh, [eax]
   mov     [ebx], dh
   inc     eax
   inc     ebx
   push    dx                   
   push    cx                   

   mov     ecx, 0               # scale = 0
   mov     cx, [eax]            # load 
   add     eax, 2               # p_frame += 2 //skip scale
   shl     ecx, 0Eh             # scale <<= 14
   mov     [ebp+var_8], ecx     # save scale

loc_17B1E:                      #(loop: next byte)

   mov     ecx, [ebp+var_8]     # (reload scale after loop)
   mov     dl, [eax]            # byte = (uint8)*p_frame
   shl     edx, 1Ch             # (sign extend low nibble, pt1)
   sar     edx, 1Ch             # (sign extend low nibble, pt2)
   imul    ecx, edx             # sample *= scale

   pop     dx                   # load hist2
   shl     edx, 10h             # (sign extend hist2, pt1)
   sar     edx, 10h             # (sign extend hist2, pt2)
   imul    edx, 3350h           # hist2 *= coef2
   sub     ecx, edx             # sample -= hist2

   pop     dx                   # ? save hist2 as hist1
   push    dx                   # load hist1
   shl     edx, 10h             # (sign extend hist1, pt1)
   sar     edx, 10h             # (sign extend hist2, pt1)  
   imul    edx, 7298h           # hist1 *= coef1
   add     ecx, edx             # sample += hist1
   sar     ecx, 0Eh             # sample >>= 14

   mov     [ebx], cl            # save sample, low byte
   inc     ebx                  # p_buffer += 1
   mov     [ebx], ch            # save sample, high byte
   inc     ebx                  # p_buffer += 1

   pop     dx                   # save hist1/2 and repeat for high nibble
   push    cx
   push    dx
   mov     ecx, [ebp+var_8]
   mov     dl, [eax]
   shl     edx, 18h
   sar     edx, 1Ch
   imul    ecx, edx
   inc     eax
   pop     dx
   shl     edx, 10h
   sar     edx, 10h
   imul    edx, 3350h
   sub     ecx, edx
   pop     dx
   push    dx
   shl     edx, 10h
   sar     edx, 10h
   imul    edx, 7298h
   add     ecx, edx
   sar     ecx, 0Eh
   mov     [ebx], cl
   inc     ebx
   mov     [ebx], ch
   inc     ebx
   pop     dx
   push    cx
   push    dx
   dec     [ebp+var_1]          
   jnz     loc_17B1E            #jump next byte
   
   pop     dx                   
   pop     dx
   pop     ebx
   mov     esp, ebp
   pop     ebp
   retn    8
sub_17AE0       endp
```

# XMD decoder (xmddecode.dll)
```
# from xmddecode.dll (sh_sounds_explorer_1.7)
 
# some parts (*) where reordered to simplify logic
sub_10006F50
 arg_0           = dword ptr  4
 arg_4           = dword ptr  8
 arg_8           = dword ptr  0Ch
 arg_C           = dword ptr  10h
 arg_10          = dword ptr  14h
                                    # esp: pointer table?
* push    ebp                       # (save external value)
* push    edi                       # (save external value)
* push    ebx                       # (save external value)
* push    esi                       # (save external value)
* xor     ebp, ebp                  # (scale = 0)
 
  mov     eax, [esp+arg_C]          # load p_hist1
  mov     edx, [esp+arg_10]         # load p_hist2
* movsx   ecx, word ptr [eax]       # hist1 = (int16)*p_hist1
* movsx   eax, word ptr [edx]       # hist2 = (int16)*p_hist2
 
                                    # (frame hist2/1 is already consumed)
  mov     edi, [esp+8+arg_4]        # load p_frame
  mov     bp, [edi]                 # scale = (uint16)*p_frame
* shl     ebp, 0Eh                  # scale <<= 14
 
  mov     edx, [esp+8+arg_8]        # load bytes_left
  test    edx, edx                  # check if bytes_left == 0
  jle     loc_10007007              # end if true
 
* add     edi, 2                    # p_frame += 2 //skip scale
  mov     esi, [esp+10h+arg_0]      # load p_buffer
  mov     [esp+10h+arg_C], edx      # save bytes_left
 
 
 loc_10006F85:                      # (loop location)
 
  ****** nibble1 ******
  mov     dl, [edi]                 # byte = (uint8)*p_frame
  and     edx, 0Fh                  # byte &= 0xF //get lower nibble
  test    dl, 8                     # check sign
  jz      short loc_10006F92        # JUMP: not signed
  or      edx, 0FFFFFFF0h           # NOJM: signed, sign extend
  loc_10006F92:
  mov     ebx, ebp                  # (copy scale)
  add     esi, 2                    # p_buffer += 2
  imul    ebx, edx                  # sample *= scale
  mov     edx, ecx                  # (copy hist1)
  imul    edx, 7298h                # hist1 *= 0x7298 //coef1
  add     ebx, edx                  # sample += hist1
 
  lea     edx, [eax+eax*4]          # hist2b = hist2  + hist2*4
  lea     edx, [eax+edx*8]          # hist2b = hist2  + hist2b*8
  lea     edx, [edx+edx*4]          # hist2b = hist2b + hist2b*4
  lea     eax, [eax+edx*4]          # hist2  = hist2  + hist2b*4
  shl     eax, 4                    # hist2 <<= 4
                                    # AKA: (hist2 + (((hist2*5 + hist2)*8)*5)*4) << 4
                                    # AKA: (hist2 + ((5*8+1)*5*4+1)) << 4 = hist2 * 0x335*10
                                    # hist2 *= 0x3350 //coef2
 
  sub     ebx, eax                  # sample -= hist2
  sar     ebx, 0Eh                  # sample >>= 14
  mov     eax, ebx                  # (copy sample)
  mov     [esi-2], ax               # *p_buffer-2 = (int16)sample
 
* xor     edx, edx                  # byte = 0 //clean upper bits
 
  ****** nibble2 ******
  mov     dl, [edi]                 # byte = *p_frame
  shr     edx, 4                    # byte >> 4 //get upper nibble
  test    dl, 8                     # (check sign)
  jz      short loc_10006FCD        # JUMP: not signed
  or      edx, 0FFFFFFF0h           # NOJM: signed, sign extend
  loc_10006FCD:
  mov     ebx, ebp                  # (copy scale)
  add     esi, 2                    # p_buffer += 2
  imul    ebx, edx                  # sample *= scale
  mov     edx, eax                  # (copy hist1 = sample)
  imul    edx, 7298h                # hist1 *= 0x7298
  add     ebx, edx                  # sample += hist1
 
  lea     edx, [ecx+ecx*4]          # hist2b = hist2  + hist2*4
  lea     edx, [ecx+edx*8]          # hist2b = hist2  + hist2b*8
  lea     edx, [edx+edx*4]          # hist2b = hist2b + hist2b*4
  lea     ecx, [ecx+edx*4]          # hist2  = hist2  + hist2b*4
                                    # AKA: hist2 + (((hist2*5 + hist2)*8)*5)*4
                                    # AKA: hist2 * ((5*8+1)*5*4+1) = hist2 * 0x335
  shl     ecx, 4                    # hist2 <<= 4
                                    # AKA: hist2 * 0x3350
 
  sub     ebx, ecx                  # sample -= hist2
  sar     ebx, 0Eh                  # sample >>= 14
  mov     ecx, ebx                  # (copy sample)
  mov     [esi-2], cx               # *p_buffer-2 = (int16)sample
 
* inc     edi                       # p_frame += 1
* mov     edx, [esp+10h+arg_C]      # load bytes_left
  dec     edx                       # bytes_left--
  mov     [esp+10h+arg_C], edx      # save bytes_left
  jnz     short loc_10006F85        # JUMP (process next byte)
 
***
 loc_10007007:
* pop     esi                       # (restore external value)
* pop     ebx                       # (restore external value)
  pop     edi                       # (restore external value)
  pop     ebp                       # (restore external value)
  retn
  endp
```
