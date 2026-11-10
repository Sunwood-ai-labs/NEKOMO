"""Inspect actual extruding G-code segments in the inverted bonnet region."""
import json, re, zipfile, math
from pathlib import Path
from collections import defaultdict, Counter
import numpy as np
ROOT=Path(__file__).resolve().parent

def read_segments(path):
    with zipfile.ZipFile(path) as z:
        text=z.read('Metadata/plate_1.gcode').decode()
    layers=defaultdict(list)
    pos={'X':0.,'Y':0.,'Z':0.,'E':0.}
    layer=-1;feature='';relative=True;relative_xyz=False;width=.42
    for line in text.splitlines():
        if line.startswith('; layer num/total_layer_count:'):
            layer=int(line.split(':',1)[1].split('/')[0])
        if line.startswith('; FEATURE:'): feature=line.split(':',1)[1].strip()
        if line.startswith('; LINE_WIDTH:'): width=float(line.split(':',1)[1])
        code=line.split(';')[0].strip()
        if code=='M83':relative=True
        if code=='M82':relative=False
        if code=='G91':relative_xyz=True
        if code=='G90':relative_xyz=False
        if code.startswith('G92 '):
            for key,value in re.findall(r'([XYZE])([-+\d.]+)',code):pos[key]=float(value)
            continue
        if not re.match(r'^G[0123]\s',code):continue
        args={k:float(v) for k,v in re.findall(r'([XYZEIJ])([-+\d.]+)',code)}
        old=pos.copy()
        for k in ['X','Y','Z']:
            if k in args:pos[k]=pos[k]+args[k] if relative_xyz else args[k]
        extrusion=args.get('E',0.) if relative else args.get('E',pos['E'])-pos['E']
        if 'E' in args:pos['E']=pos['E']+args['E'] if relative else args['E']
        length=math.hypot(pos['X']-old['X'],pos['Y']-old['Y'])
        if layer>=0 and extrusion>0 and length>.0001 and feature not in ['Prime tower','Custom']:
            if all(68<=p['X']<=112 and 78<=p['Y']<=102 for p in [old,pos]):
                points=[(old['X'],old['Y']),(pos['X'],pos['Y'])]
                if code.startswith(('G2 ','G3 ')) and ('I' in args or 'J' in args):
                    cx=old['X']+args.get('I',0);cy=old['Y']+args.get('J',0)
                    radius=math.hypot(old['X']-cx,old['Y']-cy)
                    start=math.atan2(old['Y']-cy,old['X']-cx)
                    end=math.atan2(pos['Y']-cy,pos['X']-cx)
                    sweep=(end-start)%(2*math.pi)
                    if code.startswith('G2 '):sweep=sweep-2*math.pi
                    count=max(2,int(abs(sweep)*radius/.08)+1)
                    points=[(cx+radius*math.cos(start+t*sweep),cy+radius*math.sin(start+t*sweep)) for t in np.linspace(0,1,count)]
                    points[0]=(old['X'],old['Y']);points[-1]=(pos['X'],pos['Y'])
                for a,b in zip(points,points[1:]):
                    layers[layer].append((*a,*b,width,feature,pos['Z']))
    return layers

def inspect(path):
    layers=read_segments(path)
    rows=[];features=Counter();unsupported=[]
    for layer,segs in sorted(layers.items()):
        previous=layers.get(layer-1,[])
        if not previous:continue
        a=np.array([(s[0],s[1]) for s in previous]);b=np.array([(s[2],s[3]) for s in previous]);ab=b-a
        den=np.sum(ab*ab,axis=1);pw=np.array([s[4] for s in previous])
        gaps=[];count=0
        for x0,y0,x1,y1,w,feature,z in segs:
            if not 10.2<=z<=19.0:continue
            n=max(2,int(math.hypot(x1-x0,y1-y0)/.15)+1)
            for t in np.linspace(0,1,n):
                x=x0+t*(x1-x0);y=y0+t*(y1-y0)
                # Central bonnet only; isolate it from tires, side windows and roof.
                if not (69.0<=x<=75.8 and 85<=y<=95):continue
                p=np.array([x,y]);u=np.clip(np.sum((p-a)*ab,axis=1)/np.maximum(den,1e-12),0,1)
                dist=np.linalg.norm(p-(a+u[:,None]*ab),axis=1)
                # Positive edge gap means no geometric bead overlap with previous layer.
                edge_gap=float(np.min(dist-(pw+w)/2))
                gaps.append(edge_gap);count+=1;features[feature]+=1
                if edge_gap>.03:unsupported.append([layer,round(z,3),round(x,4),round(y,4),round(edge_gap,4),feature])
        if gaps:rows.append(dict(layer=layer,z_mm=segs[0][6],samples=count,max_bead_edge_gap_mm=max(gaps)))
    return dict(artifact=str(path),region='x69..75.8 y85..95 z10.2..19.0 in placed G-code coordinates',
                method='sample extruding segments every <=0.15mm; compare to previous layer segments using their declared line widths; ideal planar bead footprint only',
                sampled_points=sum(r['samples'] for r in rows),feature_sample_counts=dict(features),
                samples_with_edge_gap_over_003mm=len(unsupported),worst_edge_gap_mm=max((r['max_bead_edge_gap_mm'] for r in rows),default=None),
                largest_gaps=sorted(unsupported,key=lambda x:x[4],reverse=True)[:12],layers=rows,
                limitations='Nominal footprint overlap does not prove cooling, adhesion, flow or surface finish. Bonnet central region only; other bus features excluded.')

results={
 'before':inspect(ROOT.parent/'school-bus-v08-photo/exports/fast-two-color-sliced.3mf'),
 'after':inspect(ROOT/'exports/sloped-two-color-sliced.3mf')}
(ROOT/'evidence/toolpath-overlap.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
for name,r in results.items():
    print(name,json.dumps({k:r[k] for k in ['sampled_points','samples_with_edge_gap_over_003mm','worst_edge_gap_mm','feature_sample_counts','largest_gaps']}))
