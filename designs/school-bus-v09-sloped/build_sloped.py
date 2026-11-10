"""FreeCAD study of a continuously sloped bonnet, retaining old variants."""
import FreeCAD as App
import FreeCADGui as Gui
import Part, MeshPart, json, math
ROOT='C:/Prj/NEKOMO/designs/school-bus-v09-sloped'
V=App.Vector
def rounded(l,w,h,x,y,z,r):
    s=Part.makeBox(l,w,h,V(x,y,z))
    return s.makeFillet(r,s.Edges)

# A cubic Bezier preserves a smooth top without a horizontal starting shelf.
# All control-polygon dz/dx slopes are >= 0.933; inverted lateral growth
# is therefore <= 0.2143 mm per 0.2 mm layer on the untouched bonnet face.
controls=[(0.,5.2),(3.,8.),(5.6,11.4),(9.,14.8)]
def bonnet_prism(y0,width,vertical_offset=0.):
    c=Part.BezierCurve()
    c.setPoles([V(x,y0,z+vertical_offset) for x,z in controls])
    a=V(0,y0,-2);b=V(9,y0,-2)
    edges=[Part.makeLine(a,b),Part.makeLine(b,V(9,y0,14.8+vertical_offset)),
           c.toShape(),Part.makeLine(V(0,y0,5.2+vertical_offset),a)]
    return Part.Face(Part.Wire(edges)).extrude(V(0,width,0))

doc=App.newDocument('SlopedBusV09')
outer=rounded(35,18,22,7,-9,2,2.8)
nose=bonnet_prism(-9,18)
# Clip the lower nose to the original lower body level; its upper surface is curved.
nose=nose.common(Part.makeBox(15,25,25,V(-1,-12.5,2)))
# Round upright leading corners without introducing a horizontal hood shelf.
vertical=[e for e in nose.Edges if e.BoundBox.ZLength>1 and e.BoundBox.XLength<1e-6 and e.BoundBox.YLength<1e-6]
nose=nose.makeFillet(0.8,vertical)
outer=outer.fuse(nose).removeSplitter()
interior=Part.makeBox(31.8,14.8,25,V(8.6,-7.4,-3))
inside_nose=bonnet_prism(-7.4,14.8,-2.4).common(Part.makeBox(10,20,30,V(1.6,-10,-3)))
interior=interior.fuse(inside_nose)
shell=outer.cut(interior).removeSplitter()
for x in [14.,23.,32.]:
    c=Part.makeBox(6.4,24,7,V(x-3.2,-12,13.5))
    c=c.makeFillet(1.3,[e for e in c.Edges if e.BoundBox.YLength>23])
    shell=shell.cut(c)
# Retain a solid connection from the cabin front to the rear of the slope.
c=Part.makeBox(12,13,4.4,V(-1,-6.5,16.))
c=c.makeFillet(1.1,[e for e in c.Edges if e.BoundBox.XLength>11])
shell=shell.cut(c).removeSplitter()
wheels=[]
for x in [8.,34.]:
    for side in [-1,1]:
        w=Part.makeCone(4,3.1,2,V(x,side*8.5,4),V(0,side,0))
        groove=Part.makeCylinder(2.2,.35,V(x,side*10.2,4),V(0,side,0)).cut(Part.makeCylinder(1.7,.6,V(x,side*10.1,4),V(0,side,0)))
        wheels.append(w.cut(groove))
whole=shell
for w in wheels: whole=whole.fuse(w)
whole=whole.removeSplitter()
assert whole.isValid() and whole.isClosed() and len(whole.Solids)==1
white=whole.common(Part.makeBox(60,40,10,V(-5,-20,21.2))).removeSplitter()
red=whole.cut(white).removeSplitter()
for name,s,col in [('RedBodyAndTires',red,(.78,.055,.035)),('WhiteRoof',white,(.93,.92,.87))]:
    o=doc.addObject('Part::Feature',name);o.Shape=s;o.ViewObject.ShapeColor=col
    o.addProperty('App::PropertyString','BonnetControlPoints');o.BonnetControlPoints=json.dumps(controls)
    p=s.copy();p.rotate(V(0,0,0),V(1,0,0),180);p.translate(V(0,0,24))
    MeshPart.meshFromShape(Shape=p,LinearDeflection=.025,AngularDeflection=.08,Relative=False).write(ROOT+'/exports/'+name+'-inverted.stl')
p=whole.copy();p.rotate(V(0,0,0),V(1,0,0),180);p.translate(V(0,0,24))
MeshPart.meshFromShape(Shape=p,LinearDeflection=.025,AngularDeflection=.08,Relative=False).write(ROOT+'/exports/whole-inverted.stl')
doc.recompute();doc.saveAs(ROOT+'/cad/sloped-bus.FCStd')
Part.export(doc.Objects,ROOT+'/exports/sloped-bus.step')
report=dict(valid=whole.isValid(),closed=whole.isClosed(),solids=len(whole.Solids),
    dimensions_mm=[whole.BoundBox.XLength,whole.BoundBox.YLength,whole.BoundBox.ZLength],
    volume_mm3=whole.Volume,bonnet_bezier_control_points_xz=controls,
    bonnet_vertical_shell_offset_mm=2.4,minimum_top_slope_dz_dx=2.8/3,
    maximum_ideal_lateral_growth_per_02mm_layer=.2/(2.8/3),
    maximum_ideal_overhang_from_vertical_deg=math.degrees(math.atan(3/2.8)),
    support_enabled=False,physical_print=False,
    change='Continuous curved bonnet; windshield bottom moved from 14.2 to 16.0 mm to preserve bonnet-to-cabin support')
with open(ROOT+'/evidence/geometry.json','w') as f: json.dump(report,f,indent=2)
print(json.dumps(report))
