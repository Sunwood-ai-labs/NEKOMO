"""Isolated visual/manufacturing study. Run inside FreeCAD; never sends a print."""
import FreeCAD as App
import FreeCADGui as Gui
import Part, MeshPart, json, os
ROOT = 'C:/Prj/NEKOMO/designs/school-bus-v08-photo'
P = dict(length=42., body_width=18., height=24., wall=1.6,
         wheel_radius=4., wheel_centers=[8.,34.], side_windows=[14.,23.,32.])
V=App.Vector
def rounded(l,w,h,x,y,z,r):
    s=Part.makeBox(l,w,h,V(x,y,z))
    return s.makeFillet(r,s.Edges)
doc=App.newDocument('PhotoBusV08')
# Main cabin with softly rounded corners and a lower nose.
outer=rounded(35,18,22,7,-9,2,2.8).fuse(rounded(13,18,12,0,-9,2,2.4)).removeSplitter()
# Open bottom: two intersecting spaces preserve the lower bonnet and roof.
inside=Part.makeBox(31.8,14.8,25,V(8.6,-7.4,-3))
inside=inside.fuse(Part.makeBox(8.7,14.8,13.4,V(1.6,-7.4,-1)))
shell=outer.cut(inside).removeSplitter()
for x in P['side_windows']:
    # Fillet the four edges parallel to Y, giving rounded rectangular through windows.
    c=Part.makeBox(6.4,24,7,V(x-3.2,-12,13.5))
    c=c.makeFillet(1.3,[e for e in c.Edges if e.BoundBox.YLength>23])
    shell=shell.cut(c)
# Upright windshield located on the cabin front, above the nose.
c=Part.makeBox(12,13,6.2,V(-1,-6.5,14.2))
c=c.makeFillet(1.1,[e for e in c.Edges if e.BoundBox.XLength>11])
shell=shell.cut(c).removeSplitter()
wheel_shapes=[]
for x in P['wheel_centers']:
    for side in [-1,1]:
        # Tapered outer face rather than a completely unsupported cylinder rim.
        wheel=Part.makeCone(4,3.1,2.0,V(x,side*8.5,4),V(0,side,0))
        groove=Part.makeCylinder(2.2,0.35,V(x,side*10.2,4),V(0,side,0)).cut(Part.makeCylinder(1.7,0.6,V(x,side*10.1,4),V(0,side,0)))
        wheel=wheel.cut(groove)
        wheel_shapes.append(wheel)
whole=shell
for wheel in wheel_shapes: whole=whole.fuse(wheel)
whole=whole.removeSplitter()
assert whole.isValid() and whole.isClosed() and len(whole.Solids)==1
# Reference pattern: roof and wheels are the contrasting colour, body the main colour.
roof=whole.common(Part.makeBox(60,40,10,V(-5,-20,21.2)))
accent=roof
for wheel in wheel_shapes: accent=accent.fuse(whole.common(wheel))
accent=accent.removeSplitter()
body=whole.cut(accent).removeSplitter()
for name,shape,color in [('Body',body,(0.78,0.055,0.035)),('RoofAndWheels',accent,(0.93,0.92,0.87))]:
    obj=doc.addObject('Part::Feature',name);obj.Shape=shape;obj.ViewObject.ShapeColor=color
    obj.ViewObject.LineColor=(0.22,0.18,0.15)
    obj.addProperty('App::PropertyString','ParametersJSON');obj.ParametersJSON=json.dumps(P)
    q=shape.copy();q.rotate(V(0,0,0),V(1,0,0),180);q.translate(V(0,0,24))
    MeshPart.meshFromShape(Shape=q,LinearDeflection=0.06,AngularDeflection=0.15,Relative=False).write(ROOT+'/exports/'+name+'-inverted.stl')
q=whole.copy();q.rotate(V(0,0,0),V(1,0,0),180);q.translate(V(0,0,24))
MeshPart.meshFromShape(Shape=q,LinearDeflection=0.06,AngularDeflection=0.15,Relative=False).write(ROOT+'/exports/whole-inverted.stl')
Part.export(doc.Objects,ROOT+'/exports/photo-bus.step')
doc.recompute();doc.saveAs(ROOT+'/cad/photo-bus.FCStd')
Gui.activeDocument().activeView().viewAxonometric();Gui.activeDocument().activeView().fitAll()
Gui.activeDocument().activeView().saveImage(ROOT+'/evidence/assembled.png',1400,1000,'White')
bb=whole.BoundBox
report=dict(parameters=P,valid=whole.isValid(),closed=whole.isClosed(),solids=len(whole.Solids),
    dimensions_mm=[bb.XLength,bb.YLength,bb.ZLength],volume_mm3=whole.Volume,
    floor_probe_mm3=whole.common(Part.makeBox(3,3,18,V(20,-1.5,-1))).Volume,
    color_overlap_mm3=body.common(accent).Volume,
    colour_reconstruction_error_mm3=abs(body.fuse(accent).Volume-whole.Volume),
    roof_flat_contact_mm2=sum(f.Area for f in q.Faces if abs(f.BoundBox.ZMin)<1e-5 and abs(f.BoundBox.ZMax)<1e-5),
    caveats=['Visual and slicing study; no physical print or child-use acceptance', 'Rounded tire overhang and window bridges need toolpath review'])
with open(ROOT+'/evidence/geometry.json','w') as f: json.dump(report,f,indent=2)
print(json.dumps(report))
