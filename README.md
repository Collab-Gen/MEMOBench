<h1 align="center">MEMOBench</h1>

<p align="center">
  <img src="assets/teaser.png" alt="MEMOBench benchmark suite overview" width="90%">
</p>

## Introduction

MEMOBench is a process-level memory benchmark for robotic manipulation. It annotates 30 history-dependent tasks with 4,200 executable checkpoints labeling three memory operations: Storage, Update, and Compression. Evaluations show leading VLA policies store information well but fail to update and compress it, reaching only 31.9% average success.

## Dataset & object assets

Both are available at [HuggingFace](https://huggingface.co/datasets/SunSeaLucky/MEMOBench).

## How to use

### 1. Set up the simulator

MEMOBench builds on [LIBERO](https://github.com/Lifelong-Robot-Learning/LIBERO), vendored under `src/third_party/LIBERO`:

```bash
git clone https://github.com/SunSeaLucky/MEMOBench.git
cd MEMOBench
pip install -e src/third_party/LIBERO
pip install imageio tyro tqdm numpy
```

Evaluation talks to the policy through the [openpi](https://github.com/Physical-Intelligence/openpi) websocket client, so also install `openpi_client` (from the openpi repository).

### 2. Download the data and assets

From [HuggingFace](https://huggingface.co/datasets/SunSeaLucky/MEMOBench):

```bash
hf download SunSeaLucky/MEMOBench MEMOBench.zip --repo-type dataset
hf download SunSeaLucky/MEMOBench assets.zip --repo-type dataset
unzip MEMOBench.zip   # -> MEMOBench/{object,procedural,spatial,temporal}/*.hdf5
```

Extract `assets.zip` and copy the extracted object/scene assets into the LIBERO assets directory `src/third_party/LIBERO/libero/libero/assets/`.

### 3. Serve your policy

Start a policy server exposing the openpi websocket API (default `0.0.0.0:8000`), e.g. with openpi's `scripts/serve_policy.py`. The client sends `observation/image`, `observation/wrist_image`, `observation/state`, and `prompt`, and expects an action chunk in return.

### 4. Run evaluation

The executable task configs (`task_config.bddl` + `task_config.meta.json` with checkpoint annotations) live under `src/bddl/`:

```bash
python src/eval.py \
    --task-dir src/bddl/temporal \
    --num-trials-per-task 50 \
    --memory-level 1 \
    --video-out-path data/libero_temporal/videos \
    --failure-out-path data/libero_temporal/failures.json
```

Key arguments: `--host` / `--port` (policy server), `--memory-level` (0–2, selects the memory operation labels), `--max-steps`, `--replan-steps`, `--seed`. The script reports overall success rate, per-operation rates (storage / update / compression), a failure-mode taxonomy (storage failure, stale memory, compression collapse, reference drift, execution failure), and saves rollout videos plus an optional failure summary JSON.

### Optional: inspect the object pool

```bash
python src/get_object_pool.py   # writes .scrapy/objects.json
```

## License

MEMOBench is licensed under [CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/) (see [LICENSE](LICENSE)): free for non-commercial scientific research with attribution; commercial use is not permitted. Third-party code under `src/third_party/` (e.g., LIBERO) remains under its own license (MIT).