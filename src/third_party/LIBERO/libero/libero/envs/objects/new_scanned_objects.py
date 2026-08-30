import os
import pathlib
import xml.etree.ElementTree as ET

import numpy as np
from robosuite.models.objects import MujocoXMLObject
from robosuite.utils.mjcf_utils import array_to_string

from libero.libero.envs.base_object import OBJECTS_DICT

absolute_path = pathlib.Path(__file__).parent.parent.parent.absolute()
_NEW_OBJECTS_DIR = os.path.join(str(absolute_path), "assets", "new_objects")


def _bbox_from_visual_mesh(xml_path):
    _default = np.array([-0.05, -0.05, -0.05]), np.array([0.05, 0.05, 0.05])
    vis_dir = os.path.join(os.path.dirname(xml_path), "visuals")
    if not os.path.isdir(vis_dir):
        return _default
    obj_files = [f for f in os.listdir(vis_dir) if f.endswith(".obj")]
    if not obj_files:
        return _default
    verts = []
    for obj_file in obj_files:
        with open(os.path.join(vis_dir, obj_file)) as f:
            for line in f:
                if line.startswith("v "):
                    p = line.split()
                    verts.append((float(p[1]), float(p[2]), float(p[3])))
    if not verts:
        return _default
    arr = np.array(verts)
    return arr.min(axis=0), arr.max(axis=0)


def _add_bounding_sites(wrapper, xml_path):
    mn, mx = _bbox_from_visual_mesh(xml_path)
    h_radius = max(mx[0] - mn[0], mx[1] - mn[1]) / 2.0
    site_defaults = dict(rgba="0 0 0 0", size="0.005")
    for name, pos in [
        ("bottom_site", [0, 0, mn[2]]),
        ("top_site", [0, 0, mx[2]]),
        ("horizontal_radius_site", [h_radius, h_radius, 0]),
    ]:
        ET.SubElement(wrapper, "site", name=name, pos=array_to_string(pos), **site_defaults)


class _NewScannedObjectBase(MujocoXMLObject):
    _xml_source_path = None

    def _get_object_subtree(self):
        if self.worldbody.find("./body/body[@name='object']") is None:
            obj_body = self.worldbody.find("./body[@name='object']")
            if obj_body is not None:
                self.worldbody.remove(obj_body)
                wrapper = ET.SubElement(self.worldbody, "body")
                wrapper.append(obj_body)
                _add_bounding_sites(wrapper, self._xml_source_path)
        return super()._get_object_subtree()


def _make_new_object_class(xml_path, category, key):
    class NewScannedObject(_NewScannedObjectBase):
        _xml_source_path = xml_path

        def __init__(self, name=key, joints=[dict(type="free", damping="0.0005")]):
            super().__init__(
                xml_path,
                name=name,
                joints=joints,
                obj_type="all",
                duplicate_collision_geoms=False,
            )
            self.category_name = category
            self.rotation = (np.pi / 2, np.pi / 2)
            self.rotation_axis = "x"
            self.object_properties = {"vis_site_names": {}}

    return NewScannedObject


def _register_new_objects():
    if not os.path.isdir(_NEW_OBJECTS_DIR):
        return

    for category in sorted(os.listdir(_NEW_OBJECTS_DIR)):
        category_path = os.path.join(_NEW_OBJECTS_DIR, category)
        if not os.path.isdir(category_path):
            continue

        variants = sorted(
            d for d in os.listdir(category_path)
            if os.path.isdir(os.path.join(category_path, d))
        )

        if not variants:
            continue

        valid_xml = []
        for model_id in variants:
            xml_path = os.path.join(
                category_path, model_id, "usd", "MJCF", f"{model_id}.xml"
            )
            if os.path.isfile(xml_path):
                valid_xml.append(xml_path)

        if not valid_xml:
            continue

        if len(valid_xml) == 1:
            key = category
            if key not in OBJECTS_DICT:
                OBJECTS_DICT[key] = _make_new_object_class(valid_xml[0], category, key)
        else:
            for idx, xml_path in enumerate(valid_xml):
                key = f"{category}__{idx}"
                if key not in OBJECTS_DICT:
                    OBJECTS_DICT[key] = _make_new_object_class(xml_path, category, key)
            oob_key = f"{category}__{len(valid_xml)}"
            if oob_key not in OBJECTS_DICT:
                OBJECTS_DICT[oob_key] = _make_new_object_class(valid_xml[-1], category, oob_key)


_register_new_objects()
