# GlobalMapper — Reading Notes

**Paper:** He, L. & Aliaga, D. *GlobalMapper: Arbitrary-Shaped Urban Layout Generation.* ICCV 2023.
**PDF:** [He_GlobalMapper_Arbitrary-Shaped_Urban_Layout_Generation_ICCV_2023_paper.pdf](He_GlobalMapper_Arbitrary-Shaped_Urban_Layout_Generation_ICCV_2023_paper.pdf)
**Code:** https://github.com/Arking1995/GlobalMapper
**arXiv:** https://arxiv.org/abs/2307.09693

---

## The big idea in 3 sentences

GlobalMapper takes an arbitrary-shaped city block (a polygon bounded by roads) and fills it with buildings that look like the city it learned from. The novelty isn't the neural network — it's a geometric trick that lets one network handle blocks of any shape: skeletonize the block, lay a stubby grid graph along the skeleton, then learn building placements in that normalized coordinate frame. Trained on 119,236 blocks / 2.5M buildings / 28 North American cities from OpenStreetMap.

## Architecture (Figure 2)

```
   Block polygon ──► 64×64 binary mask k + scale l
                              │
                              ▼
                  CNN autoencoder (4 conv layers)
                              │
                              ▼
                     block-shape latent m
                              │
                              │  (used as condition)
                              ▼
   Real layout G  ──► Canonical Spatial Transform (CST)  ──► canonical G'
                              │
                              ▼
                   Graph Attention Network (T passes)
                              │
                              ▼
                [aggregate F¹...Fᵀ → 512-dim normal]
                              │
                              ▼
                      sample z (variational)
                              │
                              ▼
              [z concat m] ──► MLP decoder ──► predicted G'
                              │
                              ▼
                   Inverse CST ──► final building layout
```

At inference: skip the encoder, sample z, condition on a new block mask, decode, inverse-transform. **5.81 ms per block** on a single A5000.

## The trick: Canonical Spatial Transform (CST)

**Problem:** every block has a different polygon shape; a fixed-size network can't directly handle arbitrary input.

**Solution:**
1. Take block's binary mask, compute its 2D skeleton (medial axis).
2. Extend skeleton endpoints to touch the block boundary → main axis polyline.
3. Define minor axes perpendicular to each main-axis segment.
4. Each building's position stored as `(distance_along_main_axis, distance_along_minor_axis)`, normalized by axis lengths.
5. Building width/height also normalized.

Result: any block, no matter how curved or irregular, has the same stubby grid graph topology (≤120 nodes, handles >99% of real blocks).

## Per-node features (each building)

- `eᵢ` — exists? (binary)
- `xᵢ, yᵢ` — center position (normalized in canonical frame)
- `wᵢ, hᵢ` — oriented bbox width/height (normalized)
- `sᵢ` — shape type (integer: Rectangular, L-shape, U-shape, X-shape)
- `aᵢ` — occupancy ratio = building area / bbox area

The 4 parameterized shapes fit real buildings with **IoU 95.78% / Hausdorff 1.36 m**. Fit found via Powell optimization in preprocessing.

## Training details

- Loss = L2 on geometry + cross-entropy on categorical + KL on z
- Loss weights: geometry **4.0**, categorical **1.0**, KL **0.5**
- They tried an explicit "no-overlap" loss (BlockPlanner-style) — **it did not help**; GAT learns non-overlap from data.
- GAT depth T = 3 (deeper = better, plateaus).
- lr = 0.001, ~10⁵ iterations, 9 hours on one A5000 GPU.
- 80/20 train/val split.

## Numbers worth quoting (Table 1; 1000 generated vs 1000 real)

| Method | L-Sim ↑ | Overlap % ↓ | Out-Block % ↓ | FID ↓ |
|---|---|---|---|---|
| LayoutVAE | 4.49 | 33.39 | 11.15 | 94.54 |
| BlockPlanner | 14.92 | 9.46 | 2.24 | 39.27 |
| Gupta et al. | 17.59 | 3.61 | 7.58 | 47.06 |
| VTN | 17.65 | 1.49 | 7.97 | 46.71 |
| **GlobalMapper** | **22.45** | **1.42** | **0.89** | **14.94** |

**User study (2AFC, 50 valid responses):** 97% prefer over LayoutVAE, 87% over BlockPlanner, 88% over VTN.

## Bonus: sparse-prior generation

Given a road network + only 5% of block layouts as priors → generate the rest of the city. New block's latent = distance-weighted average of its k=5 nearest priors + Gaussian noise. Demonstrated on Chicago including 3D heights.

---

## What translates to PowerPlan AI

| GlobalMapper concept | PowerPlan AI analogue |
|---|---|
| City block polygon | Fenced plot boundary (currently a × b rectangle) |
| Stubby grid graph (≤120 nodes) | 12 groups + future expansion as graph nodes |
| Per-node features (e, x, y, w, h, s, a) | Groups already have type/position/dims |
| Block-shape CNN encoder | Reusable as-is for irregular site shapes |
| GAT message passing | Replaces hand-coded rule evaluation with learned relations |
| CVAE training objective | What to train on (layout, score) pairs from existing engine |
| 4 parametric shape types | Extend the same way (you have rectangles + polylines) |
| 5.81 ms inference | Fast enough to drop into Streamlit slider loop |

## What doesn't translate

- They have 120,000 training blocks. PowerPlan AI has 0 validated power-plant layouts at training scale. **This is the blocker.** Options: transfer learning, or synthetic data from the existing engine.
- Their buildings are homogeneous. Cooling Tower ≠ Admin Building. Need typed nodes + many more examples per type.
- They have no hard engineering rules. Power plants have dozens of setbacks/clearances. Implication: use GlobalMapper as the **proposal generator**, `Rules.py` as the **validator** (same pattern as GenFusion #3).

## Reading guide

1. Fig. 2 + Fig. 3 (pp. 2–3) — architecture diagram. 10 min.
2. §3.1 Graph Representation (p. 3) — node feature list.
3. §3.2 Canonical Spatial Transform (pp. 3–4) — the skeleton trick. Most reusable single idea.
4. Table 1 + Table 2 (pp. 5, 6) — metrics and ablations.
5. §4.4 Controllable Map Generation (p. 6) — sparse-prior generation (the path forward given limited training data).

Skip: §4.3 ablation details, §4.2 competitor reimplementation notes, Supplemental.

## Open questions for PowerPlan AI

- Can the existing `Core/` engine generate enough synthetic (layout, score) pairs to bootstrap training? (Need ~10⁴ at minimum.)
- Should the CST be replaced by a simpler fixed grid given the rectangular plot, or kept for future irregular sites?
- How to encode hard rules (min_distance, boundary_setback, etc.) — as post-hoc validation only, or as loss terms during training?
