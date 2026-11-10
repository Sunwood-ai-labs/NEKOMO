"""Apply a horizontal roof/body colour boundary to the verified empty bus."""
from pathlib import Path
import json,hashlib
import FreeCAD as App,Part,MeshPart
ROOT=Path(__file__).resolve().parent
OUT=ROOT/'two-color';OUT.mkdir(exist_ok=True)
source_doc=App.openDocument(str(ROOT/'corrected/nekomo-v06-clear-cabin.FCStd'))
solid=source_doc.getObject('PhysicalBus').Shape.Solids[0].copy()
doc=App.newDocument('NekomoV06RedWhite')
physical=doc.addObject('Part::Feature','PhysicalBus');physical.Shape=solid
mask=doc.addObject('Part::Box','RoofColorBoundary');mask.Length=80;mask.Width=80;mask.Height=20;mask.Placement.Base=App.Vector(-10,-40,31.075)
doc.recompute()
red_shape=solid.common(mask.Shape).removeSplitter();white_shape=solid.cut(red_shape).removeSplitter()
red=doc.addObject('Part::Feature','RedRoof');red.Shape=red_shape
white=doc.addObject('Part::Feature','WhiteBody');white.Shape=white_shape
assert red.Shape.isValid() and white.Shape.isValid()
checks={'overlap_mm3':red.Shape.common(white.Shape).Volume,'missing_mm3':physical.Shape.cut(red.Shape.fuse(white.Shape)).Volume,'extra_mm3':red.Shape.fuse(white.Shape).cut(physical.Shape).Volume}
assert all(abs(x)<1e-6 for x in checks.values()),checks
records={}
for name,obj in [('red-roof',red),('white-body',white)]:
 for pose in ['upright','inverted']:
  shape=obj.Shape.copy()
  if pose=='inverted':shape.rotate(App.Vector(),App.Vector(1,0,0),180);shape.translate(App.Vector(0,0,35.568058013916016))
  mesh=MeshPart.meshFromShape(Shape=shape,LinearDeflection=.06,AngularDeflection=.12,Relative=False)
  p=OUT/(name+'-'+pose+'.stl');mesh.write(str(p));records[p.name]={'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'triangles':mesh.CountFacets}
doc.saveAs(str(OUT/'nekomo-v06-red-white.FCStd'))
report={'colors':{'roof':'red PLA','body_and_fixed_wheels':'white PLA'},'boundary_assembled_Z_mm':31.075,'color_checks':checks,'physical_volume_mm3':physical.Shape.Volume,'exports':records,'physical_geometry':'Same verified clear-cabin candidate; no geometry changes for colour placement.'}
(OUT/'geometry.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report))
