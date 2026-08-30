import json
import os
from pathlib import Path
import xml.etree.ElementTree as ET

ASSETS = Path("src/third_party/LIBERO/libero/libero/assets")
OUTPUT = Path(".scrapy/objects.json")


def get_xml_bbox(xml_path):
    if not xml_path.exists():
        return None
    tree = ET.parse(xml_path)
    root = tree.getroot()
    max_vol = 0
    best = None
    for geom in root.iter("geom"):
        if geom.get("type") == "box" and geom.get("size"):
            sizes = [float(x) for x in geom.get("size").split()]
            vol = sizes[0] * sizes[1] * sizes[2]
            if vol > max_vol:
                max_vol = vol
                best = [round(s * 2, 4) for s in sizes]
    return best


HOPE_OBJECTS = {
    "alphabet_soup": {"display_name": "Alphabet Soup Can", "category": "food_container", "material": "metal_can"},
    "bbq_sauce": {"display_name": "BBQ Sauce Bottle", "category": "food_container", "material": "plastic_bottle"},
    "butter": {"display_name": "Butter Box", "category": "food_container", "material": "cardboard"},
    "cherries": {"display_name": "Canned Cherries", "category": "food_container", "material": "metal_can"},
    "chocolate_pudding": {"display_name": "Chocolate Pudding Box", "category": "food_container", "material": "cardboard"},
    "cookies": {"display_name": "Cookies Box", "category": "food_container", "material": "cardboard"},
    "corn": {"display_name": "Canned Corn", "category": "food_container", "material": "metal_can"},
    "cream_cheese": {"display_name": "Cream Cheese Box", "category": "food_container", "material": "cardboard"},
    "ketchup": {"display_name": "Ketchup Bottle", "category": "food_container", "material": "plastic_bottle"},
    "macaroni_and_cheese": {"display_name": "Macaroni and Cheese Box", "category": "food_container", "material": "cardboard"},
    "mayo": {"display_name": "Mayonnaise Jar", "category": "food_container", "material": "plastic_jar"},
    "milk": {"display_name": "Milk Carton", "category": "food_container", "material": "cardboard"},
    "new_salad_dressing": {"display_name": "New Salad Dressing Bottle", "category": "food_container", "material": "plastic_bottle"},
    "orange_juice": {"display_name": "Orange Juice Carton", "category": "food_container", "material": "cardboard"},
    "popcorn": {"display_name": "Popcorn Box", "category": "food_container", "material": "cardboard"},
    "salad_dressing": {"display_name": "Salad Dressing Bottle", "category": "food_container", "material": "plastic_bottle"},
    "tomato_sauce": {"display_name": "Tomato Sauce Can", "category": "food_container", "material": "metal_can"},
}

GOOGLE_SCANNED = {
    "simple_rack": {"display_name": "Simple Rack", "category": "furniture", "material": "metal"},
    "white_bowl": {"display_name": "White Bowl", "category": "kitchenware", "material": "ceramic"},
    "akita_black_bowl": {"display_name": "Akita Black Bowl", "category": "kitchenware", "material": "ceramic"},
    "plate": {"display_name": "Plate", "category": "kitchenware", "material": "ceramic"},
    "basket": {"display_name": "Basket", "category": "container", "material": "wicker_or_plastic"},
    "chefmate_8_frypan": {"display_name": 'Chefmate 8" Frypan', "category": "kitchenware", "material": "metal_nonstick"},
    "glazed_rim_porcelain_ramekin": {"display_name": "Glazed Rim Porcelain Ramekin", "category": "kitchenware", "material": "porcelain"},
    "red_bowl": {"display_name": "Red Bowl", "category": "kitchenware", "material": "ceramic"},
}

ARTICULATED = {
    "microwave": {"display_name": "Microwave Oven", "category": "appliance", "material": "metal_plastic", "articulation_type": "revolute_door"},
    "slide_cabinet": {"display_name": "Slide Cabinet", "category": "furniture", "material": "wood_or_metal", "articulation_type": "prismatic"},
    "window": {"display_name": "Window", "category": "furniture", "material": "metal_glass", "articulation_type": "revolute"},
    "faucet": {"display_name": "Faucet", "category": "fixture", "material": "metal", "articulation_type": "revolute"},
    "basin_faucet": {"display_name": "Basin Faucet", "category": "fixture", "material": "metal", "articulation_type": "revolute"},
    "short_cabinet": {"display_name": "Short Cabinet", "category": "furniture", "material": "wood", "articulation_type": "prismatic"},
    "short_fridge": {"display_name": "Short Fridge", "category": "appliance", "material": "metal_plastic", "articulation_type": "revolute_door"},
    "wooden_cabinet": {"display_name": "Wooden Cabinet", "category": "furniture", "material": "wood", "articulation_type": "revolute_door"},
    "white_cabinet": {"display_name": "White Cabinet", "category": "furniture", "material": "wood_painted", "articulation_type": "revolute_door"},
    "flat_stove": {"display_name": "Flat Stove", "category": "appliance", "material": "metal_glass", "articulation_type": "revolute_knob"},
}

TURBOSQUID = {
    "wooden_tray": {"display_name": "Wooden Tray", "category": "container", "material": "wood"},
    "white_storage_box": {"display_name": "White Storage Box", "category": "container", "material": "cardboard_or_plastic"},
    "wooden_shelf": {"display_name": "Wooden Shelf", "category": "furniture", "material": "wood"},
    "wooden_two_layer_shelf": {"display_name": "Wooden Two-Layer Shelf", "category": "furniture", "material": "wood"},
    "wine_rack": {"display_name": "Wine Rack", "category": "furniture", "material": "metal_or_wood"},
    "wine_bottle": {"display_name": "Wine Bottle", "category": "drinkware", "material": "glass"},
    "dining_set_group": {"display_name": "Dining Set Group", "category": "furniture", "material": "wood"},
    "bowl_drainer": {"display_name": "Bowl Drainer", "category": "kitchenware", "material": "metal"},
    "moka_pot": {"display_name": "Moka Pot", "category": "kitchenware", "material": "aluminum"},
    "black_book": {"display_name": "Black Book", "category": "stationery", "material": "paper_cardboard"},
    "yellow_book": {"display_name": "Yellow Book", "category": "stationery", "material": "paper_cardboard"},
    "red_coffee_mug": {"display_name": "Red Coffee Mug", "category": "drinkware", "material": "ceramic"},
    "desk_caddy": {"display_name": "Desk Caddy", "category": "stationery", "material": "metal_or_plastic"},
    "porcelain_mug": {"display_name": "Porcelain Mug", "category": "drinkware", "material": "porcelain"},
    "white_yellow_mug": {"display_name": "White Yellow Mug", "category": "drinkware", "material": "ceramic"},
}


def build_hope_objects():
    results = []
    for obj_name, meta in HOPE_OBJECTS.items():
        xml_path = ASSETS / "stable_hope_objects" / obj_name / f"{obj_name}.xml"
        bbox = get_xml_bbox(xml_path) if xml_path.exists() else None
        entry = {
            "id": obj_name,
            "display_name": meta["display_name"],
            "source": "HOPE",
            "category": meta["category"],
            "material": meta["material"],
            "bbox_size_m": bbox,
            "bbox_size_cm": [round(x * 100, 2) for x in bbox] if bbox else None,
        }
        results.append(entry)
    return results


def build_google_scanned_objects():
    results = []
    for obj_name, meta in GOOGLE_SCANNED.items():
        xml_path = ASSETS / "stable_scanned_objects" / obj_name / f"{obj_name}.xml"
        bbox = get_xml_bbox(xml_path) if xml_path.exists() else None
        entry = {
            "id": obj_name,
            "display_name": meta["display_name"],
            "source": "GoogleScanned",
            "category": meta["category"],
            "material": meta["material"],
            "bbox_size_m": bbox,
            "bbox_size_cm": [round(x * 100, 2) for x in bbox] if bbox else None,
        }
        results.append(entry)
    return results


def build_articulated_objects():
    results = []
    for obj_name, meta in ARTICULATED.items():
        xml_path = ASSETS / "articulated_objects" / f"{obj_name}.xml"
        bbox = get_xml_bbox(xml_path) if xml_path.exists() else None
        entry = {
            "id": obj_name,
            "display_name": meta["display_name"],
            "source": "Articulated",
            "category": meta["category"],
            "material": meta["material"],
            "articulation_type": meta.get("articulation_type"),
            "bbox_size_m": bbox,
            "bbox_size_cm": [round(x * 100, 2) for x in bbox] if bbox else None,
        }
        results.append(entry)
    return results


def build_turbosquid_objects():
    results = []
    for obj_name, meta in TURBOSQUID.items():
        xml_path = ASSETS / "turbosquid_objects" / obj_name / f"{obj_name}.xml"
        bbox = get_xml_bbox(xml_path) if xml_path.exists() else None
        entry = {
            "id": obj_name,
            "display_name": meta["display_name"],
            "source": "TurboSquid",
            "category": meta["category"],
            "material": meta["material"],
            "bbox_size_m": bbox,
            "bbox_size_cm": [round(x * 100, 2) for x in bbox] if bbox else None,
        }
        results.append(entry)
    return results


def build_new_objects():
    results = []
    new_obj_dir = ASSETS / "new_objects"
    for category_dir in sorted(new_obj_dir.iterdir()):
        if not category_dir.is_dir():
            continue
        category = category_dir.name
        for model_dir in sorted(category_dir.iterdir()):
            if not model_dir.is_dir():
                continue
            model_id = model_dir.name
            metadata_path = model_dir / "misc" / "metadata.json"
            bbox = None
            if metadata_path.exists():
                with open(metadata_path) as f:
                    meta = json.load(f)
                bbox = [round(x, 4) for x in meta.get("bbox_size", [])]
            entry = {
                "id": f"{category}/{model_id}",
                "display_name": category,
                "source": "NewObjects_GoogleScanned",
                "category": category,
                "model_id": model_id,
                "bbox_size_m": bbox or None,
                "bbox_size_cm": [round(x * 100, 2) for x in bbox] if bbox else None,
            }
            results.append(entry)
    return results


def main():
    all_objects = []
    all_objects.extend(build_hope_objects())
    all_objects.extend(build_google_scanned_objects())
    all_objects.extend(build_articulated_objects())
    all_objects.extend(build_turbosquid_objects())
    all_objects.extend(build_new_objects())

    output = {
        "total": len(all_objects),
        "sources": {
            "HOPE": len([o for o in all_objects if o["source"] == "HOPE"]),
            "GoogleScanned": len([o for o in all_objects if o["source"] == "GoogleScanned"]),
            "Articulated": len([o for o in all_objects if o["source"] == "Articulated"]),
            "TurboSquid": len([o for o in all_objects if o["source"] == "TurboSquid"]),
            "NewObjects_GoogleScanned": len([o for o in all_objects if o["source"] == "NewObjects_GoogleScanned"]),
        },
        "objects": all_objects,
    }

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"总计 {len(all_objects)} 个物体 → {OUTPUT}")


if __name__ == "__main__":
    main()
