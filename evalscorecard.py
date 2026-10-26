"""evalscorecard —— 把评测结果压成一张能对比的记分卡。

设计原则：
1. **总分不动，不代表模型没变**。总分把涨和跌抵消掉了，所以必须保留指标级明细。
2. **离散度要一起看**。均值一样的两个模型，稳定性可能差很多。
3. **回归项排在最前**。哪个指标掉了，比掉了多少更重要。

仅依赖 Python 标准库。

用法:
    python evalscorecard.py --help
    python evalscorecard.py --current run2.json --baseline run1.json
    python evalscorecard.py --current run2.json --json
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
import sys

# ---------------------------------------------------------------------------
# 输入格式
# ---------------------------------------------------------------------------

# 期望的输入格式（两种都接受）：
#   1. 扁平：{"metric_name": 0.8, "other": 0.5}
#   2. 带样本：{"metric_name": [0.8, 0.9, 0.7]}
#   3. 嵌套：{"metric_name": {"scores": [0.8, 0.9], "higher_is_better": true}}


def _norm_metric(name: str, value) -> dict:
    """把各种输入形态归一成 {"scores": [...], "higher_is_better": bool}。"""
    higher = True
    scores: list[float] = []

    if isinstance(value, dict):
        higher = bool(value.get("higher_is_better", True))
        raw = value.get("scores", value.get("values"))
        if raw is None:
            # 形如 {"mean": 0.8, "count": 10}
            if "mean" in value:
                scores = [float(value["mean"])] * max(1, int(value.get("count", 1)))
            else:
                scores = []
        elif isinstance(raw, (int, float)):
            scores = [float(raw)]
        else:
            scores = [float(x) for x in raw]
    elif isinstance(value, (int, float)):
        scores = [float(value)]
    elif isinstance(value, (list, tuple)):
        scores = [float(x) for x in value]
    else:
        scores = []

    return {"scores": scores, "higher_is_better": higher}


def load_run(path: str) -> dict[str, dict]:
    """读入一次评测结果。"""
    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        raise ValueError(f"读不了 {path}：{e}") from e

    if not isinstance(raw, dict):
        raise ValueError(f"{path} 应该是一个以指标名为键的 JSON 对象")

    out: dict[str, dict] = {}
    for name, value in raw.items():
        out[name] = _norm_metric(name, value)
    return out


# ---------------------------------------------------------------------------
# 统计
# ---------------------------------------------------------------------------

def summarize(metric: dict) -> dict:
    """一个指标的统计摘要。"""
    scores = metric["scores"]
    if not scores:
        return {"count": 0, "mean": None, "std": None, "min": None,
                "max": None, "higher_is_better": metric["higher_is_better"]}
    mean = statistics.fmean(scores)
    std = statistics.stdev(scores) if len(scores) > 1 else 0.0
    return {
        "count": len(scores),
        "mean": round(mean, 6),
        "std": round(std, 6),
        "min": round(min(scores), 6),
        "max": round(max(scores), 6),
        "higher_is_better": metric["higher_is_better"],
    }


def compare(current: dict[str, dict], baseline: dict[str, dict] | None,
            tolerance: float) -> dict:
    """两轮结果对比，产出记分卡。"""
    # 兼容原始输入：这里再归一化一次，方便直接喂 JSON 解析结果
    current = {k: (_norm_metric(k, v) if not isinstance(v, dict)
                   or "scores" not in v else v)
               for k, v in (current or {}).items()}
    if baseline:
        baseline = {k: (_norm_metric(k, v) if not isinstance(v, dict)
                        or "scores" not in v else v)
                    for k, v in baseline.items()}

    names = sorted(set(current) | set(baseline or {}))
    rows: list[dict] = []

    for name in names:
        cur = current.get(name)
        base = baseline.get(name) if baseline else None
        cur_sum = summarize(cur) if cur else None
        base_sum = summarize(base) if base else None

        delta = None
        direction = "unknown"
        if cur_sum and base_sum and cur_sum["mean"] is not None and base_sum["mean"] is not None:
            delta = round(cur_sum["mean"] - base_sum["mean"], 6)
            higher = cur_sum["higher_is_better"]
            if abs(delta) <= tolerance:
                direction = "flat"
            elif (delta > 0) == higher:
                direction = "up"
            else:
                direction = "down"

        rows.append({
            "metric": name,
            "current": cur_sum,
            "baseline": base_sum,
            "delta": delta,
            "direction": direction,
            "new_metric": base is None,
            "missing_metric": cur is None,
        })

    # 回归项排最前
    def sort_key(r: dict):
        order = {"down": 0, "up": 1, "flat": 2, "unknown": 3}
        return (order.get(r["direction"], 3), r["metric"])

    rows.sort(key=sort_key)

    regressions = [r for r in rows if r["direction"] == "down"]
    improvements = [r for r in rows if r["direction"] == "up"]
    flat = [r for r in rows if r["direction"] == "flat"]

    # 总分：按「越高越好」统一方向后取加权平均
    def overall(run: dict[str, dict]) -> float | None:
        vals = []
        for m in run.values():
            s = summarize(m)
            if s["mean"] is None:
                continue
            vals.append(s["mean"] if s["higher_is_better"] else 1.0 - s["mean"])
        return round(statistics.fmean(vals), 6) if vals else None

    cur_overall = overall(current)
    base_overall = overall(baseline) if baseline else None

    return {
        "rows": rows,
        "regressions": regressions,
        "improvements": improvements,
        "flat": flat,
        "overall": {
            "current": cur_overall,
            "baseline": base_overall,
            "delta": (round(cur_overall - base_overall, 6)
                       if cur_overall is not None and base_overall is not None else None),
        },
        "summary": {
            "metric_count": len(rows),
            "regression_count": len(regressions),
            "improvement_count": len(improvements),
            "flat_count": len(flat),
        },
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def render(card: dict) -> str:
    out: list[str] = []
    s = card["summary"]
    o = card["overall"]
    out.append("评测记分卡")
    out.append("=" * 52)
    if o["current"] is not None:
        base = f"  基线 {o['baseline']:.4f}" if o["baseline"] is not None else ""
        delta = f"  Δ {o['delta']:+.4f}" if o["delta"] is not None else ""
        out.append(f"总分（方向已统一）{o['current']:.4f}{base}{delta}")
    out.append(f"指标 {s['metric_count']} 个 ｜ 回退 {s['regression_count']} ｜ "
               f"进步 {s['improvement_count']} ｜ 持平 {s['flat_count']}")
    out.append("")

    for r in card["rows"]:
        mark = {"down": "▼", "up": "▲", "flat": "＝", "unknown": "?"}.get(r["direction"], "?")
        cur = r["current"]
        base = r["baseline"]
        if cur and cur["mean"] is not None:
            mean_s = f"{cur['mean']:.4f}"
            std_s = f"±{cur['std']:.4f}" if cur["std"] is not None else ""
            n_s = f"n={cur['count']}"
        else:
            mean_s, std_s, n_s = "—", "", ""
        if base and base["mean"] is not None:
            base_s = f"{base['mean']:.4f}"
        else:
            base_s = "—"
        delta_s = f"{r['delta']:+.4f}" if r["delta"] is not None else "—"
        out.append(f"{mark} {r['metric']:<24} 现 {mean_s} {std_s} {n_s:<8} "
                   f"基 {base_s:<10} Δ {delta_s}")

    out.append("")
    if card["regressions"]:
        out.append("回归项（优先处理）：")
        for r in card["regressions"]:
            out.append(f"  · {r['metric']}  Δ {r['delta']:+.4f}")
        out.append("")
    if card["improvements"]:
        out.append("进步项：")
        for r in card["improvements"]:
            out.append(f"  · {r['metric']}  Δ {r['delta']:+.4f}")
        out.append("")
    if not card["regressions"] and card["flat"]:
        out.append("没有指标回退。总分没动，但分布可能变了——记得看离散度。")
    return "\n".join(out).rstrip()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="evalscorecard",
        description="把评测结果压成一张能对比的记分卡（仅依赖标准库）",
        epilog=(
            "输入格式（都接受）：\n"
            "  {\"accuracy\": 0.82}\n"
            "  {\"accuracy\": [0.8, 0.9, 0.75]}\n"
            "  {\"accuracy\": {\"scores\": [0.8, 0.9], \"higher_is_better\": true}}\n"
            "  python evalscorecard.py --current run2.json --baseline run1.json\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("--current", required=True, help="本轮结果 JSON")
    ap.add_argument("--baseline", help="基线结果 JSON")
    ap.add_argument("--tolerance", type=float, default=1e-9,
                    help="判定「持平」的绝对差阈值")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    args = ap.parse_args(argv)

    try:
        current = load_run(args.current)
        baseline = load_run(args.baseline) if args.baseline else None
    except ValueError as e:
        print(str(e), file=sys.stderr)
        return 2

    if not current:
        print("本轮结果里没有指标。", file=sys.stderr)
        return 2

    card = compare(current, baseline, args.tolerance)

    if args.json:
        print(json.dumps(card, ensure_ascii=False, indent=2))
        return 0

    print(render(card))
    # 有回退项时退出码 1，方便卡 CI
    return 1 if card["regressions"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
