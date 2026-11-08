"""生成三张实验图：消融、难度自适应、训练分布。"""
import json
from datetime import datetime
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from scripts.sim_users import EXPECTED_LEVEL, MODELS, run_simulation

plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei"]
plt.rcParams["axes.unicode_minus"] = False

ROOT = Path(__file__).resolve().parent.parent
FIGS_DIR = ROOT / "data" / "figs"
EVAL_PATH = ROOT / "data" / "eval_result.json"
RESULT_PATH = ROOT / "data" / "experiment_result.json"

COLORS = {"strong": "tab:blue", "normal": "tab:green", "weak": "tab:red"}


def _load_eval() -> dict:
    return json.loads(EVAL_PATH.read_text(encoding="utf-8"))


def _save(fig, name: str) -> None:
    FIGS_DIR.mkdir(parents=True, exist_ok=True)
    for ext in ("png", "svg"):
        fig.savefig(FIGS_DIR / f"{name}.{ext}", dpi=300, bbox_inches="tight")
    plt.close(fig)


def fig1_ablation(eval_data: dict):
    groups = list(eval_data["results"].keys())
    x = range(len(groups))
    width = 0.25
    all_vals = [eval_data["results"][g]["recall_at_3"] for g in groups]
    hard_vals = [eval_data["results_hard"][g]["recall_at_3"] for g in groups]
    time_vals = [eval_data["results_time"][g]["recall_at_3"] for g in groups]

    fig, ax = plt.subplots(figsize=(9, 5))
    ax.bar([i - width for i in x], all_vals, width, label="全部 query")
    ax.bar(list(x), hard_vals, width, label="--hard 子集")
    ax.bar([i + width for i in x], time_vals, width, label="--time 子集")
    ax.set_xticks(list(x))
    ax.set_xticklabels(groups)
    ax.set_ylabel("Recall@3")
    ax.set_ylim(0, 1.05)
    ax.set_title("消融实验 Recall@3")
    ax.legend()
    ax.text(
        0.01,
        -0.16,
        "数据来源：data/eval_result.json（36 条人工标注），评测脚本 scripts/eval_recall.py",
        transform=ax.transAxes,
        fontsize=8,
    )
    return fig


def fig2_adaptive(sim: dict):
    fig, ax = plt.subplots(figsize=(9, 5))
    for name in MODELS:
        ax.plot(
            range(1, len(sim["trajectories"][name]) + 1),
            sim["trajectories"][name],
            marker="o",
            label=name,
            color=COLORS[name],
        )
        ax.axhline(EXPECTED_LEVEL[name], linestyle="--", color=COLORS[name], alpha=0.45)
    ax.set_xlabel("局数")
    ax.set_ylabel("难度档位")
    ax.set_yticks([1, 2, 3])
    ax.set_ylim(0.5, 3.5)
    ax.set_title("难度自适应收敛曲线（模拟用户）")
    ax.legend(title="模型（虚线为期望档位）")
    return fig


def fig3_training(sim: dict):
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    names = list(MODELS.keys())

    means, stds = [], []
    for name in names:
        last5 = sim["accuracies"][name][-5:]
        means.append(np.mean(last5))
        stds.append(np.std(last5))
    ax = axes[0]
    ax.bar(names, means, yerr=stds, capsize=6, color=[COLORS[n] for n in names])
    ax.set_ylabel("正确率")
    ax.set_ylim(0, 1.05)
    ax.set_title("最后 5 局正确率")

    ax2 = axes[1]
    levels = [1, 2, 3]
    width = 0.22
    for j, name in enumerate(names):
        counts = [sim["trajectories"][name].count(l) for l in levels]
        ax2.bar([i + j * width for i in range(3)], counts, width, label=name, color=COLORS[name])
    ax2.set_xticks([i + width for i in range(3)])
    ax2.set_xticklabels(["档位 1", "档位 2", "档位 3"])
    ax2.set_ylabel("局数")
    ax2.set_title("难度档位分布")
    ax2.legend()

    fig.suptitle("模拟训练结果分布")
    fig.tight_layout()
    return fig


def main() -> None:
    eval_data = _load_eval()
    sim = run_simulation()

    _save(fig1_ablation(eval_data), "fig1_ablation")
    _save(fig2_adaptive(sim), "fig2_adaptive")
    _save(fig3_training(sim), "fig3_training")

    figures = [
        "data/figs/fig1_ablation.png",
        "data/figs/fig2_adaptive.png",
        "data/figs/fig3_training.png",
    ]
    payload = {
        "simulation": {
            "seed": sim["seed"],
            "models": sim["models"],
            "convergence": sim["convergence"],
        },
        "figures": figures,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    RESULT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print("图 1 标题：消融实验 Recall@3")
    print("图 2 标题：难度自适应收敛曲线（模拟用户）")
    print("图 3 标题：模拟训练结果分布")
    for rel in figures:
        print(str(ROOT / rel))


if __name__ == "__main__":
    main()
