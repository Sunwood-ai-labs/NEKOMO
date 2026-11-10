from pathlib import Path
import json,hashlib
import FreeCAD as App, Part, MeshPart
ROOT=Path(__file__).resolve().parent/'corrected'
ROOT.mkdir(parents=True,exist_ok=True)
SOURCE=ROOT.parents[1]/'school-bus-v04-dr/cad/nekomo-school-bus-v04.FCStd'
before=hashlib.sha256(SOURCE.read_bytes()).hexdigest()
src=App.openDocument(str(SOURCE));physical=src.getObject('PhysicalBus').Shape.copy()
tool=Part.makeBox(39,23.1,30.3,App.Vector(14,2.8,-1))
s=physical.cut(tool).removeSplitter()
assert s.isValid() and s.isClosed() and len(s.Solids)==1
clearance=Part.makeBox(38.98,23.08,29.28,App.Vector(14.01,2.81,.01))
assert s.common(clearance).Volume<1e-6
records={}
def output(shape,name):
    m=MeshPart.meshFromShape(Shape=shape,LinearDeflection=.06,AngularDeflection=.12,Relative=False)
    path=ROOT/(name+'.stl');m.write(str(path));bb=m.BoundBox
    records[name]={'path':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'triangles':m.CountFacets,'bounds':[bb.XMin,bb.YMin,bb.ZMin,bb.XMax,bb.YMax,bb.ZMax],'dimensions':[bb.XLength,bb.YLength,bb.ZLength]}
    return bb
bb=output(s,'clear-cabin-upright')
inverted=s.copy();inverted.rotate(App.Vector(0,0,0),App.Vector(1,0,0),180);inverted.translate(App.Vector(0,0,bb.ZMax))
output(inverted,'clear-cabin-inverted')
doc=App.newDocument('NekomoV06ClearCabin');base=doc.addObject('Part::Feature','SourceBody');base.Shape=physical
c=doc.addObject('Part::Box','CabinOpeningTool');c.Length=39;c.Width=23.1;c.Height=30.3;c.Placement.Base=App.Vector(14,2.8,-1)
obj=doc.addObject('Part::Cut','PhysicalBus');obj.Base=base;obj.Tool=c;obj.Refine=True
doc.recompute();doc.saveAs(str(ROOT/'nekomo-v06-clear-cabin.FCStd'));Part.export([obj],str(ROOT/'clear-cabin.step'))
report={'valid':s.isValid(),'closed':s.isClosed(),'solids':len(s.Solids),'volume_mm3':s.Volume,'removed_mm3':physical.Volume-s.Volume,'cabin_clearance_box':{'min':[14.01,2.81,.01],'size':[38.98,23.08,29.28],'remaining_solid_mm3':s.common(clearance).Volume},'source_sha256':before,'source_unchanged':hashlib.sha256(SOURCE.read_bytes()).hexdigest()==before,'exports':records,'scope':'Geometry only. Permanent open cabin; perimeter rails, fore/aft ledges and roof attachment retained. No physical strength or child-use verification.'}
(ROOT/'geometry.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report))
