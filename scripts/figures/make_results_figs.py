"""The manuscript's result figures from the deposited result tables (no agent, no data download).

  python scripts/figures/make_results_figs.py [out_dir]   (default $DERIVED_DIR/figures)

fig_sweep_domains.pdf   the sweep, credited rungs by domain, realized and AI failure (results/final/run8.md)
fig_agents.pdf          outcomes per model on the sweep building (results/final/run3.md)
fig_diagnosis.pdf       diagnosis outcomes per scenario, without and with the separating stream (pair A run4s20.md,
                        pair B run4s20_premise.md)
fig_real_plane.pdf      real buildings in the answerable x actuation plane (results/census/census_v2.json)
fig_real_streams.pdf    stream classes linked (and declared) by the real KGs, by the sweep profile that adds them
"""
import json, math, re, sys
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from bara import DERIVED_DIR, canon  # noqa: E402
FIG = Path(sys.argv[1]) if len(sys.argv) > 1 else DERIVED_DIR / "figures"
FIG.mkdir(parents=True, exist_ok=True)
plt.rcParams.update({"font.size": 9, "font.family": "serif", "axes.spines.top": False, "axes.spines.right": False})

RUN8 = (ROOT / "results/final/run8.md").read_text(encoding="utf-8")
DOMAIN_RUNGS = {}
for (d, _i), r in canon.CANONS["v2"].rungs.items():
    DOMAIN_RUNGS[d] = DOMAIN_RUNGS.get(d, 0) + len(r)


def wilson(k, n, z=1.96):
    if n == 0:
        return 0.0, 0.0
    p = k / n; den = 1 + z * z / n
    c = (p + z * z / (2 * n)) / den; h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return max(0.0, c - h), min(1.0, c + h)


# ── the sweep (run8.md: final1_* and final8_*), stacked by domain (Figure 7) ─────────────────────
total = int(re.search(r"\| minimal \| \d+/(\d+) \|", RUN8).group(1))      # the canon total of the run
PROFS = [("minimal", "minimal"), ("comfort", "comfort"), ("standard", "standard"), ("rich", "metered\n(= rich)")]
DOM = [("thermal", "#D7301F"), ("occupancy", "#8C6BB1"), ("lighting", "#E6AB02"), ("equipment", "#1B9E77"),
       ("energy", "#2C7BB6")]
per = []
for key, lab in PROFS:
    m = re.search(r"## %s: per-rung accuracy[^\n]*\n\n\|[^\n]*\n\|[^\n]*\n((?:\|[^\n]*\n)+)" % key, RUN8)
    agg = {}
    for line in m.group(1).splitlines():
        name, acc = [x.strip() for x in line.strip("|").split("|")]
        n, a = agg.get(name.split()[0], (0, 0.0)); agg[name.split()[0]] = (n + 1, a + float(acc))
    per.append((lab, agg))
fig, ax = plt.subplots(figsize=(5.6, 3.3))
for i, (lab, agg) in enumerate(per):
    y = 0.0
    for d, col in DOM:
        n, a = agg.get(d, (0, 0.0))
        if not n:
            continue
        ax.bar(i, a / total, bottom=y, color=col, width=0.62, edgecolor="white", lw=0.4); y += a / total
    fail = sum(n - a for n, a in agg.values()) / total
    ax.bar(i, fail, bottom=y, color="#7F0000", width=0.62); y += fail
    ax.text(i, y + 0.012, f"$F$ = {fail:.3f}", va="bottom", ha="center", fontsize=7.5, color="#7F0000")
    ax.bar(i, 1 - y, bottom=y, color="#E0E0E0", width=0.62)
    ax.text(i, 1.02, f"{sum(n for n, _ in agg.values())}/{total} rungs", ha="center", va="bottom", fontsize=8)
top = per[-1][1]
locked_l3 = sum(DOMAIN_RUNGS[d] - top[d][0] for d in top)
locked_aq = total - sum(n for n, _ in top.values()) - locked_l3
ax.annotate(f"never reached on this building:\nair quality ({locked_aq} rungs), L3 of\nthermal, equipment, energy ({locked_l3})",
            xy=(3, 0.83), xytext=(3.5, 0.83), fontsize=7.5, va="center", ha="left",
            arrowprops=dict(arrowstyle="-", lw=0.6, color="#555555"))
ax.set_xticks(range(len(per))); ax.set_xticklabels([l for l, _ in per])
ax.set_xlim(-0.5, 3.5); ax.set_ylim(0, 1.12); ax.set_ylabel("share of the canon total")
h = [Patch(color=col, label=d) for d, col in DOM]
h += [Patch(color="#7F0000", label="AI failure $F$"),
      Patch(color="#E0E0E0", label="data limitation")]
ax.legend(handles=h, loc="upper left", bbox_to_anchor=(1.0, 0.62), frameon=False, fontsize=7.5)
fig.tight_layout(); fig.savefig(FIG / "fig_sweep_domains.pdf", bbox_inches="tight"); plt.close(fig)

# ── comparison models (run3.md): outcomes per model (Figure 8) ─────────────────────────────────
NAMES = {"qwen3.8-27b-128k (reference)": "Qwen3.8 27B (reference)", "gemma4-31b-128k": "Gemma 4 31B",
         "qwen2.5-32b-32k": "Qwen2.5 32B", "llama3.1-8b-128k": "Llama 3.1 8B",
         "mistral-nemo-12b-128k": "Mistral NeMo 12B"}   # gemma2:9b is left out: no tool calling in Ollama
mods = []
for line in (ROOT / "results/final/run3.md").read_text(encoding="utf-8").splitlines():
    m = re.match(r"\| (\S[^|]*?) \| (\d+) \| ([\d.]+) \| (\d+) \| (\d+) \| (\d+) \| (\d+) \| (\d+) \|$", line)
    if m and m.group(1) in NAMES:
        n = int(m.group(2)); k = round(float(m.group(3)) * n)
        mods.append(dict(name=NAMES[m.group(1)], n=n, correct=k, wrong=int(m.group(4)) - k, abst=int(m.group(5)),
                         noans=int(m.group(6)), err=int(m.group(7))))
assert len(mods) == 5, mods
OUT = [("correct", "correct", "#1B9E77"), ("wrong", "wrong answer", "#E6AB02"), ("abst", "abstained", "#9E9E9E"),
       ("noans", "no answer (turn limit or stop)", "#8C6BB1"), ("err", "model-server error", "#404040")]
fig, ax = plt.subplots(figsize=(5.8, 2.4))
for i, r in enumerate(mods):
    x = 0
    for k, _, col in OUT:
        ax.barh(i, r[k], left=x, color=col, height=0.62); x += r[k]
    lo, hi = wilson(r["correct"], r["n"])
    ax.text(r["n"] + 1.5, i, f"{r['correct'] / r['n']:.2f} ({lo:.2f}–{hi:.2f})", va="center", fontsize=8)
ax.set_yticks(range(len(mods))); ax.set_yticklabels([r["name"] for r in mods], fontsize=8.5); ax.invert_yaxis()
ax.set_xlim(0, mods[0]["n"] + 22); ax.set_xlabel(f"episodes (of {mods[0]['n']})")
ax.text(mods[0]["n"] + 1.5, -0.8, "accuracy (95% interval)", fontsize=7.5, color="#555555", va="bottom")
ax.legend(handles=[Patch(color=c_, label=l) for _, l, c_ in OUT], loc="upper center", bbox_to_anchor=(0.45, -0.36),
          ncol=3, frameon=False, fontsize=7.5)
fig.tight_layout(); fig.savefig(FIG / "fig_agents.pdf", bbox_inches="tight"); plt.close(fig)

# ── paired diagnosis at 20 repeats (run4s20*.md): outcomes per scenario and condition (Figure 9) ─
SCEN = {"s1": "A: thermostat\noffset", "s1r": "A: schedule\nchange", "s3m": "B: sensor\ndrift", "s4": "B: internal-\nload step"}
diag = {}
for src, scen in (("run4s20.md", "s1r?"), ("run4s20_premise.md", "s3m|s4")):   # pair B with its premise stated
    for line in (ROOT / "results/final" / src).read_text(encoding="utf-8").splitlines():
        m = re.match(rf"\| ({scen}) \| (rung[01]) \| (\d+) \| (\d+)[^|]*\| (\d+)[^|]*\| (\d+)[^|]*\| (\d+)[^|]*\| (\d+) \|",
                     line)
        if m:
            diag[(m.group(1), m.group(2))] = dict(abst=int(m.group(4)), over=int(m.group(5)), correct=int(m.group(6)),
                                                 wrong=int(m.group(7)), noans=int(m.group(8)))
assert len(diag) == 8, diag
DOUT = [("correct", "true cause named", "#1B9E77"), ("wrong", "wrong cause named", "#E6AB02"),
        ("over", "overclaimed (a cause named without the stream)", "#D7301F"), ("abst", "abstained", "#9E9E9E"),
        ("noans", "no answer", "#8C6BB1")]
fig, ax = plt.subplots(figsize=(5.6, 3.0))
xs, labs = [], []
for j, (s, name) in enumerate(SCEN.items()):
    for c_, cond in enumerate(("rung0", "rung1")):
        x = j * 3.0 + c_ * 1.1; y = 0
        for k, _, col in DOUT:
            v = diag[(s, cond)][k]
            if v:
                ax.bar(x, v, bottom=y, color=col, width=0.9)
                if v >= 2:
                    ax.text(x, y + v / 2, str(v), ha="center", va="center", fontsize=7.5, color="white")
            y += v
        xs.append(x); labs.append("without" if cond == "rung0" else "with")
    ax.text(j * 3.0 + 0.55, -3.8, name, ha="center", va="top", fontsize=8)
ax.set_xticks(xs); ax.set_xticklabels(labs, fontsize=7.5)
ax.set_xlabel("")
ax.set_ylabel("episodes"); ax.set_ylim(0, 21); ax.set_yticks(range(0, 21, 5))
ax.legend(handles=[Patch(color=c_, label=l) for _, l, c_ in DOUT], loc="upper center", bbox_to_anchor=(0.5, -0.36),
          ncol=2, frameon=False, fontsize=7.5)
fig.tight_layout(); fig.savefig(FIG / "fig_diagnosis.pdf", bbox_inches="tight"); plt.close(fig)

# ── census: the plane ───────────────────────────────────────────────────────────────────────────
d = json.loads((ROOT / "results/census/census_v2.json").read_text(encoding="utf-8"))
pts = [r for r in d["rows"] if r["linked_points"] > 0]
fig, ax = plt.subplots(figsize=(5.2, 3.6))
for r in pts:
    if r["c_ans_declared"] > r["c_ans"] + 1e-9:
        ax.plot([r["c_ans"], r["c_ans_declared"]], [r["c_act"], r["c_act"]], color="#BDBDBD", lw=1, zorder=1)
        ax.plot(r["c_ans_declared"], r["c_act"], marker="o", mfc="white", mec="#7F7F7F", ms=4, lw=0, zorder=2)
mortar = [r for r in pts if r["source"] == "mortar"]; bts = [r for r in pts if r["source"] == "bts"]
ax.scatter([r["c_ans"] for r in mortar], [r["c_act"] for r in mortar], s=22, color="#2C7BB6", zorder=3, label="Mortar (36 buildings), linked data")
ax.scatter([r["c_ans"] for r in bts], [r["c_act"] for r in bts], s=40, marker="s", color="#D7191C", zorder=3, label="BTS Site B, linked data")
ax.plot([], [], marker="o", mfc="white", mec="#7F7F7F", ms=4, color="#BDBDBD", lw=1, label="declared by the graph")
ax.set_xlabel("answerable-readiness ceiling $C_\\mathrm{ans}(I)$"); ax.set_ylabel("actuation-readiness ceiling $C_\\mathrm{act}(I)$")
ax.set_xlim(-0.02, 1.0); ax.set_ylim(-0.03, 0.8)
ax.legend(loc="upper right", frameon=False, fontsize=8)
fig.tight_layout(); fig.savefig(FIG / "fig_real_plane.pdf"); plt.close(fig)
# ── census: which stream classes the real KGs link ──────────────────────────────────────────────────
cnt, dec = {}, {}
for r in pts:
    for st in r["streams"]:
        cnt[st] = cnt.get(st, 0) + 1
    for st in r["streams_declared"]:
        dec[st] = dec.get(st, 0) + 1
TIER = [("minimal or comfort", ["T", "Sp"], "#8C8C8C"), ("standard", ["Occ"], "#8C6BB1"),
        ("metered", ["Whole", "Sub", "Sub2", "Pwr", "Lgt", "OAT"], "#2C7BB6"),
        ("rich (Guideline 36 points)", ["SAT", "SpC", "ActC", "ActP", "Run", "Load", "CO2", "OAF"], "#D95F02")]
SHORT = {"T": "zone temperature", "Sp": "zone setpoint", "Occ": "occupancy", "Whole": "whole-building meter",
         "Sub": "one end-use submeter", "Sub2": "two end-use submeters", "Pwr": "equipment power",
         "Lgt": "lighting power", "OAT": "outside air temperature", "SAT": "supply air temperature",
         "SpC": "scheduled setpoint", "ActC": "terminal actuation command",
         "ActP": "terminal actuation response", "Run": "run status",
         "Load": "equipment load", "CO2": "zone CO$_2$", "OAF": "outdoor-air flow"}
labels, vals, decl, cols = [], [], [], []
for _, cls, col in TIER:
    for st in sorted(cls, key=lambda st: -cnt.get(st, 0)):
        labels.append(SHORT[st]); vals.append(cnt.get(st, 0)); decl.append(dec.get(st, 0)); cols.append(col)
fig, ax = plt.subplots(figsize=(5.6, 3.9))
yy = list(range(len(labels)))[::-1]
ax.barh(yy, decl, color="none", edgecolor=cols, linewidth=0.9, height=0.7)
ax.barh(yy, vals, color=cols, height=0.7)
for yi, v, d in zip(yy, vals, decl):
    ax.text(max(v, d) + 0.4, yi, str(v) if d == v else f"{v} ({d} declared)", va="center", fontsize=8)
ax.set_yticks(yy); ax.set_yticklabels(labels, fontsize=8)
ax.set_xlim(0, len(pts) + 2); ax.set_xlabel(f"real building KGs that link the stream class (of {len(pts)})")
ax.legend(handles=[Patch(color=col, label=f"first added at {t}") for t, _, col in TIER]
          + [Patch(facecolor="none", edgecolor="#555555", label="outline: declared in the KG")],
          loc="upper center", bbox_to_anchor=(0.4, -0.16), ncol=2, frameon=False, fontsize=7.5)
fig.tight_layout(); fig.savefig(FIG / "fig_real_streams.pdf", bbox_inches="tight"); plt.close(fig)

print("wrote fig_sweep_domains, fig_agents, fig_diagnosis, fig_real_plane, fig_real_streams in", FIG,
      "| plane points", len(pts))
