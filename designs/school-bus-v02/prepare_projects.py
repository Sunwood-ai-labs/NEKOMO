import json
from pathlib import Path
import xml.etree.ElementTree as ET
import zipfile

ROOT=Path(__file__).resolve().parent
NS={'m':'http://schemas.microsoft.com/3dmanufacturing/core/2015/02'}
ET.register_namespace('',NS['m'])


def prepare(part, colors):
    n=len(colors)+1
    tower_y = '130' if part == 'body' else '140'
    support=n-1
    matrix=[]
    for source in range(n):
        for target in range(n):
            matrix.append('0' if source==target else '800' if source==support else '500' if target==support else '350')
    settings={'filament_colour':colors+['#FFFFFF'],'filament_type':['PLA']*(n-1)+['PLA-S'],'filament_is_support':['0']*(n-1)+['1'],'flush_volumes_matrix':matrix,'flush_multiplier':'1','wipe_tower_x':['15'],'wipe_tower_y':[tower_y]}
    src=ROOT/'print'/(part+'-project.3mf')
    dst=ROOT/'print'/(part+'-placed.3mf')
    with zipfile.ZipFile(src) as zin,zipfile.ZipFile(dst,'w',zipfile.ZIP_DEFLATED) as zout:
        for name in zin.namelist():
            if name=='Metadata/project_settings.config':
                continue
            data=zin.read(name)
            if name=='3D/3dmodel.model':
                xml=ET.fromstring(data)
                for item in xml.find('m:build',NS):
                    transform=[float(v) for v in item.get('transform','1 0 0 0 1 0 0 0 1 0 0 0').split()]
                    transform[10]-=30
                    item.set('transform',' '.join(str(v) for v in transform))
                data=ET.tostring(xml,encoding='utf-8',xml_declaration=True)
            zout.writestr(name,data)
        zout.writestr('Metadata/project_settings.config',json.dumps(settings))
    profile={'type':'process','name':'NEKOMO v02 '+part+' 0.20 supported','inherits':'0.20mm Standard @BBL A1M','from':'user','instantiation':'true','compatible_printers':['Bambu Lab A1 mini 0.4 nozzle'],'layer_height':'0.2','initial_layer_print_height':'0.2','wall_loops':'5','sparse_infill_density':'25%','sparse_infill_pattern':'gyroid','top_shell_layers':'6','bottom_shell_layers':'5','outer_wall_speed':'50','inner_wall_speed':'100','bridge_speed':'25','enable_support':'1','support_type':'tree(auto)','support_on_build_plate_only':'0','support_threshold_angle':'30','support_filament':'1','support_interface_filament':str(n),'support_interface_top_layers':'3','support_interface_bottom_layers':'2','support_interface_spacing':'0','support_top_z_distance':'0','support_bottom_z_distance':'0.2','support_interface_pattern':'concentric','independent_support_layer_height':'0','brim_width':'3','wipe_tower_x':['15'],'wipe_tower_y':[tower_y],'flush_into_infill':'0','flush_into_objects':'0','flush_into_support':'0','flush_volumes_matrix':matrix,'flush_multiplier':'1'}
    (ROOT/'print'/('profile-'+part+'.json')).write_text(json.dumps(profile,indent=2),encoding='utf-8')
    return {'part':part,'model_filaments':n-1,'support_interface_filament':n,'project':str(dst)}


if __name__=='__main__':
    print(json.dumps([prepare('body',['#E6B34A','#76503B','#F4E2BB']),prepare('chassis',['#76503B','#F4E2BB']),prepare('roof',['#76503B'])]))
