import os
"""
Figure 1 v4 — Three-Layer Safety Gate Architecture
Clean symmetric layout. BLOCK centered under L1-L3.
"""

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch
import numpy as np

# ── Palette ───────────────────────────────────────────────────────────────────
CL1F='#f8cecc'; CL1S='#b85450'
CL2F='#fff2cc'; CL2S='#d6b656'
CL3F='#d5e8d4'; CL3S='#82b366'
CIF ='#dae8fc'; CIS ='#6c8ebf'
CKF ='#e1d5e7'; CKS ='#9673a6'
CBF ='#f8cecc'; CBS ='#b85450'
CAF ='#d5e8d4'; CAS ='#82b366'
CRED='#cc0000'; CGRN='#009900'; CGR='#666666'

fig, ax = plt.subplots(figsize=(14.5, 5.5))
ax.set_xlim(-0.3, 14.3)
ax.set_ylim(0.0, 5.5)
ax.axis('off')
fig.patch.set_facecolor('white')

# ── Primitives ────────────────────────────────────────────────────────────────
def rbox(x, y, w, h, fc, ec, lw=1.5, r=0.28, z=3):
    ax.add_patch(FancyBboxPatch((x,y), w, h,
        boxstyle=f"round,pad=0,rounding_size={r}",
        facecolor=fc, edgecolor=ec, linewidth=lw, zorder=z, clip_on=False))

def hexbox(cx, cy, w, h, fc, ec, lw=1.5, z=3):
    ind = w*0.18
    xs = [cx-w/2+ind, cx+w/2-ind, cx+w/2, cx+w/2-ind, cx-w/2+ind, cx-w/2, cx-w/2+ind]
    ys = [cy+h/2,     cy+h/2,     cy,      cy-h/2,     cy-h/2,     cy,     cy+h/2]
    ax.fill(xs, ys, color=fc, zorder=z)
    ax.plot(xs, ys, color=ec, linewidth=lw, zorder=z)

def parallelogram(x, y, w, h, fc, ec, skew=0.22, lw=1.5, z=3):
    xs = [x+skew, x+w+skew, x+w, x, x+skew]
    ys = [y+h,    y+h,       y,   y, y+h]
    ax.fill(xs, ys, color=fc, zorder=z)
    ax.plot(xs, ys, color=ec, linewidth=lw, zorder=z)

def cylinder(cx, cy, w, h, fc, ec, lw=1.5, z=3):
    ry = h*0.14
    ax.add_patch(plt.Rectangle((cx-w/2, cy-h/2), w, h, facecolor=fc, edgecolor='none', zorder=z))
    for sign, ez in [(-1,1),(1,2)]:
        ax.add_patch(mpatches.Ellipse((cx, cy+sign*h/2), w, ry*2,
            facecolor=fc, edgecolor=ec, linewidth=lw, zorder=z+ez))
    ax.plot([cx-w/2,cx-w/2],[cy-h/2,cy+h/2], color=ec, lw=lw, zorder=z)
    ax.plot([cx+w/2,cx+w/2],[cy-h/2,cy+h/2], color=ec, lw=lw, zorder=z)

def T(x, y, s, fs=9, c='black', ha='center', va='center', bold=False, italic=False, z=7):
    ax.text(x,y,s, fontsize=fs, color=c, ha=ha, va=va,
            fontweight='bold' if bold else 'normal',
            fontstyle='italic' if italic else 'normal', zorder=z)

def A(x1,y1,x2,y2, col='#333333', lw=1.8, conn='arc3,rad=0.0', dash=False, z=5):
    ax.annotate('', xy=(x2,y2), xytext=(x1,y1),
        arrowprops=dict(arrowstyle='->', color=col, lw=lw,
                        connectionstyle=conn,
                        linestyle='--' if dash else '-'),
        zorder=z, annotation_clip=False)

# ── Layout ────────────────────────────────────────────────────────────────────
# Input
IX,IY,IW,IH = 0.05, 2.35, 1.5, 1.0
ICX = IX+IW/2+0.11

# Layers — evenly spaced
LY=2.2; LW=2.2; LH=1.35; LGAP=0.9
L1X = 2.1;  L1CX,L1CY = L1X+LW/2, LY+LH/2    # cx=3.2
L2X = L1X+LW+LGAP;  L2CX,L2CY = L2X+LW/2, LY+LH/2    # cx=6.3
L3X = L2X+LW+LGAP;  L3CX,L3CY = L3X+LW/2, LY+LH/2    # cx=9.4

# BLOCK — centered under L1-L3 (x midpoint), low y
BCX = (L1CX + L3CX)/2      # = (3.2+9.4)/2 = 6.3  ← same as L2CX (perfect)
BCY = 0.90; BW=1.6; BH=0.78

# ALLOW — far right of L3
ACX = 12.8; ACY = LY+LH/2; AW=1.6; AH=0.78

# KG — to the right and below L3 (doesn't conflict with BLOCK path)
KGCX,KGCY = 11.2, 0.88; KGCW,KGCH = 1.9, 0.72

# ── Draw ──────────────────────────────────────────────────────────────────────
# Input
parallelogram(IX, IY, IW, IH, CIF, CIS)
T(ICX, IY+IH/2+0.14, 'Tool Call', fs=10, bold=True)
T(ICX, IY+IH/2-0.18, '(action, args, context)', fs=7.5, c=CGR)

# Layers
layer_data = [
    (L1X, CL1F, CL1S, 'Layer 1', 'Deterministic Blocker',
     'Datalog constraints','62 rules · P50=0.055ms','Zero FP by construction'),
    (L2X, CL2F, CL2S, 'Layer 2', 'Triviality Filter',
     'Action-type heuristics','~70% early exit','Cost-aware routing'),
    (L3X, CL3F, CL3S, 'Layer 3', 'Semantic Gate',
     'LLM + 23 minimal pairs','Intent decomposition','Majority vote (k=3)'),
]
for X,FC,EC,title,sub,d1,d2,d3 in layer_data:
    CX,CY = X+LW/2, LY+LH/2
    rbox(X, LY, LW, LH, FC, EC)
    T(CX, CY+0.43, title, fs=10.5, bold=True)
    T(CX, CY+0.14, sub, fs=9)
    T(CX, CY-0.14, d1, fs=7.5, c=CGR)
    T(CX, CY-0.33, d2, fs=7.5, c=CGR)
    T(CX, CY-0.52, d3, fs=7.5, c=CGR)

# BLOCK
hexbox(BCX, BCY, BW, BH, CBF, CBS)
T(BCX, BCY+0.15, 'BLOCK', fs=10.5, bold=True, c=CRED)
T(BCX, BCY-0.16, '+ proof trace', fs=7.5, c=CGR)

# ALLOW
hexbox(ACX, ACY, AW, AH, CAF, CAS)
T(ACX, ACY+0.15, 'ALLOW', fs=10.5, bold=True, c=CGRN)
T(ACX, ACY-0.16, '→ execute tool', fs=7.5, c=CGR)

# KG
cylinder(KGCX, KGCY, KGCW, KGCH, CKF, CKS)
T(KGCX, KGCY+0.14, 'Knowledge Graph', fs=8.5, bold=True)
T(KGCX, KGCY-0.10, '143 relations · 125 entities', fs=7, c=CGR)
T(KGCX, KGCY-0.28, 'Post-gate enrichment', fs=7, c=CGR)

# ── Arrows ────────────────────────────────────────────────────────────────────
# 1. Input → L1
A(IX+IW+0.11, IY+IH/2, L1X, L1CY)

# 2. L1 → L2 (pass)
A(L1X+LW, L1CY, L2X, L2CY)
T((L1X+LW+L2X)/2, L2CY+0.23, 'pass', fs=8.5, c=CGRN, bold=True)

# 3. L2 → L3 (ambiguous)
A(L2X+LW, L2CY, L3X, L3CY)
T((L2X+LW+L3X)/2, L3CY+0.23, 'ambiguous', fs=8, c='#cc6600')

# 4. L3 → ALLOW
A(L3X+LW, L3CY, ACX-AW/2, ACY)
T((L3X+LW + ACX-AW/2)/2, ACY+0.23, '✓ allow', fs=8.5, c=CGRN)

# 5. L1 → BLOCK (curved down-right)
#    Explicit path: L1 bottom → down-right rail → BLOCK top-left
MID_Y1 = 1.60   # intermediate y for L1 route
ax.plot([L1CX, L1CX], [LY, MID_Y1], color=CRED, lw=1.5, linestyle='--', zorder=5)
ax.plot([L1CX, BCX-BW*0.25], [MID_Y1, MID_Y1], color=CRED, lw=1.5, linestyle='--', zorder=5)
A(BCX-BW*0.25, MID_Y1, BCX-BW*0.2, BCY+BH/2, col=CRED, lw=1.5, dash=True)
T(L1CX-0.35, (LY+MID_Y1)/2, '✗', fs=13, c=CRED)

# 6. L3 → BLOCK (curved down-left, symmetric to L1)
MID_Y3 = 1.60
ax.plot([L3CX, L3CX], [LY, MID_Y3], color=CRED, lw=1.5, linestyle='--', zorder=5)
ax.plot([L3CX, BCX+BW*0.25], [MID_Y3, MID_Y3], color=CRED, lw=1.5, linestyle='--', zorder=5)
A(BCX+BW*0.25, MID_Y3, BCX+BW*0.2, BCY+BH/2, col=CRED, lw=1.5, dash=True)
T(L3CX+0.35, (LY+MID_Y3)/2, '✗', fs=13, c=CRED)

# 7. L2 → ALLOW bypass (trivially benign — go up then right)
bypass_y = 4.75
ax.plot([L2CX, L2CX, ACX], [LY+LH, bypass_y, bypass_y],
        color=CGRN, lw=1.5, linestyle='--', zorder=5)
A(ACX, bypass_y, ACX, ACY+AH/2, col=CGRN, lw=1.5, dash=True)
T((L2CX+ACX)/2, bypass_y+0.18, '✓ trivially benign (early exit)', fs=8, c=CGRN)

# 8. KG → L3 (dashed purple, up from KG to L3 right-bottom)
KG_to_L3_x = L3X+LW-0.25
ax.plot([KGCX, KG_to_L3_x], [KGCY+KGCH/2, KGCY+KGCH/2],
        color=CKS, lw=1.2, linestyle='--', zorder=5)
A(KG_to_L3_x, KGCY+KGCH/2, KG_to_L3_x, LY, col=CKS, lw=1.2, dash=True)

# ── Legend ────────────────────────────────────────────────────────────────────
lx, ly = 0.05, 0.62
for i,(ls,col,lbl) in enumerate([
    ('-', '#333333', 'main flow'),
    ('--', CRED, 'block / deny'),
    ('--', CGRN, 'allow / early exit'),
    ('--', CKS, 'auxiliary (KG)'),
]):
    yy = ly - i*0.18
    ax.plot([lx, lx+0.4], [yy,yy], ls, color=col, lw=1.7, zorder=7)
    T(lx+0.52, yy, lbl, fs=7.5, c='#333', ha='left', va='center')

# ── Shadow note ───────────────────────────────────────────────────────────────
T(7.0, 0.22, 'Shadow mode: 19,350+ calls · 99.45% consistency', fs=7.5, c='#888', italic=True)

# ── Deny labels near BLOCK ────────────────────────────────────────────────────
T(BCX, BCY+BH/2+0.15, '← from L1 · L3 →', fs=7, c=CRED)

# ── Save ─────────────────────────────────────────────────────────────────────
out_png = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'figure1.png')
out_pdf = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'figure1.pdf')
fig.savefig(out_png, dpi=220, bbox_inches='tight', facecolor='white', pad_inches=0.15)
fig.savefig(out_pdf, bbox_inches='tight', facecolor='white', pad_inches=0.15)
print(f"✅  {out_png}  (v4)")
print(f"✅  {out_pdf}  (v4)")
plt.close()
