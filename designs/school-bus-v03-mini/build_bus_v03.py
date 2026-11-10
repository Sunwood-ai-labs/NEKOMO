import sys
from pathlib import Path
import json
import math
import FreeCAD as App
import Part
import MeshPart

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import cad_helpers as h

DOC_NAME = 'NekomoSchoolBusV03'


def prism(doc, name, plane, origin, points, radius, direction, length):
    sketch = h.create_sketch(doc, name + 'Profile', name + ' profile', plane, origin)
    h.add_profile(sketch, points, radius)
    doc.recompute()
    return h.extrusion(doc, name, name, sketch, direction, length)


def rounded_rectangle(x, y, length, width):
    return [(x,y),(x+length,y),(x+length,y+width),(x,y+width)]


def ring(doc, name, x, y, length, width, radius, z, depth, thickness):
    outer = prism(doc, name+'Outer','XY',(0,0,z),rounded_rectangle(x,y,length,width),radius,(0,0,1),depth)
    inner = prism(doc, name+'Inner','XY',(0,0,z-0.2),rounded_rectangle(x+thickness,y+thickness,length-2*thickness,width-2*thickness),radius-thickness,(0,0,1),depth+0.4)
    return h.cut(doc,name,name,outer,inner)


def export_mesh(shape, path):
    MeshPart.meshFromShape(Shape=shape,LinearDeflection=0.06,AngularDeflection=0.12,Relative=False).write(str(path))


def main():
    if (ROOT/'cad'/'nekomo-school-bus-v03.FCStd').exists():
        raise RuntimeError('The v03 CAD already exists; do not overwrite a reviewed revision.')
    if DOC_NAME in App.listDocuments():
        raise RuntimeError('The v03 document is already open.')
    doc=App.newDocument(DOC_NAME)
    doc.Label='NEKOMO School Bus v03 reference-led assembly'
    print('BODY',flush=True)
    side=[(0,20),(156,20),(156,83),(29,83),(18,51),(0,46)]
    raw=prism(doc,'BodyExtrusion','XZ',(0,0,0),side,9,(0,1,0),77)
    edges=h.plane_edges_at(raw.Shape,'Y',[0,77])
    outer=h.add_fillet(doc,'BodySoftEdges','Body broad soft edges R7',raw,edges,7)
    cavity=prism(doc,'CabinOpening','XY',(0,0,18),rounded_rectangle(30,6,120,65),8,(0,0,1),100)
    shell=h.cut(doc,'HollowBody','Open top and bottom body',outer,cavity)
    bottom=h.create_box(doc,'BodyBottomTrim','Flat assembly landing',-10,-10,-10,180,100,32)
    shell=h.cut(doc,'BodyLanding','Body landing at Z22',shell,bottom)
    tools=[]
    for i,x in enumerate([36,76,116]):
        tools.append(prism(doc,'SideWindow'+str(i),'XZ',(0,-4,0),rounded_rectangle(x,46,30,29),7,(0,1,0),85))
    tools.append(prism(doc,'FrontWindow','YZ',(-5,0,0),rounded_rectangle(9,52,59,26),8,(1,0,0),43))
    tools.append(prism(doc,'RearWindow','YZ',(147,0,0),rounded_rectangle(10,48,57,28),7,(1,0,0),16))
    windows=h.fuse(doc,'WindowCutters','All window tools',tools)
    shell=h.cut(doc,'Windows','Three side windows and broad front window',shell,windows)
    print('CHASSIS',flush=True)
    floor=h.rounded_box(doc,'Floor','Rounded thin bumper and floor',0,0,10,156,77,12,4.8)
    core=[floor]
    wheel_hubs=[]
    arch_tools=[]
    for side_i,(y0,y1) in enumerate([(-4,4),(73,81)]):
        for pos_i,x in enumerate([37,123]):
            name='Wheel%d%d'%(side_i,pos_i)
            rawwheel=h.create_axis_cylinder(doc,name+'Blank',name,17,8,(x,y0,17),'Y')
            rim=h.add_fillet(doc,name,'Rounded fixed tyre',rawwheel,h.plane_edges_at(rawwheel.Shape,'Y',[y0,y1]),3)
            core.append(rim)
            f0=-1.5 if side_i==0 else 73.5
            disk=h.create_axis_cylinder(doc,name+'FenderOuter','Fender outside',23,5,(x,f0,17),'Y')
            hole=h.create_axis_cylinder(doc,name+'FenderInner','Fender inside',18.3,7,(x,f0-1,17),'Y')
            annulus=h.cut(doc,name+'FenderRing','Fender annulus',disk,hole)
            upper=h.create_box(doc,name+'FenderClip','Upper fender half',x-25,f0-1,17,50,7,25)
            fender=h.common(doc,name+'Fender','Integral upper tyre arch',[annulus,upper])
            core.append(fender)
            arch_tools.append(h.create_axis_cylinder(doc,name+'BodyClearance','Body clearance around fender',23.8,10,(x,-5 if side_i==0 else 72,17),'Y'))
            hub_y=y0 if side_i==0 else y1-1.2
            wheel_hubs.append(h.create_axis_cylinder(doc,name+'Hub','Integrated ivory colour region',8.5,1.2,(x,hub_y,17),'Y'))
    arch_union=h.fuse(doc,'WheelArchClearances','Fixed fender clearance tools',arch_tools)
    shell=h.cut(doc,'BodyWithArches','Gold body with curved wheel openings',shell,arch_union)
    guide=ring(doc,'ChassisGuide',30.8,6.8,118.4,63.4,7.2,21.5,8,5.35)
    core.append(guide)
    for row,x in enumerate([50,87,124]):
        core.append(h.rounded_box(doc,'Bench'+str(row),'Broad integral bench',x-9,6.8,21.5,18,63.4,7.5,3))
        for j,y in enumerate([6.8,48.2]):
            core.append(h.rounded_box(doc,'Back%d%d'%(row,j),'Rounded broad seat back',x+2,y,27,9,22,32,4))
    chassis=h.fuse(doc,'ChassisBase','Floor, fixed wheels, fenders and seating',core+wheel_hubs)
    h.require_solid_shape(chassis.Shape,'Chassis',1)
    ivory_chassis=h.common(doc,'ChassisIvory','Ivory hub colour regions',[h.fuse(doc,'HubRegions','Hub colour inputs',wheel_hubs),chassis])
    cocoa_chassis=h.cut(doc,'ChassisCocoa','Cocoa chassis colour region',chassis,ivory_chassis)
    print('BODY ACCENTS',flush=True)
    cocoa_body=[]
    band_points=[(14,38),(18,43),(28,47),(155,47),(155,42),(29,42),(18,37)]
    for i,y in enumerate([-0.25,75.75]):
        cocoa_body.append(prism(doc,'SideSwoosh'+str(i),'XZ',(0,y,0),band_points,0.8,(0,1,0),1.5))
    cocoa_body.append(prism(doc,'Grille','YZ',(-3,0,0),rounded_rectangle(28,28,21,13),3,(1,0,0),7))
    ivory_body=[]
    for i,y in enumerate([16,61]):
        housing=h.create_axis_cylinder(doc,'LampHousing'+str(i),'Rounded lamp housing',9,6,( -3,y,34),'X')
        housing=h.add_fillet(doc,'LampHousingRound'+str(i),'Lamp housing edge radius',housing,h.plane_edges_at(housing.Shape,'X',[-3,3]),1)
        cocoa_body.append(housing)
        lens=h.create_axis_cylinder(doc,'LampLens'+str(i),'Ivory integrated lamp lens',7,1.2,(-3.5,y,34),'X')
        lens=h.add_fillet(doc,'LampLensRound'+str(i),'Soft lamp lens edge',lens,h.plane_edges_at(lens.Shape,'X',[-3.5,-2.3]),0.45)
        ivory_body.append(lens)
    for i,y in enumerate([12,57]):
        cocoa_body.append(prism(doc,'RearLamp'+str(i),'YZ',(154,0,0),rounded_rectangle(y,31,8,8),2.6,(1,0,0),2))
    body=h.fuse(doc,'BodyAssembly','Body with integrated accent regions',[shell]+cocoa_body+ivory_body)
    slots=[]
    for i,z in enumerate([31,35]):
        slots.append(prism(doc,'GrilleSlot'+str(i),'YZ',(-5,0,0),rounded_rectangle(31,z,15,1.6),0.65,(1,0,0),9))
    body=h.cut(doc,'BodyFinal','Finished separate body',body,h.fuse(doc,'GrilleSlots','Grille slot tools',slots))
    h.require_solid_shape(body.Shape,'Body',1)
    ivory_body=h.common(doc,'BodyIvory','Ivory lamp regions',[h.fuse(doc,'LensRegions','Lens inputs',ivory_body),body])
    brown_body=h.common(doc,'BodyCocoa','Cocoa stripe and lamp surrounds',[h.fuse(doc,'BrownBodyRegions','Brown body inputs',cocoa_body),body])
    brown_body=h.cut(doc,'BodyCocoaFinal','Cocoa without ivory',brown_body,ivory_body)
    gold_body=h.cut(doc,'BodyGold','Gold body region',body,h.fuse(doc,'BodyNonGold','Non-gold body regions',[brown_body,ivory_body]))
    print('ROOF',flush=True)
    profiles=[]
    roof_sections=[(83,22,-1,134.5,79,14),(87.5,22,-1,134.5,79,15),(93,28,4,123,69,18),(95,40,15,99,47,18)]
    for i,(z,x,y,l,w,r) in enumerate(roof_sections):
        sk=h.create_sketch(doc,'RoofSection'+str(i),'Rounded roof outline '+str(i),'XY',(0,0,z))
        h.add_profile(sk,rounded_rectangle(x,y,l,w),r)
        profiles.append(sk)
    doc.recompute()
    dome=doc.addObject('Part::Loft','RoofDome');dome.Sections=profiles;dome.Solid=True;dome.Ruled=False;doc.recompute()
    h.require_solid_shape(dome.Shape,'Rounded roof dome',1)
    skirt=ring(doc,'RoofGuide',30.8,6.8,118.4,63.4,7.2,75.5,8,5.35)
    roof=h.fuse(doc,'RoofFinal','Separate roof with broad locating skirt',[dome,skirt])
    h.require_solid_shape(roof.Shape,'Roof',1)
    parts={'body':body,'chassis':chassis,'roof':roof}
    colours={'body-gold':(gold_body,'#FFFFFF'),'body-cocoa':(brown_body,'#C12E1F'),'body-ivory':(ivory_body,'#FFFFFF'),'chassis-cocoa':(cocoa_chassis,'#C12E1F'),'chassis-ivory':(ivory_chassis,'#FFFFFF'),'roof-cocoa':(roof,'#C12E1F')}
    # Native App::Link scaling keeps the editable source feature tree.
    scale = 60.0 / 160.2561472076974
    def mini_link(obj, name):
        link = doc.addObject('App::Link', name)
        link.setLink(obj)
        link.Scale = scale
        link.addProperty('App::PropertyString','DesignBasis','MiniBus')
        link.DesignBasis = '60 mm bus; source guides strengthened before scaling'
        return link
    parts = {name: mini_link(obj, 'Mini'+name.title()) for name,obj in parts.items()}
    colours = {name: (mini_link(obj,'MiniColour'+str(i)), colour) for i,(name,(obj,colour)) in enumerate(colours.items())}
    doc.recompute()
    assembly=Part.makeCompound([obj.Shape for obj in parts.values()])
    bb=assembly.optimalBoundingBox()
    intersections={a+'_'+b:parts[a].Shape.common(parts[b].Shape).Volume for a,b in [('body','chassis'),('body','roof'),('chassis','roof')]}
    report={'revision':'v03','basis':'CAD analysis, not physical toy safety validation','assembled_dimensions_mm':[bb.XLength,bb.YLength,bb.ZLength],'assembled_bounds_mm':[bb.XMin,bb.YMin,bb.ZMin,bb.XMax,bb.YMax,bb.ZMax],'physical_parts':{},'interference_volume_mm3':intersections,'fit_clearance_per_side_mm':0.8*scale,'guide_wall_mm':5.35*scale,'guide_height_mm':8*scale,'scale_factor':scale,'roof_retention_validated':False,'child_use_approved':False}
    for name,obj in parts.items():
        s=obj.Shape; b=s.optimalBoundingBox()
        report['physical_parts'][name]={'object':obj.Name,'valid':s.isValid(),'closed':s.isClosed(),'solid_count':len(s.Solids),'volume_mm3':s.Volume,'bounds_mm':[b.XMin,b.YMin,b.ZMin,b.XMax,b.YMax,b.ZMax]}
        export_mesh(s,ROOT/'exports'/('school-bus-v03-'+name+'-assembled.stl'))
    for name,(obj,colour) in colours.items():
        export_mesh(obj.Shape,ROOT/'exports'/('school-bus-v03-'+name+'.stl'))
        h.add_hex_color(obj,colour)
    step_parts=[]
    for i,obj in enumerate(parts.values()):
        f=doc.addObject('Part::Feature','StepShape'+str(i));f.Shape=obj.Shape;step_parts.append(f)
    Part.export(step_parts,str(ROOT/'exports'/'school-bus-v03-assembly.step'))
    for f in step_parts: doc.removeObject(f.Name)
    notes=doc.addObject('App::DocumentObjectGroup','AssemblyNotes')
    for prop,value in [('Purpose','Reference-led rounded bus, fixed wheels, three large physical parts'),('Fit','Mini locating guides approximately 2 mm wall, 3 mm height and 0.30 mm side clearance; retention not tested'),('Age','Under 3 years is a goal; untested prototype is not approved for child use')]:
        notes.addProperty('App::PropertyString',prop,'Design');setattr(notes,prop,value)
    h.set_final_visibility(doc,[obj for obj,_ in colours.values()]);doc.recompute()
    doc.saveAs(str(ROOT/'cad'/'nekomo-school-bus-v03.FCStd'))
    (ROOT/'evidence'/'geometry-report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report),flush=True)


main()
