"""Colour-only alternative: red roof and four red tyres, white hubs/body."""
from pathlib import Path
import hashlib,json
import FreeCAD as App,Part,MeshPart
ROOT=Path(__file__).resolve().parent
OUT=ROOT/'two-color-red-tyres';OUT.mkdir(exist_ok=True)
SOURCE=ROOT/'two-color/nekomo-v06-red-white.FCStd'
baseline_hash=hashlib.sha256(SOURCE.read_bytes()).hexdigest()
baseline=App.openDocument(str(SOURCE));physical=baseline.getObject('PhysicalBus').Shape.Solids[0].copy()
roof=baseline.getObject('RedRoof').Shape.copy()
src=App.openDocument(str(ROOT.parent/'school-bus-v04-dr/cad/nekomo-school-bus-v04.FCStd'))
scale=60.0/160.2561472076974
scale_y=float(src.getObject('WidenedChassisInput').YScaleFactor)
chassis_mesh=MeshPart.meshFromShape(Shape=src.getObject('MiniChassis').Shape,LinearDeflection=.06,AngularDeflection=.12,Relative=False)
cy=(chassis_mesh.BoundBox.YMin+chassis_mesh.BoundBox.YMax)/2
matrix=App.Matrix();matrix.A11=scale;matrix.A22=scale*scale_y;matrix.A24=cy*(1-scale_y);matrix.A33=scale
regions=[];wheel_checks={}
for name in ['Wheel00','Wheel01','Wheel10','Wheel11']:
    wheel=src.getObject(name).Shape.copy().transformGeometry(matrix)
    hub=src.getObject(name+'Hub').Shape.copy().transformGeometry(matrix)
    tyre=wheel.cut(hub).common(physical).removeSplitter()
    assert tyre.isValid() and tyre.Volume>0
    regions.append(tyre)
    wheel_checks[name]={'red_tyre_volume_mm3':tyre.Volume,'white_hub_overlap_mm3':tyre.common(hub).Volume}
red=Part.makeCompound([roof]+regions)
white=physical.cut(red).removeSplitter()
assert red.isValid() and white.isValid()
checks={'overlap_mm3':red.common(white).Volume,'missing_mm3':physical.cut(red.fuse(white)).Volume,'extra_mm3':red.fuse(white).cut(physical).Volume}
assert all(abs(v)<1e-5 for v in checks.values()),checks
doc=App.newDocument('NekomoV06RedTyres')
for name,shape in [('PhysicalBus',physical),('RedRoofAndTyres',red),('WhiteBodyAndHubs',white)]:
    obj=doc.addObject('Part::Feature',name);obj.Shape=shape
exports={}
for label,shape in [('red-roof-tyres',red),('white-body-hubs',white)]:
    for pose in ['upright','inverted']:
        out_shape=shape.copy()
        if pose=='inverted':out_shape.rotate(App.Vector(),App.Vector(1,0,0),180);out_shape.translate(App.Vector(0,0,35.568058013916016))
        mesh=MeshPart.meshFromShape(Shape=out_shape,LinearDeflection=.06,AngularDeflection=.12,Relative=False)
        path=OUT/(label+'-'+pose+'.stl');mesh.write(str(path))
        exports[path.name]={'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'triangles':mesh.CountFacets}
doc.recompute();doc.saveAs(str(OUT/'nekomo-v06-red-tyres.FCStd'))
report={'variant':'red-roof-and-red-tyres-white-body-white-hubs','physical_geometry_unchanged':True,'physical_volume_mm3':physical.Volume,'color_checks':checks,'tyres':wheel_checks,'source_white_tyre_cad_sha256':baseline_hash,'source_white_tyre_cad_unchanged':baseline_hash==hashlib.sha256(SOURCE.read_bytes()).hexdigest(),'exports':exports,'status':'CAD only; not yet sliced or printed'}
(OUT/'geometry.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report))
