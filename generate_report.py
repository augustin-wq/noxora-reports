"""
Noxora Report Generator — data-driven version
Accepts patient_data dict + notes dict, returns PDF as bytes.
"""

import io
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

from reportlab.lib.pagesizes import A4
from reportlab.lib.colors import HexColor, white, black
from reportlab.lib.units import mm
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT, TA_JUSTIFY
from reportlab.platypus import (
    BaseDocTemplate, Frame, PageTemplate,
    Paragraph, Spacer, Table, TableStyle, Image, PageBreak
)
from reportlab.platypus.flowables import Flowable

# ── Geometry ──────────────────────────────────────────────────────────────────
PW, PH = A4
ML = MR = 20*mm
MT = MB = 18*mm
CW = PW - ML - MR

LOGO_CARD_H  = 115
LOGO_CARD_Y1 = PH - 12
LOGO_CARD_Y0 = LOGO_CARD_Y1 - LOGO_CARD_H
PAT_CARD_H   = 155
PAT_CARD_Y1  = LOGO_CARD_Y0 - 85
PAT_CARD_Y0  = PAT_CARD_Y1 - PAT_CARD_H
LETTER_FRAME_H = int(PAT_CARD_Y0 - 12 - MB)
LETTER_FRAME_Y = int(MB)
HDR_H = 10*mm
FTR_H =  7*mm

# ── Colours ───────────────────────────────────────────────────────────────────
C_DARK  = HexColor('#1E2538');  C_DARK2 = HexColor('#252B3A')
C_DARK3 = HexColor('#2C3348');  C_GOLD  = HexColor('#C9A96E')
C_BLUE  = HexColor('#4A7A9B');  C_GREEN = HexColor('#5B8A5A')
C_RED   = HexColor('#B84433');  C_ORNG  = HexColor('#E07B39')
C_LIGHT = HexColor('#F5F5F0');  C_LGRAY = HexColor('#E0E0DA')
C_MGRAY = HexColor('#BBBBBB');  C_DKGRY = HexColor('#888888')
C_TEXT  = HexColor('#2A2A2A');  C_TEAL  = HexColor('#3D7A78')

KPI_GOOD    = {'bg': HexColor('#E6F4E6'), 'border': HexColor('#4A8A4A'),
               'val': HexColor('#1E5E1E'), 'lbl': HexColor('#3A7A3A'), 'dlt': HexColor('#1E5E1E')}
KPI_BAD     = {'bg': HexColor('#FAE9E6'), 'border': HexColor('#B84433'),
               'val': HexColor('#8C2A18'), 'lbl': HexColor('#B84433'), 'dlt': HexColor('#8C2A18')}
KPI_NEUTRAL = {'bg': HexColor('#F0F0EB'), 'border': C_LGRAY,
               'val': C_DARK, 'lbl': C_DKGRY, 'dlt': C_DKGRY}

# ── Styles ────────────────────────────────────────────────────────────────────
def S(n, **kw): return ParagraphStyle(n, **kw)

ST = {
    'body':    S('b',  fontName='Helvetica', fontSize=8.5, textColor=C_TEXT,
                       leading=13, alignment=TA_JUSTIFY, spaceBefore=2, spaceAfter=2),
    'body_l':  S('bl', fontName='Helvetica', fontSize=8.5, textColor=C_TEXT,
                       leading=13, alignment=TA_LEFT),
    'sec_lbl': S('sl', fontName='Helvetica-Bold', fontSize=7.5, textColor=C_GOLD,
                       leading=9, spaceBefore=12, spaceAfter=1),
    'sec_ttl': S('st', fontName='Helvetica-Bold', fontSize=16, textColor=C_DARK,
                       leading=20, spaceBefore=0, spaceAfter=4),
    'sub':     S('su', fontName='Helvetica-Bold', fontSize=9.5, textColor=C_DARK,
                       leading=12, spaceBefore=7, spaceAfter=3),
    'th':      S('th', fontName='Helvetica-Bold', fontSize=7.5, textColor=white,  leading=9),
    'td':      S('td', fontName='Helvetica',      fontSize=7.5, textColor=C_TEXT, leading=10),
    'tdb':     S('tb', fontName='Helvetica-Bold', fontSize=7.5, textColor=C_TEXT, leading=10),
    'tdg':     S('tg', fontName='Helvetica',      fontSize=7.5, textColor=C_DKGRY,leading=10),
    'th2':     S('h2', fontName='Helvetica-Bold', fontSize=7.5, textColor=C_DARK, leading=9),
    'legal':   S('lg', fontName='Helvetica',      fontSize=6.5, textColor=C_DKGRY,
                       leading=9.5, alignment=TA_JUSTIFY),
    'rt':      S('rt', fontName='Helvetica-Bold', fontSize=9,   textColor=C_DARK, leading=12),
    'rb':      S('rb', fontName='Helvetica',      fontSize=8,   textColor=C_TEXT,
                       leading=11, alignment=TA_JUSTIFY),
}

LTR_GOLD = ParagraphStyle('lg', fontName='Helvetica-Bold',   fontSize=10,  textColor=C_GOLD,             leading=13)
LTR_BODY = ParagraphStyle('lb', fontName='Helvetica',        fontSize=8.5, textColor=HexColor('#C5D0E0'), leading=12.5)
LTR_COMP = ParagraphStyle('lc', fontName='Helvetica',        fontSize=8.5, textColor=HexColor('#C5D0E0'), leading=12, leftIndent=10)
LTR_SIG  = ParagraphStyle('ls', fontName='Helvetica-Oblique',fontSize=8,   textColor=HexColor('#8899AA'), leading=10)
LTR_NAME = ParagraphStyle('ln', fontName='Helvetica-Bold',   fontSize=9,   textColor=HexColor('#D8E4F0'), leading=11)

def p(txt, s='td'): return Paragraph(txt, ST[s])
def sp(h): return Spacer(1, h*mm)

# ── Charts ────────────────────────────────────────────────────────────────────
def to_img(fig, w_mm, h_mm):
    buf = io.BytesIO()
    fig.savefig(buf, format='png', dpi=160, bbox_inches='tight', transparent=True)
    buf.seek(0); plt.close(fig)
    return Image(buf, width=w_mm*mm, height=h_mm*mm)

def _ax(ax, grid='y'):
    ax.set_facecolor('#F5F5F0')
    for s in ['top','right']: ax.spines[s].set_visible(False)
    for s in ['left','bottom']: ax.spines[s].set_color('#C8C8C0')
    ax.tick_params(colors='#555', labelsize=7)
    ax.grid(axis=grid, alpha=0.35, color='#C8C8C0', zorder=0)

def chart_key_params(pre_isi, post_isi, pre_psqi, post_psqi, pre_hab, post_hab):
    fig, ax = plt.subplots(figsize=(5.5, 2.1))
    fig.patch.set_facecolor('#F5F5F0')
    cats = ['Habits (0–24)', 'PSQI (0–21)', 'ISI med-adj (0–28)']
    pre  = [pre_hab, pre_psqi, pre_isi]
    post = [post_hab, post_psqi, post_isi]
    y = np.arange(3); h = 0.30
    b1 = ax.barh(y+h/2, pre,  h, color='#4A7A9B', label='Pre-SRP',  zorder=3)
    b2 = ax.barh(y-h/2, post, h, color='#5B8A5A', label='6 weeks', zorder=3)
    for b, v in zip(b1, pre):
        ax.text(v+.15, b.get_y()+b.get_height()/2, str(int(v)), va='center', ha='left', fontsize=8, fontweight='bold', color='#222')
    for b, v in zip(b2, post):
        ax.text(v+.15, b.get_y()+b.get_height()/2, str(int(v)), va='center', ha='left', fontsize=8, fontweight='bold', color='#222')
    ax.set_yticks(y); ax.set_yticklabels(cats, fontsize=8)
    ax.set_xlim(0, max(max(pre), max(post)) + 3)
    _ax(ax, 'x')
    ax.spines['left'].set_visible(False); ax.tick_params(left=False)
    ax.legend(fontsize=7, loc='lower right', framealpha=0.9, edgecolor='#C8C8C0')
    fig.tight_layout(pad=0.4)
    return to_img(fig, 145, 52)

def chart_avg_isi():
    fig, ax = plt.subplots(figsize=(5.5, 2.0))
    fig.patch.set_facecolor('#F5F5F0')
    bars = ax.bar([0,1], [15.4, 8.4], color=['#4A7A9B','#5B8A5A'], width=0.55, zorder=3, edgecolor='none')
    for b, v in zip(bars, [15.4, 8.4]):
        ax.text(b.get_x()+b.get_width()/2, v+0.3, str(v), ha='center', va='bottom', fontsize=13, fontweight='bold', color='#222')
    ax.annotate('', xy=(1,8.4), xytext=(0,15.4),
                arrowprops=dict(arrowstyle='->', color='#C9A96E', lw=1.5, connectionstyle='arc3,rad=-0.15'))
    ax.text(0.5, 11.2, '–7.0 pts\n(–45%)', ha='center', va='center', fontsize=8, color='#C9A96E', fontweight='bold')
    ax.set_xticks([0,1]); ax.set_xticklabels(['Pre-Treatment','Post-Treatment (6W)'], fontsize=9)
    ax.set_ylim(0, 21); ax.set_ylabel('Avg ISI Score', fontsize=8, color='#555')
    ax.set_title('Average Medication-Adjusted ISI Score', fontsize=9, fontweight='bold', color='#1E2538', pad=6)
    _ax(ax); fig.tight_layout(pad=0.5)
    return to_img(fig, 138, 50)

def chart_dist(which):
    fig, ax = plt.subplots(figsize=(3.2, 2.0))
    fig.patch.set_facecolor('#F5F5F0')
    cats = ['0-3','4-6','7-9','10-12','13-15','16-18','19-21']
    if which == 'pre':
        vals = [0,4,9,0,39,30,17]; col = '#4A7A9B'; title = 'Pre-Treatment'
    else:
        vals = [23,11,26,5,5,5,0]; col = '#5B8A5A'; title = 'Post-Treatment (6W)'
    bars = ax.bar(range(len(cats)), vals, color=col, width=0.7, zorder=3, edgecolor='none')
    ax.set_xticks(range(len(cats))); ax.set_xticklabels(cats, fontsize=6.5)
    for b, v in zip(bars, vals):
        if v > 0:
            ax.text(b.get_x()+b.get_width()/2, v+0.8, f'{v}%', ha='center', va='bottom', fontsize=7, fontweight='bold', color='#222')
    ax.set_ylim(0, 52)
    ax.set_title(title, fontsize=9, fontweight='bold', color='#1E2538', pad=4)
    ax.set_ylabel('% of participants', fontsize=7, color='#555')
    _ax(ax); fig.tight_layout(pad=0.4)
    return to_img(fig, 78, 50)

def chart_time_impact():
    fig, ax = plt.subplots(figsize=(5.5, 2.0))
    fig.patch.set_facecolor('#F5F5F0')
    cats = ['6 weeks or more','3–5 weeks','2–3 weeks','1 week']
    vals = [18, 36, 18, 27]
    colors = ['#C86830','#E07B39','#E8954A','#F0A860']
    bars = ax.barh(cats, vals, color=colors, height=0.55, zorder=3, edgecolor='none')
    for b, v in zip(bars, vals):
        ax.text(v+0.6, b.get_y()+b.get_height()/2, f'{v}%', va='center', ha='left', fontsize=9, fontweight='bold', color='#222')
    ax.set_xlim(0, 50)
    ax.set_xlabel('% of participants', fontsize=7, color='#555')
    ax.set_title('Time After Treatment to Feel Positive Impact', fontsize=9, fontweight='bold', color='#1E2538', pad=5)
    _ax(ax, 'x')
    ax.spines['left'].set_visible(False); ax.tick_params(left=False)
    ax.tick_params(axis='y', labelsize=8)
    fig.tight_layout(pad=0.5)
    return to_img(fig, 138, 50)

# ── Flowables ─────────────────────────────────────────────────────────────────
class SectionHdr(Flowable):
    def __init__(self, label, title):
        super().__init__(); self.label=label; self.title=title
    def wrap(self,aW,aH): self._w=aW; return aW, 36
    def draw(self):
        c=self.canv
        c.setFillColor(C_GOLD); c.rect(0,2,3,32,fill=1,stroke=0)
        c.setFont('Helvetica-Bold',7.5); c.setFillColor(C_GOLD); c.drawString(10,27,self.label)
        c.setFont('Helvetica-Bold',16); c.setFillColor(C_DARK); c.drawString(10,9,self.title)

class MiniHdr(Flowable):
    def __init__(self, label, title):
        super().__init__(); self.label=label; self.title=title
    def wrap(self,aW,aH): self._w=aW; return aW, 24
    def draw(self):
        c=self.canv
        c.setFillColor(C_GOLD); c.rect(0,0,2.5,22,fill=1,stroke=0)
        c.setFont('Helvetica-Bold',6.5); c.setFillColor(C_GOLD); c.drawString(8,17,self.label)
        c.setFont('Helvetica-Bold',11); c.setFillColor(C_DARK); c.drawString(8,5,self.title)

class GoldHR(Flowable):
    def wrap(self,aW,aH): self._w=aW; return aW,3
    def draw(self):
        c=self.canv; c.setStrokeColor(C_GOLD); c.setLineWidth(0.7); c.line(0,1,self._w,1)

class ClinNote(Flowable):
    def __init__(self, label='CLINICIAN NOTES', text='', placeholder='', height=22*mm, width=None):
        super().__init__(); self.label=label; self.text=text; self.ph=placeholder
        self._hh=height; self._fw=width
    def wrap(self,aW,aH): self._w=self._fw or aW; return self._w, self._hh
    def draw(self):
        c=self.canv; w=self._w; h=self._hh
        c.setFillColor(white); c.setStrokeColor(C_LGRAY); c.setLineWidth(0.5)
        c.roundRect(0,0,w,h,3,fill=1,stroke=1)
        c.setFillColor(C_GOLD); c.rect(0,0,3,h,fill=1,stroke=0)
        c.setFont('Helvetica-Bold',6.5); c.setFillColor(C_GOLD); c.drawString(10,h-12,self.label)
        # Display user text or placeholder
        display = self.text if self.text.strip() else self.ph
        col = C_TEXT if self.text.strip() else C_DKGRY
        font = 'Helvetica' if self.text.strip() else 'Helvetica-Oblique'
        c.setFont(font, 8); c.setFillColor(col)
        # Simple word-wrap
        chars_per_line = int((w - 24) / 4.4)
        words = display.split(); line = ''; lines = []; y = h-24
        for word in words:
            test = (line+' '+word).strip()
            if len(test) > chars_per_line and line:
                lines.append(line); line = word
            else:
                line = test
        if line: lines.append(line)
        for l in lines:
            if y < 8: break
            c.drawString(10, y, l); y -= 11
        if not self.text.strip():
            c.setStrokeColor(HexColor('#EBEBEB')); c.setLineWidth(0.4)
            ly = h-36
            while ly > 6: c.line(10,ly,w-10,ly); ly -= 13

class PreTreatCard(Flowable):
    def __init__(self, score, max_score, score_label, title, desc_lines,
                 pre_class, badge_col, range_rows, width=None):
        super().__init__()
        self.score=score; self.max_score=max_score; self.score_label=score_label
        self.title=title; self.desc_lines=desc_lines; self.pre_class=pre_class
        self.badge_col=badge_col; self.range_rows=range_rows; self._fw=width
    def wrap(self,aW,aH):
        self._w=self._fw or aW
        n_range=len(self.range_rows)+1
        self._h=max(max(16+len(self.desc_lines)*11+24, n_range*16+12), 82)
        return self._w, self._h
    def draw(self):
        c=self.canv; w=self._w; h=self._h
        BADGE_W=24*mm; RANGE_W=60*mm; DESC_W=w-BADGE_W-RANGE_W-8
        c.setFillColor(C_LIGHT); c.setStrokeColor(C_LGRAY); c.setLineWidth(0.5)
        c.roundRect(0,0,w,h,4,fill=1,stroke=1)
        cx=BADGE_W/2; cy=h-26
        c.setFillColor(self.badge_col); c.circle(cx,cy,17,fill=1,stroke=0)
        c.setFont('Helvetica-Bold',17); c.setFillColor(white); c.drawCentredString(cx,cy-5,str(self.score))
        c.setFont('Helvetica',6.5); c.setFillColor(HexColor('#CCCCCC')); c.drawCentredString(cx,cy-16,f'/{self.max_score}')
        c.setFont('Helvetica',6); c.setFillColor(C_DKGRY); c.drawCentredString(cx,7,self.score_label)
        x0=BADGE_W+5; y=h-12
        c.setFont('Helvetica-Bold',10); c.setFillColor(C_DARK); c.drawString(x0,y,self.title); y-=14
        c.setFont('Helvetica',7.5); c.setFillColor(C_TEXT)
        for line in self.desc_lines: c.drawString(x0,y,line); y-=11
        y-=3
        c.setFont('Helvetica-Bold',7.5); c.setFillColor(C_DARK)
        c.drawString(x0,y,f'Pre-SRP: {self.pre_class}')
        xr=BADGE_W+DESC_W+10; yr=h-2; rh=14; col1=22
        c.setFillColor(C_DARK); c.rect(xr,yr-rh,RANGE_W-4,rh,fill=1,stroke=0)
        c.setFont('Helvetica-Bold',6.5); c.setFillColor(white)
        c.drawString(xr+3,yr-rh+4,'RANGE'); c.drawString(xr+col1+5,yr-rh+4,'CLASSIFICATION')
        yr-=rh
        for rng,cls,bold in self.range_rows:
            bg=HexColor('#D8E8F5') if bold else white
            c.setFillColor(bg); c.rect(xr,yr-rh,RANGE_W-4,rh,fill=1,stroke=0)
            c.setStrokeColor(C_LGRAY); c.setLineWidth(0.3); c.rect(xr,yr-rh,RANGE_W-4,rh,fill=0,stroke=1)
            fn='Helvetica-Bold' if bold else 'Helvetica'
            c.setFont(fn,7); c.setFillColor(C_TEXT)
            c.drawString(xr+3,yr-rh+4,rng); c.drawString(xr+col1+5,yr-rh+4,cls)
            yr-=rh

class GlanceGrid(Flowable):
    def __init__(self, cards, width=None):
        super().__init__(); self.cards=cards; self._fw=width
    def wrap(self,aW,aH): self._w=self._fw or aW; return self._w, 160
    def draw(self):
        c=self.canv; w=self._w; cols=3; rows=2; cw=w/cols; ch=76
        for i,(val,lbl,dlt,note,status) in enumerate(self.cards):
            col=i%cols; row=i//cols; x=col*cw; y=(rows-1-row)*ch
            sc=KPI_GOOD if status=='good' else (KPI_BAD if status=='bad' else KPI_NEUTRAL)
            c.setFillColor(sc['bg']); c.setStrokeColor(sc['border']); c.setLineWidth(0.8)
            c.roundRect(x+3,y+3,cw-6,ch-6,4,fill=1,stroke=1)
            c.setFont('Helvetica-Bold',19); c.setFillColor(sc['val']); c.drawCentredString(x+cw/2,y+ch-26,val)
            c.setFont('Helvetica-Bold',6.5); c.setFillColor(sc['lbl']); c.drawCentredString(x+cw/2,y+ch-38,lbl)
            c.setStrokeColor(sc['border']); c.setLineWidth(0.8)
            lw=28; c.line(x+cw/2-lw/2,y+ch-42,x+cw/2+lw/2,y+ch-42)
            c.setFont('Helvetica-Bold',9); c.setFillColor(sc['dlt']); c.drawCentredString(x+cw/2,y+ch-54,dlt)
            c.setFont('Helvetica',6.5); c.setFillColor(HexColor('#666')); c.drawCentredString(x+cw/2,y+ch-65,note)

class ISIJourney(Flowable):
    def __init__(self, bv, bl, av, al, footnote='', width=None):
        super().__init__(); self.bv=bv; self.bl=bl; self.av=av; self.al=al; self.fn=footnote; self._fw=width
    def wrap(self,aW,aH): self._w=self._fw or aW; return self._w, 82
    def draw(self):
        c=self.canv; w=self._w; bw=w*0.40; aw=w*0.40; ax0=w*0.60
        c.setFillColor(C_DARK3); c.roundRect(0,8,bw,70,4,fill=1,stroke=0)
        c.setFont('Helvetica-Bold',7.5); c.setFillColor(C_MGRAY); c.drawCentredString(bw/2,67,'BEFORE')
        c.setFont('Helvetica-Bold',36); c.setFillColor(white); c.drawCentredString(bw/2,34,str(self.bv))
        c.setFont('Helvetica',8); c.setFillColor(HexColor('#8899AA')); c.drawCentredString(bw/2,17,self.bl)
        c.setFont('Helvetica',20); c.setFillColor(C_MGRAY); c.drawCentredString(w/2,40,'→')
        c.setFillColor(C_DARK); c.roundRect(ax0,8,aw,70,4,fill=1,stroke=0)
        c.setFont('Helvetica-Bold',7.5); c.setFillColor(C_MGRAY); c.drawCentredString(ax0+aw/2,67,'AFTER (6 weeks)')
        c.setFont('Helvetica-Bold',36); c.setFillColor(C_GOLD); c.drawCentredString(ax0+aw/2,34,str(self.av))
        c.setFont('Helvetica',8); c.setFillColor(HexColor('#8899AA')); c.drawCentredString(ax0+aw/2,17,self.al)
        if self.fn:
            c.setFont('Helvetica',6.5); c.setFillColor(C_DKGRY); c.drawCentredString(w/2,2,self.fn)

class WhatImproved(Flowable):
    def __init__(self, improved, watch, width=None):
        super().__init__(); self.imp=improved; self.wat=watch; self._fw=width
    def wrap(self,aW,aH):
        self._w=self._fw or aW; rows=max(len(self.imp),len(self.wat)); self._h=28+rows*11+8; return self._w, self._h
    def draw(self):
        c=self.canv; w=self._w; h=self._h; hw=(w-4)/2
        c.setFillColor(HexColor('#E6F4E6')); c.roundRect(0,0,hw,h,3,fill=1,stroke=0)
        c.setFillColor(HexColor('#FAE9E6')); c.roundRect(hw+4,0,hw,h,3,fill=1,stroke=0)
        c.setFont('Helvetica-Bold',8); c.setFillColor(HexColor('#1E5E1E')); c.drawString(8,h-18,'WHAT IMPROVED')
        c.setFont('Helvetica-Bold',8); c.setFillColor(HexColor('#8C2A18')); c.drawString(hw+12,h-18,'AREAS TO WATCH')
        y=h-30; c.setFont('Helvetica',7.5)
        for t in self.imp: c.setFillColor(C_TEXT); c.drawString(8,y,f'• {t}'); y-=11
        y=h-30
        for t in self.wat: c.setFillColor(C_TEXT); c.drawString(hw+12,y,f'• {t}'); y-=11

class ScoreTriple(Flowable):
    def __init__(self, cards, width=None):
        super().__init__(); self.cards=cards; self._fw=width
    def wrap(self,aW,aH): self._w=self._fw or aW; return self._w, 74
    def draw(self):
        c=self.canv; w=self._w; n=len(self.cards); cw=w/n
        for i,(lbl,pre,post,dlt,note) in enumerate(self.cards):
            x=i*cw
            c.setFillColor(C_LIGHT); c.setStrokeColor(C_LGRAY); c.setLineWidth(0.5)
            c.roundRect(x+2,2,cw-4,70,3,fill=1,stroke=1)
            c.setFont('Helvetica',7); c.setFillColor(C_GOLD); c.drawCentredString(x+cw/2,62,lbl)
            c.setFont('Helvetica-Bold',24); c.setFillColor(C_DARK); c.drawCentredString(x+cw/2,40,str(post))
            c.setFont('Helvetica',7); c.setFillColor(C_DKGRY); c.drawCentredString(x+cw/2,29,f'Pre-SRP: {pre}')
            c.setFont('Helvetica-Bold',9.5); c.setFillColor(C_GREEN); c.drawCentredString(x+cw/2,17,dlt)
            if note: c.setFont('Helvetica',6); c.setFillColor(C_DKGRY); c.drawCentredString(x+cw/2,6,note)

# ── Document template ─────────────────────────────────────────────────────────
class NoxoraDoc(BaseDocTemplate):
    def __init__(self, path_or_buf, pd, **kw):
        self._pg=[1]; self.pd=pd
        super().__init__(path_or_buf, **kw)
        cover_f = Frame(ML, LETTER_FRAME_Y, CW, LETTER_FRAME_H,
                        leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0, id='cover')
        body_f  = Frame(ML, MB+FTR_H, CW, PH-MT-HDR_H-MB-FTR_H,
                        leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0, id='body')
        self.addPageTemplates([
            PageTemplate(id='Cover', frames=[cover_f], onPage=self._cover),
            PageTemplate(id='Body',  frames=[body_f],  onPage=self._body),
        ])

    def _cover(self, c, doc):
        pd = self.pd
        c.saveState()
        c.setFillColor(C_DARK); c.rect(0,0,PW,PH,fill=1,stroke=0)
        c.setFillColor(HexColor('#222A3A')); c.circle(PW+40,PH+40,PH*0.48,fill=1,stroke=0)
        # Logo card
        c.setFillColor(HexColor('#252B3A'))
        c.roundRect(ML, LOGO_CARD_Y0, CW, LOGO_CARD_H, 7, fill=1, stroke=0)
        c.setFont('Helvetica-Bold',32); c.setFillColor(white)
        c.drawString(ML+14, LOGO_CARD_Y0+LOGO_CARD_H-44,'NOXORA')
        c.setFont('Helvetica',9); c.setFillColor(C_GOLD)
        c.drawString(ML+14, LOGO_CARD_Y0+LOGO_CARD_H-62,'SLEEP, RESTORED.')
        # Title
        ty = LOGO_CARD_Y0 - 14
        c.setFont('Helvetica-Bold',22); c.setFillColor(white); c.drawString(ML,ty,'Sleep Recovery Report')
        c.setFont('Helvetica-Bold',12); c.setFillColor(C_GOLD); c.drawString(ML,ty-20,'Personal Report')
        c.setFont('Helvetica',9); c.setFillColor(HexColor('#8899BB'))
        c.drawString(ML,ty-35,'Post-programme outcome & 6-week follow-up assessment')
        # Patient card
        px=ML; py=PAT_CARD_Y0; pw=CW; ph=PAT_CARD_H
        c.setFillColor(HexColor('#1A2133')); c.roundRect(px,py,pw,ph,5,fill=1,stroke=0)
        c.setStrokeColor(HexColor('#3A4560')); c.setLineWidth(0.8); c.roundRect(px,py,pw,ph,5,fill=0,stroke=1)
        lw=pw*0.35; lx=px+12
        c.setFont('Helvetica',6); c.setFillColor(C_MGRAY); c.drawString(lx,py+ph-16,'PATIENT')
        c.setFont('Helvetica-Bold',20); c.setFillColor(white); c.drawString(lx,py+ph-36,pd['first_name'])
        c.setFont('Helvetica-Bold',10); c.setFillColor(C_GOLD); c.drawString(lx,py+ph-52,pd['gender'])
        c.setFont('Helvetica-Bold',10); c.setFillColor(white); c.drawString(lx,py+ph-67,pd['patient_id'])
        c.setStrokeColor(HexColor('#2E3A50')); c.setLineWidth(0.6)
        c.line(px+lw,py+8,px+lw,py+ph-10)
        rx=px+lw+14
        fields=[('PROGRAMME DATES',    pd['program_date']),
                ('LOCATION',           pd['location']),
                ('NO. OF STIMULATIONS',pd['num_stimulations']),
                ('LEAD PROFESSIONAL',  pd['lead_professional']),
                ('REPORT TYPE',        pd['report_type'].upper()),]
        fy=py+ph-15
        for lbl,fval in fields:
            c.setFont('Helvetica',5.5); c.setFillColor(C_MGRAY); c.drawString(rx,fy,lbl)
            c.setFont('Helvetica-Bold',8.5); c.setFillColor(white); c.drawString(rx,fy-12,str(fval))
            fy-=27
        c.setFillColor(HexColor('#D8D8D0')); c.rect(0,LETTER_FRAME_Y+LETTER_FRAME_H,PW,0.8,fill=1,stroke=0)
        c.restoreState()

    def _body(self, c, doc):
        pd = self.pd
        c.saveState()
        self._pg[0]+=1; pg=self._pg[0]
        c.setFillColor(C_DARK); c.rect(0,PH-HDR_H,PW,HDR_H,fill=1,stroke=0)
        c.setFont('Helvetica-Bold',7.5); c.setFillColor(white); c.drawString(ML,PH-HDR_H+3.5*mm,'NOXORA')
        c.setFont('Helvetica',7.5); c.setFillColor(C_GOLD); c.drawString(ML+40,PH-HDR_H+3.5*mm,'|')
        c.setFillColor(HexColor('#9AAABB'))
        c.drawString(ML+50,PH-HDR_H+3.5*mm,'Sleep Recovery Report  |  Personal Report')
        c.drawRightString(PW-MR,PH-HDR_H+3.5*mm,f"{pd['first_name']} {pd['last_name']}  |  Confidential")
        c.setStrokeColor(C_LGRAY); c.setLineWidth(0.5); c.line(ML,MB+FTR_H-1,PW-MR,MB+FTR_H-1)
        c.setFont('Helvetica',6.5); c.setFillColor(C_DKGRY)
        c.drawString(ML,MB+2,'Intended for the named patient and their healthcare provider only.')
        c.drawRightString(PW-MR,MB+2,f'Page {pg}')
        c.restoreState()

# ── Table / box helpers ───────────────────────────────────────────────────────
def htable(data, cw, hdr=1):
    ts=TableStyle([
        ('FONTNAME',(0,0),(-1,hdr-1),'Helvetica-Bold'),('FONTSIZE',(0,0),(-1,-1),7.5),
        ('TEXTCOLOR',(0,0),(-1,hdr-1),white),('TEXTCOLOR',(0,hdr),(-1,-1),C_TEXT),
        ('BACKGROUND',(0,0),(-1,hdr-1),C_DARK),('GRID',(0,0),(-1,-1),0.35,C_LGRAY),
        ('VALIGN',(0,0),(-1,-1),'MIDDLE'),('TOPPADDING',(0,0),(-1,-1),4),
        ('BOTTOMPADDING',(0,0),(-1,-1),4),('LEFTPADDING',(0,0),(-1,-1),6),
        ('RIGHTPADDING',(0,0),(-1,-1),4),
    ])
    for i in range(hdr,len(data)):
        ts.add('BACKGROUND',(0,i),(-1,i),C_LIGHT if i%2==0 else white)
    return Table(data,colWidths=cw,style=ts,hAlign='LEFT',repeatRows=hdr)

def dark_box(label, lines):
    lp=Paragraph(label,ParagraphStyle('dbl',fontName='Helvetica-Bold',fontSize=7.5,textColor=C_GOLD,leading=10))
    cp=Paragraph('<br/>'.join(lines),ParagraphStyle('dbc',fontName='Helvetica-Oblique',fontSize=7.5,textColor=white,leading=11.5))
    t=Table([[lp,cp]],colWidths=[34*mm,CW-34*mm])
    t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,-1),C_DARK2),('VALIGN',(0,0),(-1,-1),'TOP'),
                            ('TOPPADDING',(0,0),(-1,-1),8),('BOTTOMPADDING',(0,0),(-1,-1),8),
                            ('LEFTPADDING',(0,0),(-1,-1),8),('RIGHTPADDING',(0,0),(-1,-1),8),
                            ('GRID',(0,0),(-1,-1),0,C_DARK2)]))
    return t

def gold_box(label, lines):
    lp=Paragraph(label,ParagraphStyle('gbl',fontName='Helvetica-Bold',fontSize=7.5,textColor=C_GOLD,leading=10))
    cp=Paragraph('<br/>'.join(lines),ParagraphStyle('gbc',fontName='Helvetica-Oblique',fontSize=8,textColor=HexColor('#333'),leading=12))
    t=Table([[lp,cp]],colWidths=[36*mm,CW-36*mm])
    t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,-1),HexColor('#FDFAF3')),
                            ('BOX',(0,0),(-1,-1),0.7,C_GOLD),('VALIGN',(0,0),(-1,-1),'TOP'),
                            ('TOPPADDING',(0,0),(-1,-1),8),('BOTTOMPADDING',(0,0),(-1,-1),8),
                            ('LEFTPADDING',(0,0),(-1,-1),8),('RIGHTPADDING',(0,0),(-1,-1),8)]))
    return t

def light_box(text):
    t=Table([[Paragraph(text,ParagraphStyle('lb',fontName='Helvetica',fontSize=8,textColor=C_TEXT,leading=12))]],colWidths=[CW])
    t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,-1),HexColor('#EDECEA')),
                            ('BOX',(0,0),(-1,-1),0.5,C_LGRAY),
                            ('TOPPADDING',(0,0),(-1,-1),8),('BOTTOMPADDING',(0,0),(-1,-1),8),
                            ('LEFTPADDING',(0,0),(-1,-1),10),('RIGHTPADDING',(0,0),(-1,-1),10)]))
    return t

def rec_item(num, title, body_text, priority, pc=None):
    pc=pc or C_RED
    ps=ParagraphStyle(f'rp{num}',fontName='Helvetica-Bold',fontSize=7,textColor=pc,leading=9,alignment=TA_RIGHT)
    data=[[Paragraph(str(num),ParagraphStyle(f'rn{num}',fontName='Helvetica-Bold',fontSize=11,
                     textColor=white,leading=13,alignment=TA_CENTER)),
           Paragraph(f'<b>{title}</b>',ST['rt']),Paragraph(priority,ps)],
          ['',Paragraph(body_text,ST['rb']),'']]
    ts=TableStyle([('BACKGROUND',(0,0),(0,-1),C_DARK),('BACKGROUND',(1,0),(-1,-1),white),
                   ('TEXTCOLOR',(1,0),(-1,-1),C_TEXT),('BOX',(0,0),(-1,-1),0.4,C_LGRAY),
                   ('VALIGN',(0,0),(-1,-1),'TOP'),('TOPPADDING',(0,0),(-1,-1),5),
                   ('BOTTOMPADDING',(0,0),(-1,-1),5),('LEFTPADDING',(0,0),(-1,-1),6),
                   ('RIGHTPADDING',(0,0),(-1,-1),4),('SPAN',(0,0),(0,1))])
    return Table(data,colWidths=[11*mm,CW-36*mm,25*mm],style=ts,hAlign='LEFT')

def section(label, title): return [SectionHdr(label,title), sp(2)]
def mini_sec(label, title): return [MiniHdr(label,title), sp(1.5)]

# ── ISI classification helper ──────────────────────────────────────────────────
def isi_class(score):
    if score is None: return "Unknown"
    if score <= 7:  return "No Significant Insomnia"
    if score <= 14: return "Subthreshold / Mild Insomnia"
    if score <= 21: return "Moderate Insomnia"
    return "Severe Insomnia"

def delta_str(pre, post, unit='pts'):
    if pre is None or post is None: return "—"
    d = int(post) - int(pre)
    return f"{'–' if d < 0 else '+'}{abs(d)} {unit}"

def kpi_status(pre, post, lower_is_better=True):
    if pre is None or post is None: return 'neutral'
    try:
        d = float(post) - float(pre)
        if d == 0: return 'neutral'
        return ('good' if d < 0 else 'bad') if lower_is_better else ('good' if d > 0 else 'bad')
    except Exception: return 'neutral'

# ── Page builders ─────────────────────────────────────────────────────────────

def cover_story(pd, notes):
    items = []
    items.append(sp(5))
    items.append(Paragraph(f"Dear {pd['first_name']},", LTR_GOLD))
    items.append(sp(2))
    items.append(Paragraph(
        'We are happy to provide you with this Sleep Recovery Report, which summarises '
        'the progress you have made with us on your journey to improved sleep quality. '
        'We have based this report on the information you provided through our questionnaires '
        'and during your interactions with the Noxora team.',
        LTR_BODY))
    items.append(sp(4))
    items.append(Paragraph('This report includes:', LTR_BODY))
    items.append(sp(1))
    for comp in ['Pre-treatment sleep profile',
                 'Post-treatment sleep development & key parameters',
                 'Your results at a glance — 6-week follow-up',
                 'Personalised clinical recommendations',
                 'Noxora overall program performance',
                 'Personal questionnaires — detailed data']:
        items.append(Paragraph(f'—  {comp}', LTR_COMP))
    items.append(sp(8))
    items.append(Paragraph('(Signature)', LTR_SIG))
    items.append(Paragraph(f"[{pd['lead_professional']}]", LTR_NAME))
    return items

def page2(pd, notes):
    items = []
    items += section('SECTION 01','Patient Profile')
    items.append(htable([
        [p('PATIENT NAME','th'),p('GENDER','th'),p('AGE','th'),p('PATIENT ID','th')],
        [p(f"{pd['first_name']} {pd['last_name']}",'tdb'),p(pd['gender'],'td'),p(str(pd['age']),'td'),p(pd['patient_id'],'tdb')],
        [p('PROGRAMME LOCATION','th2'),p('PROGRAMME DATE','th2'),p('REPORT DATE','th2'),p('','th2')],
        [p(pd['location'],'td'),p(str(pd['program_date']),'td'),p(pd['report_date'],'td'),p('','td')],
    ],[CW*0.30,CW*0.16,CW*0.18,CW*0.36]))
    items.append(sp(5))

    items += section('SECTION 02','Sleep Recovery Programme Details')
    items.append(htable([
        [p('PROGRAMME DATES','th'),p('LOCATION','th'),p('NO. OF SESSIONS','th'),p('TREATMENT MODALITY','th')],
        [p(str(pd['program_date']),'td'),p(pd['location'],'td'),p(str(pd['num_stimulations']),'tdb'),
         p('Neurostimulation + therapeutical modules + evaluation','tdb')],
        [p('LEAD PROFESSIONAL','th2'),p('REPORT VERSION','th2'),p('REPORT TYPE','th2'),p('','th2')],
        [p(pd['lead_professional'],'td'),p('v1.0','td'),p(pd['report_type'].upper(),'tdb'),p('','td')],
    ],[CW*0.28,CW*0.20,CW*0.20,CW*0.32]))
    items.append(sp(5))

    items += section('SECTION 03','Medical Pre-Screening')
    items.append(htable([
        [p('SCREENING DATE','th'),p('PRE-TREATMENT INTERVIEW','th'),p('EXCLUSION CRITERIA','th'),p('CONSENTING PROFESSIONAL','th')],
        [p(str(pd['program_date']),'td'),p('Completed','tdb'),p('All Cleared','tdb'),p('Noxora Medical','td')],
    ],[CW*0.22,CW*0.26,CW*0.22,CW*0.30]))
    items.append(sp(3))
    items.append(light_box(
        'Exclusion criteria confirmed absent: <b>epilepsy, cardiac or cranial implants, '
        'pregnancy, history of brain stroke, prior head or neurosurgical intervention.</b>'))
    items.append(sp(3))
    med_note_text = notes.get('medication','') or 'No particular medical condition noted.'
    if pd.get('medical_other'):
        med_note_text += f" Medical note: {pd['medical_other']}."
    items.append(ClinNote(label='CLINICAL NOTES FROM MEDICAL PROFILE',
                          text=med_note_text,
                          placeholder='[Clinician: relevant medical history, comorbidities, medications affecting sleep.]',
                          height=28*mm))
    return items

def page3(pd, notes):
    items = []
    items += section('SECTION 04','Pre-Treatment Sleep Profile')
    items.append(Paragraph(
        'The following validated clinical instruments were completed prior to the Sleep Recovery Programme '
        'to establish a clinical baseline. Outcomes are measured against these scores at follow-up.',
        ST['body']))
    items.append(sp(4))
    items.append(dark_box('MEDICATION NOTE',[
        f"Prescribed medication: {int(pd['pre_hab_prescribed'])}/3 at intake. "
        f"Unprescribed medication: {int(pd['pre_hab_unprescribed'])}/3 at intake.",
        'For patients taking sleep medication, ISI scores must be interpreted with caution.',
        'A stable or reduced ISI may partially reflect medication masking rather than neurological recovery.',
        f"Medication-adjusted ISI is the primary outcome metric for {pd['first_name']}.",
    ]))
    items.append(sp(4))

    pre_isi = pd['pre_isi_total']
    pre_isi_class = isi_class(pre_isi)
    items.append(PreTreatCard(
        score=pre_isi, max_score=28, score_label='ISI Score',
        title='Insomnia Severity Index (ISI)',
        desc_lines=['Validated 7-item questionnaire (range 0–28) assessing insomnia',
                    'severity and daytime impact. Primary outcome for the Noxora SRP.'],
        pre_class=f'{pre_isi_class} (Score: {pre_isi})',
        badge_col=C_BLUE,
        range_rows=[('0 – 7','No significant insomnia', pre_isi <= 7),
                    ('8 – 14','Subthreshold / mild',     8 <= pre_isi <= 14),
                    ('15 – 21','Moderate insomnia',       15 <= pre_isi <= 21),
                    ('22 – 28','Severe insomnia',          pre_isi >= 22)]))
    items.append(sp(3))
    items.append(ClinNote(label='ISI — CLINICAL COMMENTS',
                          text=notes.get('isi_comments',''),
                          placeholder='[Describe insomnia symptom profile, onset, duration and contributing factors.]',
                          height=22*mm))
    items.append(sp(4))

    pre_psqi = pd['pre_psqi_total']
    items.append(PreTreatCard(
        score=pre_psqi, max_score=21, score_label='PSQI Score',
        title='Pittsburgh Sleep Quality Index (PSQI)',
        desc_lines=[f"Bedtime: {pd['pre_psqi_bedtime']} | Latency: {pd['pre_psqi_latency']} min | Wake: {pd['pre_psqi_wake']}",
                    f"Net sleep: {pd['pre_psqi_hours']}h | Efficiency: {pd['pre_psqi_efficiency']}"],
        pre_class=f"{'Normal' if pre_psqi <= 5 else 'Poor' if pre_psqi <= 10 else 'Very Poor'} Sleep Quality (Score: {pre_psqi})",
        badge_col=C_TEAL,
        range_rows=[('0 – 5','Normal sleep quality',  pre_psqi <= 5),
                    ('6 – 10','Poor sleep quality',   6 <= pre_psqi <= 10),
                    ('11 – 21','Very poor quality',    pre_psqi >= 11)]))
    items.append(sp(3))
    items.append(ClinNote(label='PSQI — CLINICAL COMMENTS',
                          text=notes.get('psqi_comments',''),
                          placeholder='[Note components of concern: efficiency, latency, awakenings, medication use.]',
                          height=22*mm))
    items.append(sp(4))

    # Habits + Other obs
    def mini_box(paras_data):
        rows=[[Paragraph(t,ParagraphStyle('mb',fontName=f,fontSize=7.5,textColor=c,leading=11))]
              for t,f,c in paras_data]
        t=Table(rows,colWidths=[CW/2-4])
        t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,-1),C_LIGHT),('BOX',(0,0),(-1,-1),0.5,C_LGRAY),
                                ('TOPPADDING',(0,0),(-1,-1),3),('BOTTOMPADDING',(0,0),(-1,-1),3),
                                ('LEFTPADDING',(0,0),(-1,-1),8),('RIGHTPADDING',(0,0),(-1,-1),6),
                                ('VALIGN',(0,0),(-1,-1),'TOP')]))
        return t
    hab_box=mini_box([
        ('NOXORA SLEEP HABITS PROFILE','Helvetica-Bold',C_DARK),
        (f"Score: {pd['pre_hab_score']} / 24 — {'Very Good' if pd['pre_hab_score']<=3 else 'Moderate'} Habits Baseline",
         'Helvetica',C_TEXT),
        (f"Unprescribed medication: {int(pd['pre_hab_unprescribed'])}/3 at intake.",'Helvetica-Oblique',HexColor('#555')),
    ])
    obs_box=mini_box([
        ('OTHER CLINICAL OBSERVATIONS','Helvetica-Bold',C_DARK),
        (f"{pd['gender']}, age {pd['age']}.",'Helvetica',C_TEXT),
        (f"Medical context: {pd['medical_other'] or 'None noted.'}",'Helvetica',C_TEXT),
        (f"Bedtime: {pd['pre_psqi_bedtime']} | Sleep: {pd['pre_psqi_hours']}h | Eff: {pd['pre_psqi_efficiency']}",
         'Helvetica',C_TEXT),
    ])
    two_col=Table([[hab_box,obs_box]],colWidths=[CW/2,CW/2])
    two_col.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'TOP'),
                                   ('LEFTPADDING',(0,0),(-1,-1),0),('RIGHTPADDING',(0,0),(-1,-1),0),
                                   ('TOPPADDING',(0,0),(-1,-1),0),('BOTTOMPADDING',(0,0),(-1,-1),0),
                                   ('GRID',(0,0),(-1,-1),0,white)]))
    items.append(two_col)
    items.append(sp(4))
    items.append(ClinNote(label='GENERAL CLINICAL OBSERVATIONS',
                          text=notes.get('general',''),
                          placeholder='[Any additional clinical observations not captured above.]',
                          height=26*mm))
    return items

def page4(pd, notes):
    pre_isi  = pd['pre_isi_med_adj']
    post_isi = pd['post_isi_med_adj']
    pre_psqi = pd['pre_psqi_total']
    post_psqi= pd['post_psqi_total']
    pre_unp  = pd['pre_hab_unprescribed']
    post_unp = pd['post_hab_unprescribed']
    pre_q5h  = pd['pre_psqi_q5h']
    post_q5h = pd['post_psqi_q5h']

    items = []
    items += section('YOUR RESULTS AT A GLANCE','6-Week Follow-Up Summary')
    items.append(Paragraph(
        'This page gives you a clear, accessible overview of your progress since completing the Noxora '
        'Sleep Recovery Programme. Detailed clinical data follows in the pages after. '
        '<b>Green = improvement. Red = no improvement. Gray = unchanged.</b>',
        ST['body']))
    items.append(sp(5))

    isi_d   = delta_str(pre_isi, post_isi)
    psqi_d  = delta_str(pre_psqi, post_psqi)
    unp_d   = f"{int(pre_unp)}/3 → {int(post_unp)}/3"
    items.append(GlanceGrid([
        (f"{pre_isi} → {post_isi}", 'INSOMNIA SEVERITY INDEX',   isi_d,          'medication-adjusted',          kpi_status(pre_isi,post_isi)),
        (f"{pre_psqi} → {post_psqi}",'SLEEP QUALITY (PSQI)',      psqi_d,         'with lower medication use',     kpi_status(pre_psqi,post_psqi)),
        (f"{pd['pre_psqi_hours']}h", 'SLEEP DURATION',            'Unchanged',    'stable sleep quantity',         'neutral'),
        (f"{pd['pre_psqi_latency']}m",'SLEEP LATENCY',            'Unchanged',    f"{pd['pre_psqi_latency']} min at both timepoints",'neutral'),
        (str(pd['pre_psqi_efficiency']),'SLEEP EFFICIENCY',        'Unchanged',    'target: > 85%',                'neutral'),
        (unp_d,                      'UNPRESCRIBED MEDICATION',    '↓ Reduction',  'natural recovery signal',       kpi_status(pre_unp,post_unp)),
    ], width=CW))
    items.append(sp(6))

    items.append(Paragraph('YOUR ISI SCORE JOURNEY', ST['sec_lbl']))
    items.append(ISIJourney(pre_isi, isi_class(pre_isi), post_isi, isi_class(post_isi),
                            f'A reduction of {pre_isi-post_isi} pts (medication-adjusted). Clinical significance threshold: 5 pts.',
                            width=CW))
    items.append(sp(5))

    # What improved / areas to watch (derived from data)
    improved = []
    watch    = []
    if post_isi < pre_isi:   improved.append(f"ISI improved: {pre_isi} → {post_isi} (med-adj)")
    else:                    watch.append(f"ISI not improved ({pre_isi} → {post_isi})")
    if post_psqi < pre_psqi: improved.append(f"Sleep quality (PSQI): {pre_psqi} → {post_psqi}")
    else:                    watch.append(f"PSQI unchanged/worsened ({pre_psqi} → {post_psqi})")
    if post_unp < pre_unp:   improved.append(f"Unprescribed medication: {int(pre_unp)}/3 → {int(post_unp)}/3")
    if post_q5h < pre_q5h:   improved.append(f"Bad dreams: {int(pre_q5h)}/3 → {int(post_q5h)}/3")
    # Generic watches
    watch += ['Sleep efficiency to be monitored',
              'Medication levels — discuss with physician']
    if len(improved) == 0: improved = ['—']
    items.append(WhatImproved(improved[:5], watch[:5], width=CW))
    items.append(sp(4))
    items.append(ClinNote(label='CLINICIAN SUMMARY COMMENT',
                          text=notes.get('recommendations',''),
                          placeholder='[Clinician: enter overall assessment of the 6-week follow-up result.]',
                          height=24*mm))
    return items

def page5(pd, notes):
    pre_isi   = pd['pre_isi_med_adj'];  post_isi   = pd['post_isi_med_adj']
    pre_psqi  = pd['pre_psqi_total'];   post_psqi  = pd['post_psqi_total']
    pre_hab   = pd['pre_hab_score'];    post_hab   = pd['post_hab_score']
    pre_unp   = pd['pre_hab_unprescribed']; post_unp = pd['post_hab_unprescribed']

    items = []
    items += section('SECTION 05','Post-Treatment Sleep Development')
    items.append(Paragraph(
        '6-week follow-up scores compared to pre-treatment baseline. An improvement of 4+ points on the ISI '
        'is clinically significant (Morin et al., 2011). Medication-adjusted ISI removes the masking effect '
        'of continued medication use.', ST['body']))
    items.append(sp(5))

    items.append(ScoreTriple([
        ('ISI SCORE (MED-ADJ)', str(pre_isi), str(post_isi), delta_str(pre_isi,post_isi), isi_class(post_isi)),
        ('PSQI SCORE',          str(pre_psqi), str(post_psqi), delta_str(pre_psqi,post_psqi),'with lower medication use'),
        ('SLEEP HABITS',        str(pre_hab),  str(post_hab),
         'Unchanged' if pre_hab == post_hab else delta_str(pre_hab,post_hab), 'habits baseline'),
    ], width=CW))
    items.append(sp(5))

    items.append(Paragraph('KEY PARAMETER EVOLUTION', ST['sec_lbl']))
    items.append(chart_key_params(pre_isi, post_isi, pre_psqi, post_psqi, pre_hab, post_hab))
    items.append(sp(5))

    def pr(pre, post): return f"↓ {int(pre)-int(post)} pts" if pre > post else ("↑ worsened" if post > pre else "0")
    items.append(htable([
        [p('MEASURE','th'),p('PRE-SRP','th'),p('6-WEEK','th'),p('CHANGE','th'),p('NOTE','th')],
        [p('ISI Total Score (0–28)','tdb'),   p(str(pd['pre_isi_total']),'td'),  p(str(pd['post_isi_total']),'td'),  p(delta_str(pd['pre_isi_total'],pd['post_isi_total']),'tdb'),   p('Raw score improvement','tdg')],
        [p('ISI Medication-Adjusted','tdb'),  p(str(pre_isi),'td'),              p(str(post_isi),'td'),              p(delta_str(pre_isi,post_isi),'tdb'),                          p('Primary outcome metric','tdg')],
        [p('PSQI Total Score (0–21)','tdb'),  p(str(pre_psqi),'td'),             p(str(post_psqi),'td'),             p(delta_str(pre_psqi,post_psqi),'tdb'),                        p('Medication reduction noted','tdg')],
        [p('Sleep Habits (0–24)','tdb'),      p(str(pre_hab),'td'),              p(str(post_hab),'td'),              p('0' if pre_hab==post_hab else delta_str(pre_hab,post_hab),'td'),p('Habits baseline','tdg')],
        [p('Unprescribed Medication','tdb'),  p(f"{int(pre_unp)}/3",'td'),       p(f"{int(post_unp)}/3",'tdb'),      p(delta_str(pre_unp,post_unp,unit=''),'tdb'),                  p('Natural recovery signal','tdg')],
        [p('Bad Dreams (PSQI Q5h)','tdb'),    p(f"{int(pd['pre_psqi_q5h'])}/3",'td'),p(f"{int(pd['post_psqi_q5h'])}/3",'tdb'),p(delta_str(pd['pre_psqi_q5h'],pd['post_psqi_q5h'],unit=''),'tdb'),p('Quality improvement','tdg')],
    ],[CW*0.30,CW*0.10,CW*0.10,CW*0.13,CW*0.37]))
    items.append(sp(5))
    items.append(gold_box('OBSERVABLE RESULTS AND COMMENTS',[
        f"ISI medication-adjusted: {pre_isi} → {post_isi} ({delta_str(pre_isi,post_isi)}). "
        f"Clinical significance threshold: 5 pts. "
        f"{'Above threshold — clinically significant improvement.' if (pre_isi-post_isi) >= 5 else 'Approaching the 5-point clinical significance threshold.'}",
        f"PSQI: {pre_psqi} → {post_psqi}. Unprescribed medication: {int(pre_unp)}/3 → {int(post_unp)}/3.",
    ]))
    items.append(sp(4))
    items.append(ClinNote(label='POST-TREATMENT CLINICAL NOTES',
                          text=notes.get('post_treatment',''),
                          placeholder='[Clinician: specific symptom dimensions, daytime functioning, remaining concerns.]',
                          height=24*mm))
    return items

def page6(pd, notes):
    items = []
    items += section('SECTION 06','Personalised Recommendations')
    items.append(Paragraph(
        'Based on your assessment results, treatment outcomes, and progress to date, your Noxora clinician '
        'recommends the following actions. These recommendations are derived directly from your sleep habits '
        'profile, ISI and PSQI responses, and your 6-week follow-up data.', ST['body']))
    items.append(sp(5))

    # Dynamic recommendations based on data
    recs = []
    pre_rx = int(pd['pre_hab_prescribed']); post_rx = int(pd['post_hab_prescribed'])
    pre_unp = int(pd['pre_hab_unprescribed']); post_unp = int(pd['post_hab_unprescribed'])
    post_isi = pd['post_isi_med_adj']

    if pre_rx > 0 or pre_unp > 0:
        recs.append((1,
            'Discuss sleep medication with your prescribing physician.',
            f'Your prescribed medication level was {pre_rx}/3 at intake and your unprescribed medication '
            f'was {pre_unp}/3. Continued use may partially mask your neurological sleep recovery. '
            'Work with your physician to assess whether a supervised, gradual reduction is appropriate. '
            'Do not adjust medication without medical supervision.',
            'PRIORITY: HIGH — MEDICAL', C_RED))
    if post_unp < pre_unp:
        recs.append((len(recs)+1,
            'Continue reducing unprescribed medication — build on the gains made.',
            f'Your unprescribed medication use dropped from {pre_unp}/3 to {post_unp}/3 — a positive signal. '
            'Continue on this trajectory with your pharmacist or GP. '
            f'Target: 0/3 by the 12-week assessment.',
            'PRIORITY: HIGH', C_RED))
    recs.append((len(recs)+1,
        f"Consider a booster neurostimulation session to consolidate gains.",
        f"Your medication-adjusted ISI of {post_isi} {'is now in the no-significant-insomnia range — outstanding.' if post_isi <= 7 else 'is approaching but not yet below the subthreshold range.' if post_isi <= 14 else 'remains elevated.'} "
        "A 1-day booster session would reinforce neurological sleep regulation. Contact us to discuss.",
        'SUGGESTED', C_DARK2))
    recs.append((len(recs)+1,
        f"Re-engage if ISI returns above {'10' if post_isi<=10 else '14'}.",
        f"Your current ISI of {post_isi} (medication-adjusted). "
        f"Use ISI ≥ {'10' if post_isi<=10 else '14'} as your personal re-engagement threshold. "
        "A booster session at that point will rapidly consolidate any regression. Self-assess monthly.",
        'BOOSTER TRIGGER', C_DARK2))
    recs.append((len(recs)+1,
        'Next recommended assessment: 12-week follow-up.',
        'A structured 12-week ISI, PSQI, and Habits assessment will confirm whether gains are durable. '
        'Your clinician will review medication levels, sleep efficiency trajectory, and any ongoing comorbidities.',
        'NEXT STEP', C_DARK2))

    # Add custom recommendation from notes
    if notes.get('recommendations','').strip():
        recs.append((len(recs)+1,
            'Clinician personalised recommendation.',
            notes['recommendations'],
            'PERSONALISED', C_TEAL))

    for num, title, body, pri, pc in recs:
        items.append(rec_item(num,title,body,pri,pc)); items.append(sp(2.5))

    items.append(sp(2))
    items.append(htable([
        [p('Next Assessment','th'),p('Clinician Contact','th'),p('Booster Session Criteria','th')],
        [p('[12-week follow-up date]','td'),p('hello@noxorasleep.com  |  [Phone]','td'),
         p(f"ISI score at or above {'10' if pd['post_isi_med_adj']<=10 else '14'} at any self-assessment",'td')],
    ],[CW/3]*3))
    return items

def page7():
    items = []
    items += section('SECTION 07','Noxora Overall Program Performance')
    items.append(Paragraph('Programme benchmark data as of 10 May 2026.',ST['body_l']))
    items.append(sp(5))
    _n=ParagraphStyle('pn7',fontName='Helvetica',fontSize=7.5,textColor=C_DKGRY,leading=11)

    kpi_data=[[p('PROGRAMME AVG ISI (PRE)','th'),p('PROGRAMME AVG ISI (POST)','th'),p('AVG REDUCTION','th'),p('4pt+ IMPROVEMENT RATE','th')],
              [Paragraph('<b>15.4</b>',ParagraphStyle('kv',fontName='Helvetica-Bold',fontSize=16,textColor=C_BLUE,leading=19,alignment=TA_CENTER)),
               Paragraph('<b>8.4</b>',ParagraphStyle('kv2',fontName='Helvetica-Bold',fontSize=16,textColor=C_GREEN,leading=19,alignment=TA_CENTER)),
               Paragraph('<b>–7.0 pts</b>',ParagraphStyle('kv3',fontName='Helvetica-Bold',fontSize=16,textColor=C_GOLD,leading=19,alignment=TA_CENTER)),
               Paragraph('<b>~82%</b>',ParagraphStyle('kv4',fontName='Helvetica-Bold',fontSize=16,textColor=HexColor('#5B6FA8'),leading=19,alignment=TA_CENTER))]]
    kt=Table(kpi_data,colWidths=[CW/4]*4)
    kt.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),C_DARK),('TEXTCOLOR',(0,0),(-1,0),white),
                              ('BACKGROUND',(0,1),(-1,1),C_LIGHT),('GRID',(0,0),(-1,-1),0.35,C_LGRAY),
                              ('FONTSIZE',(0,0),(-1,0),7.5),('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),
                              ('VALIGN',(0,0),(-1,-1),'MIDDLE'),('TOPPADDING',(0,0),(-1,-1),6),
                              ('BOTTOMPADDING',(0,0),(-1,-1),6),('LEFTPADDING',(0,0),(-1,-1),4),
                              ('ALIGN',(0,1),(-1,1),'CENTER')]))
    items.append(kt); items.append(sp(4))
    items.append(chart_avg_isi())
    items.append(Paragraph('On average, Noxora clients improve from <b>15.4</b> to <b>8.4</b> — a reduction of 7.0 points, '
                            'nearly 2× the clinical significance threshold.', _n))
    items.append(sp(4))
    items.append(Paragraph('Distribution of ISI Scores — Pre vs. Post Treatment',ST['sub']))
    r2=Table([[chart_dist('pre'),chart_dist('post')]],colWidths=[CW/2,CW/2])
    r2.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'TOP'),
                              ('LEFTPADDING',(0,0),(-1,-1),0),('RIGHTPADDING',(0,0),(-1,-1),0),
                              ('TOPPADDING',(0,0),(-1,-1),0),('BOTTOMPADDING',(0,0),(-1,-1),0),
                              ('GRID',(0,0),(-1,-1),0,white)]))
    items.append(r2); items.append(sp(4))
    items.append(chart_time_impact())
    items.append(Paragraph('54% of Noxora clients feel improvement within <b>3–5 weeks</b>; 27% within the first week.', _n))
    return items

def page8(pd):
    items = []
    items += section('ANNEXE A','Personal Questionnaires — Detailed Data')
    items.append(Paragraph('<b>INSOMNIA SEVERITY INDEX (ISI)</b>',ST['sub']))
    qs=['Difficulty falling asleep','Difficulty staying asleep','Waking up too early',
        'Sleep satisfaction','Noticeable to others','Worried about sleep','Interferes with functioning']
    rows=[[p('ITEM','th'),p('QUESTION','th'),p('PRE','th'),p('6-WEEK','th'),p('DELTA','th'),p('NOTE','th')]]
    for i,(q,pre_v,post_v) in enumerate(zip(qs, pd['pre_isi_q'], pd['post_isi_q']),1):
        d=int(post_v)-int(pre_v)
        note='Unchanged' if d==0 else ('Improvement' if d<0 else 'Worsened')
        rows.append([p(f'Q{i}','tdb'),p(q,'td'),p(str(int(pre_v)),'td'),p(str(int(post_v)),'td'),
                     p(f'{"–" if d<0 else "+" if d>0 else "0"}{abs(d)}','tdb'),p(note,'tdg')])
    rows.append([p('TOTAL','tdb'),p('ISI Total Score (0–28)','tdb'),p(str(pd['pre_isi_total']),'tdb'),
                 p(str(pd['post_isi_total']),'tdb'),p(delta_str(pd['pre_isi_total'],pd['post_isi_total']),'tdb'),p('Raw improvement','tdg')])
    rows.append([p('MED-ADJ','tdb'),p('Medication-adjusted ISI','tdb'),p(str(pd['pre_isi_med_adj']),'tdb'),
                 p(str(pd['post_isi_med_adj']),'tdb'),p(delta_str(pd['pre_isi_med_adj'],pd['post_isi_med_adj']),'tdb'),p('Primary outcome metric','tdg')])
    items.append(htable(rows,[16*mm,CW*0.37,14*mm,14*mm,13*mm,CW*0.17]))
    items.append(sp(5))

    items.append(Paragraph('<b>PITTSBURGH SLEEP QUALITY INDEX (PSQI)</b>',ST['sub']))
    items.append(htable([
        [p('ITEM','th'),p('QUESTION','th'),p('PRE','th'),p('6-WEEK','th'),p('DELTA','th')],
        [p('Q1','td'),p('Bedtime','td'),               p(str(pd['pre_psqi_bedtime']),'td'),  p(str(pd['post_psqi_bedtime']),'td'),  p('—','td')],
        [p('Q2','td'),p('Minutes to fall asleep','td'),p(str(pd['pre_psqi_latency']),'td'),  p(str(pd['post_psqi_latency']),'td'),  p(delta_str(pd['pre_psqi_latency'],pd['post_psqi_latency'],unit='min'),'td')],
        [p('Q4','td'),p('Net hours sleep','td'),        p(str(pd['pre_psqi_hours']),'td'),   p(str(pd['post_psqi_hours']),'td'),   p('—','td')],
        [p('Q5c','td'),p('Bathroom use','td'),          p(str(int(pd['pre_psqi_q5c'])),'td'),p(str(int(pd['post_psqi_q5c'])),'td'),p(delta_str(pd['pre_psqi_q5c'],pd['post_psqi_q5c'],unit=''),'td')],
        [p('Q5g','td'),p('Hot / heat disturbance','td'),p(str(int(pd['pre_psqi_q5g'])),'td'),p(str(int(pd['post_psqi_q5g'])),'td'),p(delta_str(pd['pre_psqi_q5g'],pd['post_psqi_q5g'],unit=''),'td')],
        [p('Q5h','tdb'),p('Bad dreams','tdb'),          p(str(int(pd['pre_psqi_q5h'])),'td'),p(str(int(pd['post_psqi_q5h'])),'tdb'),p(delta_str(pd['pre_psqi_q5h'],pd['post_psqi_q5h'],unit=''),'tdb')],
        [p('Q6','tdb'),p('Medication levels (0–3)','tdb'),p(str(int(pd['pre_psqi_q6'])),'tdb'),p(str(int(pd['post_psqi_q6'])),'tdb'),p(delta_str(pd['pre_psqi_q6'],pd['post_psqi_q6'],unit=''),'tdb')],
        [p('Q9','td'),p('Overall sleep quality','td'), p(str(int(pd['pre_psqi_q9'])),'td'), p(str(int(pd['post_psqi_q9'])),'td'), p(delta_str(pd['pre_psqi_q9'],pd['post_psqi_q9'],unit=''),'td')],
        [p('TOTAL','tdb'),p('PSQI Total Score (0–21)','tdb'),p(str(pd['pre_psqi_total']),'tdb'),p(str(pd['post_psqi_total']),'tdb'),p(delta_str(pd['pre_psqi_total'],pd['post_psqi_total']),'tdb')],
    ],[14*mm,CW*0.43,18*mm,18*mm,CW*0.14]))
    items.append(sp(5))

    items.append(Paragraph('<b>NOXORA SLEEP HABITS — Summary</b>',ST['sub']))
    items.append(htable([
        [p('MEASURE','th'),p('PRE-SRP','th'),p('6-WEEK','th'),p('DELTA','th'),p('NOTE','th')],
        [p('Bedtime (weekday)','td'),p(str(pd['pre_hab_bedtime']),'td'),p(str(pd['post_hab_bedtime']),'td'),p('—','td'),p('Sleep onset schedule','td')],
        [p('Prescribed medication (0–3)','td'),p(str(int(pd['pre_hab_prescribed'])),'td'),p(str(int(pd['post_hab_prescribed'])),'td'),p(delta_str(pd['pre_hab_prescribed'],pd['post_hab_prescribed'],unit=''),'tdb'),p('Discuss with physician','td')],
        [p('Unprescribed medication (0–3)','tdb'),p(str(int(pd['pre_hab_unprescribed'])),'tdb'),p(str(int(pd['post_hab_unprescribed'])),'tdb'),p(delta_str(pd['pre_hab_unprescribed'],pd['post_hab_unprescribed'],unit=''),'tdb'),p('Key recovery signal','td')],
        [p('Feel stressed (0–3)','td'),p(str(int(pd['pre_hab_stressed'])),'td'),p(str(int(pd['post_hab_stressed'])),'td'),p(delta_str(pd['pre_hab_stressed'],pd['post_hab_stressed'],unit=''),'td'),p('Sleep anxiety indicator','td')],
        [p('Habits Score (0–24, high=bad)','tdb'),p(str(pd['pre_hab_score']),'tdb'),p(str(pd['post_hab_score']),'tdb'),p(delta_str(pd['pre_hab_score'],pd['post_hab_score'],unit=''),'tdb'),p('Overall habits baseline','td')],
        [p('Weekend Habits (0–9, high=bad)','tdb'),p(str(pd['pre_hab_weekend']),'tdb'),p(str(pd['post_hab_weekend']),'tdb'),p(delta_str(pd['pre_hab_weekend'],pd['post_hab_weekend'],unit=''),'tdb'),p('Weekend pattern','td')],
    ],[CW*0.30,CW*0.12,CW*0.12,CW*0.12,CW*0.34]))
    return items

def page9(pd):
    items = []
    items += section('SECTION 08','Report Sign-Off')
    items.append(htable([
        [p('RECOMMENDED NEXT STEPS','th'),p('','th')],
        [p('12-week follow-up assessment (ISI + PSQI + Habits)','tdb'),p('Share this report with your treating physician','tdb')],
        [p(f"Contact Noxora if ISI score returns at or above {'10' if pd['post_isi_med_adj']<=10 else '14'}","td"),p('Continue to maintain your sleep hygiene baseline','td')],
    ],[CW/2,CW/2]))
    items.append(sp(6))
    items.append(htable([
        [p('COMPLETED BY','th'),p('DATE','th'),p('SIGNATURE','th')],
        [p(pd['lead_professional'],'td'),p(str(pd['report_date']),'td'),p('___________________________','td')],
        [p('','td'),p('','td'),p('','td')],
    ],[CW*0.35,CW*0.25,CW*0.40]))
    items.append(sp(10)); items+=[GoldHR(),sp(4)]
    items.append(Paragraph('LEGAL DISCLAIMER',ST['sec_lbl']))
    items.append(Paragraph(
        'This report has been prepared by Noxora for the exclusive use of the named patient and their treating '
        'healthcare professional. The information is based on validated psychometric instruments and clinical '
        'observation and is intended to support — not replace — professional medical advice, diagnosis, or '
        'treatment. Noxora\'s Sleep Recovery Programme is not a medical device and is not intended to '
        'diagnose, treat, cure, or prevent any disease. Individual results may vary. Scores reflect '
        'self-assessed data and should be interpreted in the context of a full clinical assessment. '
        'This document is confidential. Redistribution without prior written consent of Noxora is prohibited. '
        'noxorasleep.com', ST['legal']))
    items.append(sp(10)); items+=[GoldHR(),sp(6)]
    ftr=Table([[Paragraph('<b>NOXORA</b>',ParagraphStyle('fl',fontName='Helvetica-Bold',fontSize=16,textColor=C_DARK,leading=19)),
               Paragraph('Sleep, Restored. | noxorasleep.com',ParagraphStyle('ft',fontName='Helvetica',fontSize=9,textColor=C_DKGRY,leading=11,alignment=TA_RIGHT))]],
              colWidths=[CW/2,CW/2])
    ftr.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'MIDDLE'),('LEFTPADDING',(0,0),(-1,-1),0),('GRID',(0,0),(-1,-1),0,white)]))
    items.append(ftr)
    return items

# ── Main function ─────────────────────────────────────────────────────────────
def generate_pdf(patient_data: dict, notes: dict) -> bytes:
    """
    Generate a Noxora report PDF.
    Returns the PDF as bytes.
    """
    from reportlab.platypus import NextPageTemplate
    buf = io.BytesIO()

    doc = NoxoraDoc(buf, patient_data,
                    pagesize=A4, leftMargin=ML, rightMargin=MR,
                    topMargin=MT, bottomMargin=MB,
                    title=f"Noxora Sleep Recovery Report — {patient_data['first_name']} {patient_data['last_name']}",
                    author='Noxora')
    doc._pg[0] = 1

    story = cover_story(patient_data, notes)
    story.append(NextPageTemplate('Body'))
    for fn, args in [
        (page2, (patient_data, notes)),
        (page3, (patient_data, notes)),
        (page4, (patient_data, notes)),
        (page5, (patient_data, notes)),
        (page6, (patient_data, notes)),
        (page7, ()),
        (page8, (patient_data,)),
        (page9, (patient_data,)),
    ]:
        story.append(PageBreak())
        story += fn(*args)

    doc.build(story)
    buf.seek(0)
    return buf.read()
