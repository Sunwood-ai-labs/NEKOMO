import html
import json
from pathlib import Path

import FreeCAD as App
import TechDraw


root = Path(__file__).resolve().parent
report = json.loads((root / 'evidence' / 'geometry-report.json').read_text(encoding='utf-8'))
doc = App.openDocument(str(root / 'cad' / 'nekomo-school-bus-v01.FCStd'))
total = doc.getObject('Total') or doc.getObject('TotalShape') or doc.getObject('FinalSolid')
if total is None:
    raise RuntimeError('The verified whole-bus object was not found in the CAD document.')
shape = total.Shape
bb = shape.optimalBoundingBox()


def project(direction):
    return TechDraw.projectToSVG(shape, App.Vector(*direction)).replace('stroke-width="1.0"', 'stroke-width="0.24"')


side = project((0, -1, 0))
front = project((-1, 0, 0))
top = project((0, 0, 1))
dimension_text = f'{bb.XLength:.1f} × {bb.YLength:.1f} × {bb.ZLength:.1f} mm'
svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="1120" height="800" viewBox="0 0 560 400">
<rect width="560" height="400" fill="#fffdf8"/>
<style>text{{font-family:'Yu Gothic','Meiryo',sans-serif;fill:#3b332f}}.label{{font-size:7px}}.small{{font-size:5px}}.dim{{stroke:#8b776a;stroke-width:0.35;fill:none}}</style>
<text x="30" y="24" font-size="13" font-weight="bold">NEKOMO スクールバス 試作設計 v0.1</text>
<text x="30" y="38" font-size="7">一体構造　固定車輪　外形 {html.escape(dimension_text)}</text>
<g transform="translate(35 175) scale(1.4) rotate(90)">{side}</g>
<text x="35" y="195" class="label">側面</text>
<g transform="translate(425 175) scale(1.4) rotate(90)">{front}</g>
<text x="330" y="195" class="label">前面</text>
<g transform="translate(35 310) scale(1.4)">{top}</g>
<text x="35" y="328" class="label">上面</text>
<path class="dim" d="M {35+1.4*bb.XMin:.2f} 187 V 201 M {35+1.4*bb.XMax:.2f} 187 V 201 M {35+1.4*bb.XMin:.2f} 201 H {35+1.4*bb.XMax:.2f}"/>
<text x="115" y="211" class="small">全長 {bb.XLength:.1f} mm</text>
<text x="330" y="211" class="small">全幅 {bb.YLength:.1f} mm　全高 {bb.ZLength:.1f} mm</text>
<text x="320" y="250" class="label">設計上の確認値</text>
<text x="320" y="266" class="small">側壁 5 mm　窓柱 10 mm</text>
<text x="320" y="279" class="small">側面窓 26 × 29 mm　角 R5 mm</text>
<text x="320" y="292" class="small">屋根裏 45度　中央橋渡し 20 mm</text>
<text x="320" y="305" class="small">上記は設計寸法であり、安全合否値ではない</text>
<path d="M 30 350 H 530" stroke="#d8cbbd" stroke-width="0.5"/>
<text x="30" y="365" class="small">FreeCAD TechDrawによるCAD実形状の投影。寸法単位 mm。図の表示倍率で寸法を測定しない。</text>
<text x="30" y="378" class="small">3歳未満向けを目標とする評価用試作。現物の破損・小部品・挟み込み・材料評価は未実施。</text>
</svg>'''
(root / 'exports' / 'nekomo-school-bus-v01-drawing.svg').write_text(svg, encoding='utf-8')
print(json.dumps({'drawing': str(root / 'exports' / 'nekomo-school-bus-v01-drawing.svg'), 'source_object': total.Name, 'dimensions_mm': [bb.XLength, bb.YLength, bb.ZLength]}))
