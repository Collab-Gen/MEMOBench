import argparse
import json
import os
import sys
import h5py
import numpy as np
from copy import deepcopy
from tqdm import tqdm

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from libero.libero.envs import TASK_MAPPING

def check_subtask(env, goal_dict):
    base_env = env.env if hasattr(env, "env") else env
    if "and" in goal_dict:
        for pred in goal_dict["and"]:
            try:
                if not base_env._eval_predicate(pred):
                    return False
            except Exception:
                return False
        return True
    return False

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=str, required=True)
    parser.add_argument("--bddl-file", type=str, required=True)
    parser.add_argument("--template", type=str, required=True)
    parser.add_argument("--output", type=str, default="")
    args = parser.parse_args()

    in_hdf5_path = args.dataset
    out_hdf5_path = args.output if args.output else in_hdf5_path.replace(".hdf5", "_packed.hdf5")

    with open(args.template, "r", encoding="utf-8") as f:
        meta_template = json.load(f)

    f_in = h5py.File(in_hdf5_path, "r")
    f_out = h5py.File(out_hdf5_path, "w")

    data_group_in = f_in["data"]
    data_group_out = f_out.create_group("data")

    for key, val in data_group_in.attrs.items():
        data_group_out.attrs[key] = val

    with open(args.bddl_file, "r", encoding="utf-8") as f:
        bddl_content = f.read()
    data_group_out.attrs["bddl_file_name"] = args.bddl_file
    data_group_out.attrs["bddl_file_content"] = bddl_content

    env_info = json.loads(data_group_in.attrs["env_info"])
    problem_info = json.loads(data_group_in.attrs["problem_info"])

    env = TASK_MAPPING[problem_info["problem_name"]](
        bddl_file_name=args.bddl_file,
        **env_info,
        has_renderer=False,
        has_offscreen_renderer=True,
        render_camera="agentview",
        use_camera_obs=False,
    )

    demos = [key for key in data_group_in.keys() if key.startswith("demo_")]
    demos.sort(key=lambda x: int(x.split("_")[1]))

    for ep in tqdm(demos, desc="Packing"):
        ep_group_in = data_group_in[ep]
        states = ep_group_in["states"][()]
        actions = ep_group_in["actions"][()]
        num_samples = len(states)

        model_xml = ep_group_in.attrs["model_file"]
        if isinstance(model_xml, bytes): 
            model_xml = model_xml.decode("utf-8")

        env.reset()
        env.reset_from_xml_string(model_xml)

        agentview_imgs = []
        wristview_imgs = []

        current_meta = deepcopy(meta_template)
        goals = current_meta["subtask_goals"]
        current_stage = 0

        for i in range(num_samples):
            env.sim.set_state_from_flattened(states[i])
            env.sim.forward()

            img_static = env.sim.render(camera_name="agentview", height=256, width=256)[::-1]
            img_wrist = env.sim.render(camera_name="robot0_eye_in_hand", height=256, width=256)[::-1]

            agentview_imgs.append(img_static)
            wristview_imgs.append(img_wrist)

            if current_stage < len(goals):
                if check_subtask(env, goals[current_stage]):
                    current_meta["key_frame"][current_stage] = i
                    current_stage += 1

        ep_group_out = data_group_out.create_group(ep)
        ep_group_out.create_dataset("states", data=states)
        ep_group_out.create_dataset("actions", data=actions)

        obs_group = ep_group_out.create_group("obs")
        obs_group.create_dataset("agentview_image", data=np.array(agentview_imgs, dtype=np.uint8))
        obs_group.create_dataset("robot0_eye_in_hand_image", data=np.array(wristview_imgs, dtype=np.uint8))

        ep_group_out.attrs["num_samples"] = num_samples
        ep_group_out.attrs["model_file"] = model_xml
        ep_group_out.attrs["meta_data"] = json.dumps(current_meta)

    f_in.close()
    f_out.close()

if __name__ == "__main__":
    main()
