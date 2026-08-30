import collections
import dataclasses
import json
import logging
import math
import pathlib
import re
import traceback
from typing import Optional

import imageio
from libero.libero.envs import OffScreenRenderEnv
import numpy as np
from openpi_client import image_tools
from openpi_client import websocket_client_policy as _websocket_client_policy
import tqdm
import tyro

LIBERO_DUMMY_ACTION = [0.0] * 6 + [-1.0]
LIBERO_ENV_RESOLUTION = 256


@dataclasses.dataclass
class Args:
    host: str = "0.0.0.0"
    port: int = 8000
    resize_size: int = 224
    replan_steps: int = 5
    task_dir: str = "temporal"
    num_steps_wait: int = 10
    num_trials_per_task: int = 50
    max_steps: int = 400
    video_out_path: str = "data/libero_temporal/videos"
    failure_out_path: Optional[str] = None
    seed: int = 7
    memory_level: int = 1


def extract_language(bddl_path: pathlib.Path) -> str:
    text = bddl_path.read_text()
    m = re.search(r"\(:language\s+(.+?)\)", text)
    return m.group(1).strip() if m else bddl_path.parent.name.replace("_", " ")


def eval_goal(env, goal):
    if isinstance(goal, dict):
        if "and" in goal:
            return all(eval_goal(env, g) for g in goal["and"])
        if "or" in goal:
            return any(eval_goal(env, g) for g in goal["or"])
    return env.env._eval_predicate(goal)


def load_task_meta(task_path: pathlib.Path, memory_level: int) -> Optional[dict]:
    meta_file = task_path / "task_config.meta.json"
    if not meta_file.exists():
        return None
    data = json.loads(meta_file.read_text())
    if "subtask_goals" not in data:
        return None
    return {
        "subtask_goals": data["subtask_goals"],
        "operating_types": [ops[memory_level] for ops in data["operating_type"]],
    }


def eval_subtasks(env, subtask_goals: list) -> list[bool]:
    return [eval_goal(env, goal) for goal in subtask_goals]


def compute_operation_rates(records: list[dict]) -> dict[int, tuple[int, int]]:
    stats = collections.defaultdict(lambda: [0, 0])
    for r in records:
        stats[r["op_type"]][1] += 1
        if r["completed"]:
            stats[r["op_type"]][0] += 1
    return dict(stats)


def collect_positive_binary_goals(goal) -> list[list]:
    if isinstance(goal, dict):
        if "and" in goal:
            return sum((collect_positive_binary_goals(g) for g in goal["and"]), [])
        if "or" in goal:
            return sum((collect_positive_binary_goals(g) for g in goal["or"]), [])
        if "not" in goal:
            return []
    if isinstance(goal, list):
        if (
            len(goal) == 3
            and isinstance(goal[0], str)
            and goal[0].lower() in {"on", "in"}
        ):
            return [goal]
        return sum((collect_positive_binary_goals(g) for g in goal), [])
    return []


def entity_siblings(env, entity_name: str) -> list[str]:
    parsed_problem = env.env.parsed_problem
    for key in ["objects", "fixtures"]:
        for names in parsed_problem.get(key, {}).values():
            if entity_name in names:
                return [name for name in names if name != entity_name]
    regions = parsed_problem.get("regions", {})
    if entity_name in regions and entity_name.endswith("_region"):
        prefix = entity_name.rsplit("_", 2)[0]
        return [
            name for name in regions if name != entity_name and name.startswith(prefix)
        ]
    return []


def has_reference_drift(env, goal) -> bool:
    for predicate, object_name, target_name in collect_positive_binary_goals(goal):
        for sibling in entity_siblings(env, object_name):
            if eval_goal(env, [predicate, sibling, target_name]):
                return True
        for sibling in entity_siblings(env, target_name):
            if eval_goal(env, [predicate, object_name, sibling]):
                return True
    return False


def classify_failure(
    env,
    task_type: str,
    task_success: bool,
    subtask_goals: list,
    operating_types: list[int],
    completions: list[bool],
) -> Optional[dict]:
    if task_success:
        return None
    reference_drift = task_type == "object" and has_reference_drift(env, subtask_goals)
    if all(completions):
        if reference_drift:
            return {"mode": "reference_drift", "first_failed_idx": None, "op_type": None}
        return {"mode": "execution_failure", "first_failed_idx": None, "op_type": None}

    first_failed_idx = completions.index(False)
    op_type = operating_types[first_failed_idx]
    if reference_drift:
        mode = "reference_drift"
    else:
        mode = {
            0: "storage_failure",
            1: "stale_memory",
            2: "compression_collapse",
        }.get(op_type, f"operation_{op_type}_failure")
    return {"mode": mode, "first_failed_idx": first_failed_idx, "op_type": op_type}


def summarize_failure_modes(records: list[dict]) -> dict[str, int]:
    return dict(collections.Counter(r["mode"] for r in records))


def log_failure_summary(records: list[dict]) -> None:
    if not records:
        logging.info("Failure mode taxonomy: no failed episodes with checkpoint metadata")
        return

    mode_names = {
        "storage_failure": "Storage failure",
        "stale_memory": "Stale memory",
        "compression_collapse": "Compression collapse",
        "reference_drift": "Reference drift",
        "execution_failure": "Execution failure",
    }
    counts = summarize_failure_modes(records)
    total = len(records)
    logging.info("Failure mode taxonomy:")
    for mode in mode_names:
        count = counts.get(mode, 0)
        logging.info(f"  {mode_names[mode]}: {count}/{total} ({count / total * 100:.1f}%)")


def write_failure_summary(records: list[dict], out_path: Optional[str]) -> None:
    if out_path is None:
        return
    payload = {
        "counts": summarize_failure_modes(records),
        "records": records,
    }
    pathlib.Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    pathlib.Path(out_path).write_text(json.dumps(payload, indent=2))


def eval_temporal(args: Args) -> None:
    np.random.seed(args.seed)

    task_dir = pathlib.Path(args.task_dir)
    tasks = sorted([d for d in task_dir.iterdir() if d.is_dir()])
    logging.info(f"Found {len(tasks)} temporal tasks in {task_dir}")

    pathlib.Path(args.video_out_path).mkdir(parents=True, exist_ok=True)

    client = _websocket_client_policy.WebsocketClientPolicy(args.host, args.port)

    total_episodes, total_successes = 0, 0
    subtask_records = []
    failure_records = []
    for task_path in tqdm.tqdm(tasks, desc="Tasks"):
        bddl_file = task_path / "task_config.bddl"
        meta = load_task_meta(task_path, args.memory_level)
        task_description = extract_language(bddl_file)
        logging.info(f"Task: {task_description} ({task_path.name})")

        task_episodes, task_successes = 0, 0
        for episode_idx in tqdm.tqdm(
            range(args.num_trials_per_task), desc="Episodes", leave=False
        ):
            env_args = {
                "bddl_file_name": str(bddl_file),
                "camera_heights": LIBERO_ENV_RESOLUTION,
                "camera_widths": LIBERO_ENV_RESOLUTION,
            }
            env = OffScreenRenderEnv(**env_args)
            env.seed(args.seed + episode_idx)
            obs = env.reset()
            action_plan = collections.deque()

            t = 0
            replay_images = []
            replay_wrist_images = []
            task_success = False
            episode_finished = False
            subtask_completions = [False] * len(meta["subtask_goals"]) if meta else None

            while t < args.max_steps + args.num_steps_wait:
                try:
                    if t < args.num_steps_wait:
                        obs, reward, task_success, info = env.step(LIBERO_DUMMY_ACTION)
                        t += 1
                        continue

                    img = np.ascontiguousarray(obs["agentview_image"][::-1])
                    wrist_img = np.ascontiguousarray(
                        obs["robot0_eye_in_hand_image"][::-1]
                    )
                    img = image_tools.convert_to_uint8(
                        image_tools.resize_with_pad(
                            img, args.resize_size, args.resize_size
                        )
                    )
                    wrist_img = image_tools.convert_to_uint8(
                        image_tools.resize_with_pad(
                            wrist_img, args.resize_size, args.resize_size
                        )
                    )
                    replay_images.append(img)
                    replay_wrist_images.append(wrist_img)

                    if not action_plan:
                        element = {
                            "observation/image": img,
                            "observation/wrist_image": wrist_img,
                            "observation/state": np.concatenate((
                                obs["robot0_eef_pos"],
                                _quat2axisangle(obs["robot0_eef_quat"]),
                                obs["robot0_gripper_qpos"],
                            )),
                            "prompt": task_description,
                        }
                        action_chunk = client.infer(element)["actions"]
                        action_plan.extend(action_chunk[: args.replan_steps])

                    action = action_plan.popleft()
                    obs, reward, task_success, info = env.step(action.tolist())

                    if subtask_completions is not None:
                        for i, g in enumerate(meta["subtask_goals"]):
                            if not subtask_completions[i] and eval_goal(env, g):
                                subtask_completions[i] = True
                        episode_finished = all(subtask_completions)

                    if task_success:
                        task_successes += 1
                        total_successes += 1
                        break
                    if episode_finished:
                        break
                    t += 1
                except Exception as e:
                    logging.error(
                        f"Caught exception: {type(e).__name__}: {e}\n{traceback.format_exc()}"
                    )
                    break

            if meta:
                completions = subtask_completions
                logging.info(f"  subtasks: {completions}")
                for op_type, completed in zip(meta["operating_types"], completions):
                    subtask_records.append({"op_type": op_type, "completed": completed})
                failure = classify_failure(
                    env,
                    task_path.parent.name,
                    task_success,
                    meta["subtask_goals"],
                    meta["operating_types"],
                    completions,
                )
                if failure:
                    failure_record = {
                        "task_type": task_path.parent.name,
                        "task": task_path.name,
                        "episode": episode_idx,
                        **failure,
                    }
                    failure_records.append(failure_record)
                    logging.info(
                        f"  failure_mode: {failure_record['mode']} "
                        f"(first_failed_idx={failure_record['first_failed_idx']}, op_type={failure_record['op_type']})"
                    )

            task_episodes += 1
            total_episodes += 1
            env.close()

            suffix = "success" if task_success else "failure"
            task_segment = task_description.replace(" ", "_")[:80]
            video_dir = pathlib.Path(args.video_out_path)
            imageio.mimwrite(
                video_dir / f"rollout_{task_segment}_ep{episode_idx}_{suffix}.mp4",
                [np.asarray(x) for x in replay_images],
                fps=10,
                codec="libx264",
            )
            imageio.mimwrite(
                video_dir
                / f"rollout_{task_segment}_ep{episode_idx}_{suffix}_wrist.mp4",
                [np.asarray(x) for x in replay_wrist_images],
                fps=10,
                codec="libx264",
            )

            logging.info(
                f"Episode {episode_idx}: {'success' if task_success else 'failure'} | "
                f"total: {total_successes}/{total_episodes} ({total_successes / total_episodes * 100:.1f}%)"
            )

        logging.info(
            f"Task [{task_path.name}] success rate: {task_successes}/{task_episodes}"
        )

    logging.info(
        f"Total success rate: {total_successes}/{total_episodes} ({total_successes / total_episodes * 100:.1f}%)"
    )

    if subtask_records:
        rates = compute_operation_rates(subtask_records)
        op_names = {0: "memory_save", 1: "memory_update", 2: "memory_compress"}
        for op_type in sorted(rates):
            completed, total = rates[op_type]
            logging.info(
                f"{op_names.get(op_type, f'type_{op_type}')}: {completed}/{total} ({completed / total * 100:.1f}%)"
            )
    log_failure_summary(failure_records)
    write_failure_summary(failure_records, args.failure_out_path)


def _quat2axisangle(quat):
    if quat[3] > 1.0:
        quat[3] = 1.0
    elif quat[3] < -1.0:
        quat[3] = -1.0
    den = np.sqrt(1.0 - quat[3] * quat[3])
    if math.isclose(den, 0.0):
        return np.zeros(3)
    return (quat[:3] * 2.0 * math.acos(quat[3])) / den


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    tyro.cli(eval_temporal)
