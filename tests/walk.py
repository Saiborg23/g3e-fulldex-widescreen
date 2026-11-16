import sys
out, moves = sys.argv[1], sys.argv[2]
L=[]
for f in range(400, 4500, 18): L.append(f"key {f} X 3")
for f in range(4500, 5600, 18): L.append(f"key {f} Z 3")
f = 5600; n = 0
for tok in moves.split():
    if tok.startswith('dump:'):
        L.append(f"dump {f} SHOTDIR/{tok[5:]}.bin"); continue
    if tok.startswith('shot'):
        L.append(f"shot {f} SHOTDIR/{tok[5:] or 'p%02d'%n}.bmp"); n += 1; continue
    if tok.startswith('wait'): f += int(tok[4:]); continue
    if tok.startswith('P:'):   # P:SDLKEY:HOLD  press without advancing time (for combos)
        _, kk, hh = tok.split(':'); L.append(f"key {f} {kk} {hh}"); continue
    if tok.startswith('H:'):   # H:KEY:HOLD  long press
        _, kk, hh = tok.split(':'); k = {'A':'X','B':'Z','S':'Return','U':'Up','D':'Down','L':'Left','R':'Right'}[kk]
        L.append(f"key {f} {k} {hh}"); f += int(hh) + 12; continue
    if tok.startswith('M:'):
        k = {'R':'Right','L':'Left','U':'Up','D':'Down'}[tok[2]]
        L.append(f"key {f} {k} 17"); L.append(f"shot {f+9} SHOTDIR/m{n:02d}.bmp"); n += 1; f += 22; continue
    k = {'R':'Right','L':'Left','U':'Up','D':'Down','A':'X','B':'Z','S':'Return'}[tok[0]]; c = int(tok[1:] or 1)
    for _ in range(c):
        hold = 3 if k in ('X','Z','Return') else 17
        L.append(f"key {f} {k} {hold}"); f += 22 if k not in ('X','Z','Return') else 30
L.append(f"shot {f+60} SHOTDIR/final.bmp"); L.append(f"quit {f+70}")
open(out,'w').write("\n".join(L)+"\n")
