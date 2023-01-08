import os
import subprocess
from math import radians

import bpy
from mathutils import Euler


def generate_gif(input_ply_path: str):
    bpy.ops.object.select_all(action="DESELECT")
    for obj in bpy.data.objects:
        obj.select_set(obj.type == "MESH")

    # call the operator once
    bpy.ops.object.delete()

    # importing the ply file with color
    bpy.ops.import_mesh.ply(filepath=input_ply_path)

    object_list = bpy.data.objects
    meshes = []
    for obj in object_list:
        if obj.type == "MESH":
            meshes.append(obj)

    for _object in meshes:
        if _object.type == "MESH":
            bpy.context.view_layer.objects.active = _object
            _object.select_set(True)
            mat = bpy.data.materials.new("material_1")
            _object.active_material = mat
            mat.use_nodes = True
            nodes = mat.node_tree.nodes
            mat_links = mat.node_tree.links
            bsdf = nodes.get("Principled BSDF")
            assert bsdf  # make sure it exists to continue
            vcol = nodes.new(type="ShaderNodeVertexColor")
            # vcol.layer_name = "VColor" # the vertex color layer name
            vcol.layer_name = "Col"
            mat_links.new(vcol.outputs["Color"], bsdf.inputs["Base Color"])
        elif _object.type == "CAMERA":
            _object.data.clip_end = 1000000
            _object.data.clip_start = 0.01
            _object.select_set(False)
        else:
            _object.select_set(False)

    bpy.ops.wm.save_as_mainfile(filepath=f"{os.getcwd()}/scene.blend")

    scene = bpy.context.scene
    scene.render.image_settings.file_format = "PNG"  # set output format to .png

    frames = range(1, 20)
    x_rotation = radians(0)
    y_rotation = radians(0)
    z_rotation = radians(0)

    for frame_nr in frames:
        scene.frame_set(frame_nr)

        context = bpy.context
        scene = context.scene
        _object = context.view_layer.objects.active  # the newly added cylinder.
        _object.name = "tree"
        _object.rotation_euler = Euler((x_rotation, y_rotation, z_rotation), "XYZ")
        scene.render.filepath = f"frame_{frame_nr:04d}.png"
        bpy.ops.render.render(write_still=True)
        z_rotation = z_rotation + radians(20)

    subprocess.run(
        f'gm convert -delay 20 -loop 0 "*.png" "output.gif"',
        shell=True,
        check=True,
    )


if __name__ == "__main__":
    generate_gif("mesh.ply")
