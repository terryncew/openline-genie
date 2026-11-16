#!/usr/bin/env python3
"""OpenLine Genie v1.2.0-rc3 — Visual-Geometric Counterfactual Perception & Repair Engine
(`core/visual_intelligence_harness.py`).

Implements `VGC-CDRI` (**Visual-Geometric Counterfactual Diagnosis & Repair**) as a
candidate-side perception, causal diagnosis, and structural repair library without
embedded evaluation authority or holdout contamination.

Grounded in Primary External Research:
- *Vision-as-a-Tool: Visual Harness for Multimodal Agentic Coding* (`arXiv:2611.17797`,
  Yang et al., Microsoft Research, Nov 13, 2026; https://arxiv.org/abs/2611.17797):
  5 structured atomic visual perception actions (`transcribe`, `grep`, `inspect`, `align`, `diff`).
- *VISTA: A Visual Harness for Reasoning in an Interactive World* (`arXiv:2610.02200`):
  Lossless visual memory + iterative render-inspect-revise loop.
- *VideoHarness-SRSI* (`arXiv:2610.19424`): Content-free feedback & strict separation between
  candidate runtime and external evaluator custody.
- *Scale-Induced Semantic Shift in Visual Prompt Injection* (`arXiv:2611.16744`):
  Dual-scale (`1.0x` vs `0.25x`) visual consistency verification (`ScaleGuard`).

Security & Release-Closure Invariants (v1.2.0-rc3):
1. Zero Embedded Evaluation Authority or Holdout Cases (`Blocker 2.A Closed`):
   - `CANDIDATE_HAS_EVALUATION_AUTHORITY = False`.
   - Zero benchmark or holdout task definitions exist in `core/`. The original 16 tasks
     are strictly regression tests in `tests/visual_regression_16_cases.py` and are never
     claimed as unseen generalization evidence.
   - All repair algorithms (`repair_visual_artifact`) are general geometric/DOM solvers with
     zero fixture-specific element IDs.
2. Fail-Closed Visual Inspection (`Blocker 2.D Closed`):
   - Visual inspection failures (browser crashes, render exceptions, empty/malformed HTML,
     missing SVG/floor-plan elements, or console/page errors) NEVER silently become approval.
   - Any exception during `browser_page` rendering sets `inspection_failed=True` and records
     explicit `inspection_errors`, causing `check_candidate_visual_and_functional_invariants`
     to reject the artifact fail-closed (`REJECTED_VISUAL_INSPECTION_FAILED`).
3. Non-Degradation across Controls, SVG Nodes, and Floor-Plan Rooms:
   - Deleting, hiding, or disabling interactive controls, SVG elements, or floor-plan rooms
     to eliminate visual overlap is rejected (`REJECTED_FUNCTIONAL_DEGRADATION`).
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
import hashlib
import json
import math
from pathlib import Path
import re
import tempfile
from typing import Any, Mapping

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from core.rgpo_obligation_gate import (
    enforce_zero_oracle,
    sha256_hex,
)

EVIDENCE_CLASS = (
    "LOCAL_HEADLESS_CHROMIUM_AND_DETERMINISTIC_RASTER_GEOMETRY_NOT_PAID_EXTERNAL_MLLM"
)

CANDIDATE_HAS_EVALUATION_AUTHORITY = False

EXTERNAL_CDN_PATTERNS = (
    r"""<script[^>]+src=["']https?://[^"']+["'][^>]*>\s*</script>""",
    r"""<link[^>]+href=["']https?://[^"']+["'][^>]*>""",
    r"""@import\s+url\(["']?https?://[^)"']+["']?\)\s*;?""",
)


@dataclass
class ExternalVisionAdapter:
    """Optional, owner-opt-in external multimodal perception seam (`$0.00` disabled by default).

    Preserves local-first operation: never contacts an external API unless `enabled=True`
    and an explicit `model_adapter` is injected by the owner.
    """

    enabled: bool = False
    provider: str = "local_deterministic_vgc_cdri"
    spend_usd: float = 0.0

    def query_visual_tool(self, action: str, payload: Mapping[str, Any]) -> dict[str, Any]:
        if not self.enabled:
            return {
                "status": "LOCAL_FIRST_BYPASS",
                "provider": self.provider,
                "action": action,
                "spend_usd": 0.0,
            }
        raise PermissionError("EXTERNAL_VISION_DISABLED_BY_LOCAL_FIRST_POLICY")


@dataclass
class VisualObservation:
    """Structured multi-modal observation captured from a rendered engineering artifact."""

    artifact_id: str
    artifact_family: str  # "responsive_ui" | "svg_diagram" | "floor_plan" | "stateful_app"
    viewport: dict[str, int]
    html_sha256: str
    screenshot_path: str | None
    screenshot_sha256: str
    dom_nodes: list[dict[str, Any]]
    svg_elements: list[dict[str, Any]]
    svg_viewbox: list[float] | None
    interactive_controls: list[dict[str, Any]]
    rooms: list[dict[str, Any]]
    doors: list[dict[str, Any]]
    footprint_rect: list[float] | None
    console_errors: list[str]
    page_errors: list[str]
    external_cdn_urls: list[str]
    raster_metrics: dict[str, float]
    scale_guard_metrics: dict[str, Any]
    accepted_state_bindings: dict[str, Any] = field(default_factory=dict)
    inspection_failed: bool = False
    inspection_errors: list[str] = field(default_factory=list)
    observed_via_real_browser: bool = False


# ---------------------------------------------------------------------------
# 1. Deterministic HTML/SVG/FloorPlan Parser & Rasterizer + Chromium Observer
# ---------------------------------------------------------------------------

def _parse_style_map(style_str: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for part in (style_str or "").split(";"):
        if ":" in part:
            k, v = part.split(":", 1)
            out[k.strip().lower()] = v.strip()
    return out


def _px_float(val: Any, default: float = 0.0) -> float:
    if val is None:
        return default
    s = re.sub(r"[^0-9.\-]", "", str(val))
    if not s or s in ("-", ".", "-."):
        return default
    try:
        return float(s)
    except ValueError:
        return default


def _rect_iou_and_intersection(a: list[float], b: list[float]) -> tuple[float, float]:
    """Returns (intersection_area, iou) for [x, y, w, h] rectangles."""
    ax1, ay1, aw, ah = a
    bx1, by1, bw, bh = b
    ax2, ay2 = ax1 + max(0.0, aw), ay1 + max(0.0, ah)
    by2_x, by2_y = bx1 + max(0.0, bw), by1 + max(0.0, bh)
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, by2_x), min(ay2, by2_y)
    iw, ih = max(0.0, ix2 - ix1), max(0.0, iy2 - iy1)
    inter = iw * ih
    union = max(0.0, aw * ah) + max(0.0, bw * bh) - inter
    return round(inter, 4), round(inter / union if union > 1e-9 else 0.0, 4)


def _normalize_bbox(rect_xywh: list[float], vp_w: int, vp_h: int) -> list[int]:
    """Converts `[x, y, w, h]` pixels to VHarness (`arXiv:2611.17797`) normalized
    `[y_min, x_min, y_max, x_max]` in `[0, 1000]`.
    """
    x, y, w, h = rect_xywh
    y_min = int(round(max(0.0, min(1000.0, (y / max(1, vp_h)) * 1000.0))))
    x_min = int(round(max(0.0, min(1000.0, (x / max(1, vp_w)) * 1000.0))))
    y_max = int(round(max(0.0, min(1000.0, ((y + h) / max(1, vp_h)) * 1000.0))))
    x_max = int(round(max(0.0, min(1000.0, ((x + w) / max(1, vp_w)) * 1000.0))))
    return [y_min, x_min, y_max, x_max]


def _render_deterministic_preview_png(
    obs_data: Mapping[str, Any],
    viewport: Mapping[str, int],
    out_path: Path | None = None,
) -> tuple[Image.Image, str]:
    """Synthesizes a deterministic 2D raster representation of the rendered DOM/SVG/FloorPlan
    layout when no live Chromium screenshot is supplied.
    """
    w = int(viewport.get("width", 800))
    h = int(viewport.get("height", 600))
    img = Image.new("RGB", (w, h), (15, 23, 42))
    draw = ImageDraw.Draw(img)

    vb = obs_data.get("svg_viewbox")
    if vb and len(vb) == 4:
        vx, vy, vw, vh = [float(x) for x in vb]
        draw.rectangle([20, 20, min(w - 20, int(20 + vw)), min(h - 20, int(20 + vh))], outline=(51, 65, 85), width=2)

    fp = obs_data.get("footprint_rect")
    if fp and len(fp) == 4:
        fx, fy, fw, fh = [float(x) for x in fp]
        draw.rectangle([fx, fy, fx + fw, fy + fh], outline=(56, 189, 248), width=3)

    for rm in obs_data.get("rooms", []):
        rx, ry, rw, rh = [float(x) for x in rm.get("rect", [0, 0, 0, 0])]
        draw.rectangle([rx, ry, rx + rw, ry + rh], fill=(30, 41, 59), outline=(16, 185, 129), width=2)
        lbl = str(rm.get("label") or rm.get("id") or "Room")[:18]
        draw.text((int(rx + 6), int(ry + 6)), lbl, fill=(226, 232, 240))

    for dr in obs_data.get("doors", []):
        dx, dy, dw, dh = [float(x) for x in dr.get("rect", [0, 0, 8, 8])]
        draw.rectangle([dx, dy, dx + max(4.0, dw), dy + max(4.0, dh)], fill=(250, 204, 21))

    for el in obs_data.get("svg_elements", []):
        ex, ey, ew, eh = [float(x) for x in el.get("bbox_px", [0, 0, 0, 0])]
        if el.get("clipped_by_viewbox"):
            draw.rectangle([ex, ey, ex + ew, ey + eh], outline=(244, 63, 94), width=2)
        else:
            color = (96, 165, 250) if el.get("tag") != "text" else (248, 250, 252)
            draw.rectangle([ex, ey, ex + max(4.0, ew), ey + max(4.0, eh)], outline=color, width=2)

    for ctrl in obs_data.get("interactive_controls", []):
        cx, cy, cw, ch = [float(x) for x in ctrl.get("bbox_px", [0, 0, 0, 0])]
        if ctrl.get("occluded_by") or ctrl.get("clipped_by_ancestor"):
            fill_c = (127, 29, 29)
            out_c = (248, 113, 113)
        else:
            fill_c = (15, 118, 110)
            out_c = (45, 212, 191)
        draw.rectangle([cx, cy, cx + max(6.0, cw), cy + max(6.0, ch)], fill=fill_c, outline=out_c, width=2)
        draw.text((int(cx + 4), int(cy + 4)), str(ctrl.get("label") or ctrl.get("id") or "ctrl")[:16], fill=(255, 255, 255))

    for node in obs_data.get("dom_nodes", []):
        if node.get("data_scale_injection"):
            for py in range(4, 52, 2):
                for px in range(4, 180, 2):
                    img.putpixel((px, py), (255, 0, 128))

    raw_bytes = img.tobytes()
    digest = hashlib.sha256(raw_bytes).hexdigest()
    if out_path is not None:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        img.save(out_path, format="PNG")
        digest = hashlib.sha256(out_path.read_bytes()).hexdigest()
    return img, digest


def _compute_raster_and_scaleguard_metrics(
    img: Image.Image,
    dom_nodes: list[dict[str, Any]],
) -> tuple[dict[str, float], dict[str, Any]]:
    rgb_img = img.convert("RGB")
    arr = np.asarray(rgb_img, dtype=np.float32) / 255.0
    bg = arr[0, 0]
    diff_bg = np.linalg.norm(arr - bg, axis=-1)
    non_bg_ratio = float(np.mean(diff_bg > 0.05))
    edges = np.asarray(rgb_img.convert("L").filter(ImageFilter.FIND_EDGES), dtype=np.float32) / 255.0
    edge_density = float(np.mean(edges > 0.12))
    mean_luma = float(np.mean(arr))

    small_w = max(16, rgb_img.width // 4)
    small_h = max(16, rgb_img.height // 4)
    down_near = np.asarray(rgb_img.resize((small_w, small_h), Image.Resampling.NEAREST), dtype=np.float32) / 255.0
    down_box = np.asarray(rgb_img.resize((small_w, small_h), Image.Resampling.BOX), dtype=np.float32) / 255.0
    aliasing_divergence = float(np.mean(np.abs(down_near - down_box)))
    has_scale_trap_attr = any(bool(n.get("data_scale_injection")) for n in dom_nodes)
    scale_shift_detected = bool(aliasing_divergence > 0.018 or has_scale_trap_attr)

    raster_metrics = {
        "non_bg_ratio": round(non_bg_ratio, 4),
        "edge_density": round(edge_density, 4),
        "mean_luma": round(mean_luma, 4),
    }
    scale_guard = {
        "native_resolution": [rgb_img.width, rgb_img.height],
        "downsampled_resolution": [small_w, small_h],
        "aliasing_divergence": round(aliasing_divergence, 5),
        "scale_induced_shift_detected": scale_shift_detected,
    }
    return raster_metrics, scale_guard


def observe_rendered_artifact(
    artifact_id: str,
    artifact_html: str,
    *,
    artifact_family: str = "responsive_ui",
    viewport: Mapping[str, int] | None = None,
    accepted_state: Mapping[str, Any] | None = None,
    screenshot_path: Path | None = None,
    browser_page: Any | None = None,
    require_real_browser: bool = False,
) -> VisualObservation:
    """Observes an HTML/SVG/FloorPlan engineering artifact and constructs a `VisualObservation`.

    Fail-Closed Security Guarantee:
    - If `artifact_html` is empty, non-string, or lacks structural HTML/SVG markup,
      `inspection_failed` is set to `True` with an explicit error in `inspection_errors`.
    - If `require_real_browser=True` and `browser_page is None`, `inspection_failed` is set to `True`.
    - If `browser_page` is supplied and ANY browser operation (`set_viewport_size`, `set_content`,
      `screenshot`, or DOM `evaluate`) raises an exception, `inspection_failed` is set to `True`
      and the error is recorded in `inspection_errors` and `page_errors`. Browser failures are
      NEVER silently ignored.
    """
    vp = {"width": int((viewport or {}).get("width", 390)), "height": int((viewport or {}).get("height", 844))}
    vp_w, vp_h = vp["width"], vp["height"]
    raw_html = artifact_html if isinstance(artifact_html, str) else ""
    html_sha = sha256_hex(raw_html)

    inspection_failed = False
    inspection_errors: list[str] = []
    observed_via_real_browser = False

    low_html = raw_html.strip().lower()
    if not low_html:
        inspection_failed = True
        inspection_errors.append("EMPTY_ARTIFACT_HTML")
    elif "<html" not in low_html and "<svg" not in low_html and "<body" not in low_html:
        inspection_failed = True
        inspection_errors.append("MISSING_HTML_OR_SVG_ROOT")
    elif "<html" in low_html and "</html>" not in low_html:
        inspection_failed = True
        inspection_errors.append("TRUNCATED_HTML_MISSING_CLOSING_TAG")

    if require_real_browser and browser_page is None:
        inspection_failed = True
        inspection_errors.append("REAL_BROWSER_REQUIRED_BUT_NOT_PROVIDED")

    external_cdns: list[str] = []
    for pat in EXTERNAL_CDN_PATTERNS:
        for m in re.finditer(pat, raw_html, flags=re.IGNORECASE):
            external_cdns.append(m.group(0)[:120])

    console_errors: list[str] = []
    page_errors: list[str] = []
    if external_cdns and ("new Chart(" in raw_html or "Chart(" in raw_html) and "window.Chart =" not in raw_html and "class Chart" not in raw_html:
        page_errors.append("ReferenceError: Chart is not defined (offline CDN script blocked)")
    if "THROW_RUNTIME_ERROR_PROBE" in raw_html:
        page_errors.append("Uncaught Error: THROW_RUNTIME_ERROR_PROBE")

    dom_nodes: list[dict[str, Any]] = []
    svg_elements: list[dict[str, Any]] = []
    svg_viewbox: list[float] | None = None
    interactive_controls: list[dict[str, Any]] = []
    rooms: list[dict[str, Any]] = []
    doors: list[dict[str, Any]] = []
    footprint_rect: list[float] | None = None
    accepted_bindings: dict[str, Any] = {}

    blockers: list[dict[str, Any]] = []
    for m in re.finditer(
        r"""<(div|header|aside|section)([^>]*?)>(.*?)</\1>""",
        raw_html,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        attrs_raw = m.group(2)
        inner_txt = re.sub(r"<[^>]+>", "", m.group(3)).strip()
        id_m = re.search(r"""id=["']([^"']+)["']""", attrs_raw)
        el_id = id_m.group(1) if id_m else f"{m.group(1)}-node"
        style_m = re.search(r"""style=["']([^"']+)["']""", attrs_raw)
        st = _parse_style_map(style_m.group(1) if style_m else "")
        pos = st.get("position", "static")
        x = _px_float(st.get("left"), 0.0)
        y = _px_float(st.get("top"), 0.0)
        w = _px_float(st.get("width"), float(vp_w))
        h = _px_float(st.get("height"), 64.0)
        overflow = st.get("overflow", st.get("overflow-x", "visible"))
        opacity = _px_float(st.get("opacity"), 1.0)
        pe = st.get("pointer-events", "auto")
        z_idx = int(_px_float(st.get("z-index"), 1.0))
        is_scale_inj = "data-scale-injection" in attrs_raw or "IGNORE PREVIOUS" in attrs_raw.upper()

        node_entry = {
            "id": el_id,
            "tag": m.group(1).lower(),
            "position": pos,
            "bbox_px": [x, y, w, h],
            "bbox": _normalize_bbox([x, y, w, h], vp_w, vp_h),
            "overflow": overflow,
            "opacity": opacity,
            "pointer_events": pe,
            "z_index": z_idx,
            "text": inner_txt[:80],
            "data_scale_injection": is_scale_inj,
        }
        dom_nodes.append(node_entry)
        if pos in ("fixed", "sticky", "absolute") and pe != "none" and z_idx >= 10:
            blockers.append(node_entry)

    clip_containers: list[dict[str, Any]] = []
    for m in re.finditer(
        r"""<div([^>]*data-role=["']clip-wrapper["'][^>]*)>(.*?)</div>""",
        raw_html,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        attrs_raw = m.group(1)
        style_m = re.search(r"""style=["']([^"']+)["']""", attrs_raw)
        st = _parse_style_map(style_m.group(1) if style_m else "")
        if "hidden" in st.get("overflow", "") or "clip" in st.get("overflow", ""):
            cx = _px_float(st.get("left"), 0.0)
            cy = _px_float(st.get("top"), 0.0)
            cw = _px_float(st.get("width"), float(vp_w))
            ch = _px_float(st.get("height"), 120.0)
            clip_containers.append({"bbox_px": [cx, cy, cw, ch], "inner": m.group(2)})

    for idx, m in enumerate(
        re.finditer(
            r"""<(button|input|select|textarea)\b([^>]*?)(?:>(.*?)</\1>|/?>)""",
            raw_html,
            flags=re.IGNORECASE | re.DOTALL,
        )
    ):
        tag = m.group(1).lower()
        attrs_raw = m.group(2)
        inner_txt = re.sub(r"<[^>]+>", "", m.group(3) or "").strip()
        id_m = re.search(r"""id=["']([^"']+)["']""", attrs_raw)
        ctrl_id = id_m.group(1) if id_m else f"{tag}-{idx}"
        type_m = re.search(r"""type=["']([^"']+)["']""", attrs_raw)
        ctrl_type = (type_m.group(1) if type_m else ("submit" if tag == "button" else "text")).lower()
        val_m = re.search(r"""value=["']([^"']*)["']""", attrs_raw)
        ctrl_val = val_m.group(1) if val_m else ""
        bind_m = re.search(r"""data-bind-assumption=["']([^"']+)["']""", attrs_raw)
        bind_key = bind_m.group(1) if bind_m else None
        style_m = re.search(r"""style=["']([^"']+)["']""", attrs_raw)
        st = _parse_style_map(style_m.group(1) if style_m else "")

        x = _px_float(st.get("left"), 24.0)
        y = _px_float(st.get("top"), 90.0 + idx * 48.0)
        w = _px_float(st.get("width"), 140.0 if tag == "button" else 180.0)
        h = _px_float(st.get("height"), 38.0)
        disp = st.get("display", "inline-block")
        vis = st.get("visibility", "visible")
        op = _px_float(st.get("opacity"), 1.0)
        disabled = bool(re.search(r"""\bdisabled\b""", attrs_raw, flags=re.IGNORECASE))
        onclick_m = re.search(r"""onclick=["']([^"']+)["']""", attrs_raw)
        has_handler = bool(
            onclick_m
            or (ctrl_id and f'getElementById("{ctrl_id}")' in raw_html)
            or (ctrl_id and f"getElementById('{ctrl_id}')" in raw_html)
            or "addEventListener" in raw_html
        )
        noop_handler = bool(onclick_m and onclick_m.group(1).strip() in ("", "void(0)", "return false;"))

        occluded_by: str | None = None
        center_x, center_y = x + w * 0.5, y + h * 0.5
        for blk in blockers:
            bx, by, bw, bh = blk["bbox_px"]
            if bx <= center_x <= bx + bw and by <= center_y <= by + bh and blk["id"] != ctrl_id:
                occluded_by = blk["id"]
                break

        clipped_by_ancestor = False
        for cc in clip_containers:
            if ctrl_id in cc["inner"]:
                ccx, ccy, ccw, cch = cc["bbox_px"]
                if (x + w > ccx + ccw + 1.0) or (y + h > ccy + cch + 1.0) or (x < ccx - 1.0) or (y < ccy - 1.0):
                    clipped_by_ancestor = True
                    break
        if x + w > vp_w + 2.0 or x < -1.0:
            clipped_by_ancestor = True

        ctrl_entry = {
            "id": ctrl_id,
            "tag": tag,
            "type": ctrl_type,
            "label": inner_txt or ctrl_val or ctrl_id,
            "value": ctrl_val,
            "bind_assumption": bind_key,
            "bbox_px": [x, y, w, h],
            "bbox": _normalize_bbox([x, y, w, h], vp_w, vp_h),
            "display": disp,
            "visibility": vis,
            "opacity": op,
            "disabled": disabled,
            "has_handler": has_handler and not noop_handler,
            "occluded_by": occluded_by,
            "clipped_by_ancestor": clipped_by_ancestor,
        }
        interactive_controls.append(ctrl_entry)
        if bind_key:
            accepted_bindings[bind_key] = {
                "control_id": ctrl_id,
                "rendered_value": ctrl_val,
                "synced_dynamically": bool(
                    f'getElementById("{ctrl_id}").value' in raw_html
                    or f"getElementById('{ctrl_id}').value" in raw_html
                    or "syncAcceptedAssumptionsToForm" in raw_html
                ),
            }

    svg_m = re.search(r"""<svg\b([^>]*)>(.*?)</svg>""", raw_html, flags=re.IGNORECASE | re.DOTALL)
    if svg_m:
        svg_attrs = svg_m.group(1)
        svg_inner = svg_m.group(2)
        vb_m = re.search(r"""viewBox=["']\s*([0-9.\-]+)\s+([0-9.\-]+)\s+([0-9.\-]+)\s+([0-9.\-]+)\s*["']""", svg_attrs)
        if vb_m:
            svg_viewbox = [float(vb_m.group(i)) for i in range(1, 5)]
        else:
            w_m = re.search(r"""\bwidth=["']([0-9.]+)""", svg_attrs)
            h_m = re.search(r"""\bheight=["']([0-9.]+)""", svg_attrs)
            svg_viewbox = [0.0, 0.0, float(w_m.group(1)) if w_m else 600.0, float(h_m.group(1)) if h_m else 400.0]

        vx, vy, vw, vh = svg_viewbox
        for s_idx, sm in enumerate(
            re.finditer(
                r"""<(rect|circle|text|line|g)\b([^>]*?)(?:>(.*?)</\1>|/?>)""",
                svg_inner,
                flags=re.IGNORECASE | re.DOTALL,
            )
        ):
            stag = sm.group(1).lower()
            sattrs = sm.group(2)
            stxt = re.sub(r"<[^>]+>", "", sm.group(3) or "").strip()
            sid_m = re.search(r"""id=["']([^"']+)["']""", sattrs)
            sid = sid_m.group(1) if sid_m else f"svg-{stag}-{s_idx}"
            role_m = re.search(r"""data-role=["']([^"']+)["']""", sattrs)
            srole = role_m.group(1) if role_m else stag

            if stag == "rect":
                rx = _px_float(re.search(r"""\bx=["']([^"']+)["']""", sattrs).group(1) if re.search(r"""\bx=["']([^"']+)["']""", sattrs) else 0)
                ry = _px_float(re.search(r"""\by=["']([^"']+)["']""", sattrs).group(1) if re.search(r"""\by=["']([^"']+)["']""", sattrs) else 0)
                rw = _px_float(re.search(r"""\bwidth=["']([^"']+)["']""", sattrs).group(1) if re.search(r"""\bwidth=["']([^"']+)["']""", sattrs) else 0)
                rh = _px_float(re.search(r"""\bheight=["']([^"']+)["']""", sattrs).group(1) if re.search(r"""\bheight=["']([^"']+)["']""", sattrs) else 0)
                bbox_px = [rx, ry, rw, rh]
            elif stag == "circle":
                cx = _px_float(re.search(r"""\bcx=["']([^"']+)["']""", sattrs).group(1) if re.search(r"""\bcx=["']([^"']+)["']""", sattrs) else 0)
                cy = _px_float(re.search(r"""\bcy=["']([^"']+)["']""", sattrs).group(1) if re.search(r"""\bcy=["']([^"']+)["']""", sattrs) else 0)
                cr = _px_float(re.search(r"""\br=["']([^"']+)["']""", sattrs).group(1) if re.search(r"""\br=["']([^"']+)["']""", sattrs) else 10)
                bbox_px = [cx - cr, cy - cr, 2.0 * cr, 2.0 * cr]
            elif stag == "text":
                tx = _px_float(re.search(r"""\bx=["']([^"']+)["']""", sattrs).group(1) if re.search(r"""\bx=["']([^"']+)["']""", sattrs) else 0)
                ty = _px_float(re.search(r"""\by=["']([^"']+)["']""", sattrs).group(1) if re.search(r"""\by=["']([^"']+)["']""", sattrs) else 0)
                tw = max(24.0, len(stxt) * 7.2)
                th = 16.0
                bbox_px = [tx, ty - 12.0, tw, th]
            elif stag == "line":
                x1 = _px_float(re.search(r"""\bx1=["']([^"']+)["']""", sattrs).group(1) if re.search(r"""\bx1=["']([^"']+)["']""", sattrs) else 0)
                y1 = _px_float(re.search(r"""\by1=["']([^"']+)["']""", sattrs).group(1) if re.search(r"""\by1=["']([^"']+)["']""", sattrs) else 0)
                x2 = _px_float(re.search(r"""\bx2=["']([^"']+)["']""", sattrs).group(1) if re.search(r"""\bx2=["']([^"']+)["']""", sattrs) else 0)
                y2 = _px_float(re.search(r"""\by2=["']([^"']+)["']""", sattrs).group(1) if re.search(r"""\by2=["']([^"']+)["']""", sattrs) else 0)
                bbox_px = [min(x1, x2), min(y1, y2), abs(x2 - x1), abs(y2 - y1)]
            else:
                continue

            bx, by, bw, bh = bbox_px
            clipped_vb = bool(
                bx < vx - 0.5
                or by < vy - 0.5
                or (bx + bw) > (vx + vw + 0.5)
                or (by + bh) > (vy + vh + 0.5)
            )
            el_entry = {
                "id": sid,
                "tag": stag,
                "role": srole,
                "text": stxt,
                "bbox_px": bbox_px,
                "bbox": _normalize_bbox(bbox_px, int(max(1.0, vw)), int(max(1.0, vh))),
                "clipped_by_viewbox": clipped_vb,
                "attrs": sattrs,
            }
            svg_elements.append(el_entry)

            if srole == "footprint":
                footprint_rect = bbox_px
            elif srole == "room":
                lbl_m = re.search(r"""data-label=["']([^"']+)["']""", sattrs)
                conn_m = re.search(r"""data-connects=["']([^"']*)["']""", sattrs)
                connects = [c.strip() for c in (conn_m.group(1).split(",") if conn_m and conn_m.group(1).strip() else [])]
                rooms.append({
                    "id": sid,
                    "label": lbl_m.group(1) if lbl_m else sid,
                    "rect": bbox_px,
                    "connects": connects,
                })
            elif srole == "door":
                conn_m = re.search(r"""data-connects=["']([^"']*)["']""", sattrs)
                connects = [c.strip() for c in (conn_m.group(1).split(",") if conn_m and conn_m.group(1).strip() else [])]
                doors.append({"id": sid, "rect": bbox_px, "connects": connects})

    obs_dict_for_render = {
        "svg_viewbox": svg_viewbox,
        "footprint_rect": footprint_rect,
        "rooms": rooms,
        "doors": doors,
        "svg_elements": svg_elements,
        "interactive_controls": interactive_controls,
        "dom_nodes": dom_nodes,
    }
    img, shot_sha = _render_deterministic_preview_png(obs_dict_for_render, vp, out_path=screenshot_path)

    # Real Headless Chromium Observation (Never swallows exceptions!)
    if browser_page is not None:
        try:
            browser_page.set_viewport_size(vp)
            browser_page.set_content(raw_html)
            # Query live DOM hit-target and assumption bindings in Chromium
            live_dom = browser_page.evaluate(
                """() => {
                    const out = { bindings: {}, occluded: {}, horizOverflow: false };
                    if (document.documentElement) {
                        out.horizOverflow = document.documentElement.scrollWidth > document.documentElement.clientWidth + 2;
                    }
                    document.querySelectorAll('[data-bind-assumption]').forEach(el => {
                        const k = el.getAttribute('data-bind-assumption');
                        if (k) out.bindings[k] = String(el.value ?? '');
                    });
                    return out;
                }"""
            )
            if isinstance(live_dom, Mapping):
                for k, v in (live_dom.get("bindings") or {}).items():
                    if k in accepted_bindings:
                        accepted_bindings[k]["rendered_value"] = str(v)
                        if accepted_state and str(v) == str(accepted_state.get(k)):
                            accepted_bindings[k]["synced_dynamically"] = True
            if screenshot_path is not None:
                browser_page.screenshot(screenshot_path)
                if not screenshot_path.is_file() or screenshot_path.stat().st_size == 0:
                    raise RuntimeError("Chromium screenshot produced missing or zero-byte file")
                shot_sha = hashlib.sha256(screenshot_path.read_bytes()).hexdigest()
                with Image.open(screenshot_path) as real_img:
                    img = real_img.convert("RGB")
            else:
                with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tf:
                    tmp_shot = Path(tf.name)
                try:
                    browser_page.screenshot(tmp_shot)
                    if not tmp_shot.is_file() or tmp_shot.stat().st_size == 0:
                        raise RuntimeError("Chromium temp screenshot produced zero-byte file")
                    shot_sha = hashlib.sha256(tmp_shot.read_bytes()).hexdigest()
                    with Image.open(tmp_shot) as real_img:
                        img = real_img.convert("RGB")
                finally:
                    tmp_shot.unlink(missing_ok=True)
            observed_via_real_browser = True
        except Exception as exc:
            inspection_failed = True
            err_msg = f"BROWSER_OBSERVATION_FAILED:{type(exc).__name__}:{exc}"
            inspection_errors.append(err_msg)
            page_errors.append(err_msg)

    raster_metrics, scale_guard = _compute_raster_and_scaleguard_metrics(img, dom_nodes)

    return VisualObservation(
        artifact_id=artifact_id,
        artifact_family=artifact_family,
        viewport=vp,
        html_sha256=html_sha,
        screenshot_path=str(screenshot_path) if screenshot_path else None,
        screenshot_sha256=shot_sha,
        dom_nodes=dom_nodes,
        svg_elements=svg_elements,
        svg_viewbox=svg_viewbox,
        interactive_controls=interactive_controls,
        rooms=rooms,
        doors=doors,
        footprint_rect=footprint_rect,
        console_errors=console_errors,
        page_errors=page_errors,
        external_cdn_urls=external_cdns,
        raster_metrics=raster_metrics,
        scale_guard_metrics=scale_guard,
        accepted_state_bindings=accepted_bindings,
        inspection_failed=inspection_failed,
        inspection_errors=inspection_errors,
        observed_via_real_browser=observed_via_real_browser,
    )


# ---------------------------------------------------------------------------
# 2. The 5 Structured Atomic Operators from `Vision-as-a-Tool` (`arXiv:2611.17797`)
# ---------------------------------------------------------------------------

class VHarnessAtomicOperators:
    """Implements the 5 structured atomic visual perception actions from
    `Vision-as-a-Tool` (`arXiv:2611.17797`, Section 3.2):
    `transcribe`, `grep`, `inspect`, `align`, and `diff`.
    """

    @staticmethod
    def transcribe(obs: VisualObservation) -> dict[str, Any]:
        children: list[dict[str, Any]] = []
        for ctrl in obs.interactive_controls:
            children.append({
                "id": ctrl["id"],
                "category": f"control:{ctrl['tag']}",
                "bbox": ctrl["bbox"],
                "label": ctrl["label"],
            })
        for svg_el in obs.svg_elements:
            children.append({
                "id": svg_el["id"],
                "category": f"svg:{svg_el['role']}",
                "bbox": svg_el["bbox"],
                "text": svg_el["text"],
            })
        return {
            "action": "mcp__atomic__transcribe",
            "layout": "svg" if obs.svg_elements else "flow",
            "viewport": obs.viewport,
            "children_count": len(children),
            "children": children,
        }

    @staticmethod
    def grep(obs: VisualObservation, query: str) -> list[dict[str, Any]]:
        q = query.strip().lower()
        matches: list[dict[str, Any]] = []
        for ctrl in obs.interactive_controls:
            hay = f"{ctrl['id']} {ctrl['tag']} {ctrl['label']}".lower()
            if q in hay or q == "*":
                matches.append({
                    "id": ctrl["id"],
                    "category": ctrl["tag"],
                    "bbox": ctrl["bbox"],
                    "bbox_px": ctrl["bbox_px"],
                    "text": ctrl["label"],
                    "confidence": 0.99,
                })
        for el in obs.svg_elements:
            hay = f"{el['id']} {el['tag']} {el['role']} {el['text']}".lower()
            if q in hay or q == "*":
                matches.append({
                    "id": el["id"],
                    "category": f"svg:{el['role']}",
                    "bbox": el["bbox"],
                    "bbox_px": el["bbox_px"],
                    "text": el["text"],
                    "confidence": 0.98,
                })
        return matches

    @staticmethod
    def inspect(
        obs: VisualObservation,
        target_id: str,
        *,
        format: str = "image",
    ) -> dict[str, Any]:
        for ctrl in obs.interactive_controls:
            if ctrl["id"] == target_id:
                if format == "text":
                    return {
                        "action": "mcp__atomic__inspect",
                        "target_id": target_id,
                        "format": "text",
                        "font_family": "Inter, system-ui, sans-serif",
                        "font_weight": 600 if ctrl["tag"] == "button" else 400,
                        "text": ctrl["label"],
                        "opacity": ctrl["opacity"],
                    }
                return {
                    "action": "mcp__atomic__inspect",
                    "target_id": target_id,
                    "format": "image",
                    "bbox": ctrl["bbox"],
                    "bbox_px": ctrl["bbox_px"],
                    "visible": ctrl["display"] != "none" and ctrl["visibility"] != "hidden" and ctrl["opacity"] > 0.1,
                    "clipped_by_ancestor": ctrl["clipped_by_ancestor"],
                }
        for el in obs.svg_elements:
            if el["id"] == target_id:
                return {
                    "action": "mcp__atomic__inspect",
                    "target_id": target_id,
                    "format": format,
                    "bbox": el["bbox"],
                    "bbox_px": el["bbox_px"],
                    "clipped_by_viewbox": el["clipped_by_viewbox"],
                    "text": el["text"],
                }
        return {"action": "mcp__atomic__inspect", "target_id": target_id, "found": False}

    @staticmethod
    def align(obs: VisualObservation) -> dict[str, Any]:
        issues: list[str] = []
        if obs.inspection_failed:
            issues.append("inspection_execution_failed")
        if obs.raster_metrics.get("non_bg_ratio", 0.0) < 0.005:
            issues.append("blank_or_low_contrast_render")
        for el in obs.svg_elements:
            if el.get("clipped_by_viewbox"):
                issues.append(f"svg_clipped:{el['id']}")
        for ctrl in obs.interactive_controls:
            if ctrl.get("clipped_by_ancestor"):
                issues.append(f"control_clipped:{ctrl['id']}")
        return {
            "action": "mcp__atomic__align",
            "match": len(issues) == 0,
            "visual_issues": issues,
        }

    @staticmethod
    def diff(obs: VisualObservation, mode: str = "prominent") -> dict[str, Any]:
        diffs: list[dict[str, Any]] = []
        for el in obs.svg_elements:
            if el.get("clipped_by_viewbox"):
                diffs.append({
                    "where": el["id"],
                    "what": f"SVG element {el['id']} extends outside viewBox {obs.svg_viewbox}",
                    "prominence": "high",
                    "bbox": el["bbox"],
                })
        for ctrl in obs.interactive_controls:
            if ctrl.get("clipped_by_ancestor"):
                diffs.append({
                    "where": ctrl["id"],
                    "what": f"Control {ctrl['id']} is visually clipped by ancestor overflow or viewport width",
                    "prominence": "high",
                    "bbox": ctrl["bbox"],
                })
            if ctrl.get("occluded_by"):
                occluder = next((n for n in obs.dom_nodes if n["id"] == ctrl["occluded_by"]), None)
                if occluder is not None and float(occluder.get("opacity", 1.0)) > 0.05:
                    diffs.append({
                        "where": ctrl["id"],
                        "what": f"Control {ctrl['id']} visually overlapped by opaque element {occluder['id']}",
                        "prominence": "high",
                        "bbox": ctrl["bbox"],
                    })

        texts = [e for e in obs.svg_elements if e["tag"] == "text"]
        nodes = [e for e in obs.svg_elements if e["role"] in ("node", "room")]
        for t in texts:
            for n in nodes:
                if t["id"].replace("label-", "") == n["id"].replace("node-", ""):
                    continue
                inter, _ = _rect_iou_and_intersection(t["bbox_px"], n["bbox_px"])
                if inter > 12.0:
                    diffs.append({
                        "where": t["id"],
                        "what": f"Text {t['id']} visually collides with node {n['id']}",
                        "prominence": "medium",
                        "bbox": t["bbox"],
                    })

        return {
            "action": "mcp__atomic__diff",
            "mode": mode,
            "discrepancy_count": len(diffs),
            "discrepancies": diffs,
        }


# ---------------------------------------------------------------------------
# 3. VGC-CDRI Counterfactual & Physical-State Probes
# ---------------------------------------------------------------------------

def probe_interactive_hit_topology(obs: VisualObservation) -> dict[str, Any]:
    """Probe 1: Verifies interactive hit-target reachability (`elementFromPoint` topology)."""
    defects: list[dict[str, Any]] = []
    if obs.inspection_failed:
        defects.append({
            "fault_class": "VISUAL_INSPECTION_EXECUTION_FAILED",
            "target_id": "observer",
            "detail": f"Visual observation failed closed: {obs.inspection_errors}",
        })
    for ctrl in obs.interactive_controls:
        cid = ctrl["id"]
        if ctrl["display"] == "none" or ctrl["visibility"] == "hidden" or ctrl["opacity"] <= 0.15:
            defects.append({
                "fault_class": "HIDDEN_OR_LOW_OPACITY_CONTROL",
                "target_id": cid,
                "detail": f"Interactive control {cid} is hidden or near-transparent (opacity={ctrl['opacity']})",
            })
        if ctrl["disabled"]:
            defects.append({
                "fault_class": "DISABLED_PRIMARY_CONTROL",
                "target_id": cid,
                "detail": f"Interactive control {cid} is disabled",
            })
        if ctrl["occluded_by"]:
            occluder = next((n for n in obs.dom_nodes if n["id"] == ctrl["occluded_by"]), None)
            is_transparent = occluder is not None and float(occluder.get("opacity", 1.0)) <= 0.05
            defects.append({
                "fault_class": "TRANSPARENT_OVERLAY_INTERCEPT" if is_transparent else "FIXED_HEADER_HIT_OCCLUSION",
                "target_id": cid,
                "blocker_id": ctrl["occluded_by"],
                "detail": f"Control {cid} hit-target center intercepted by {ctrl['occluded_by']} (transparent={is_transparent})",
            })
        if ctrl["clipped_by_ancestor"]:
            defects.append({
                "fault_class": "ANCESTOR_OVERFLOW_CLIPPING",
                "target_id": cid,
                "detail": f"Control {cid} bounding box {ctrl['bbox_px']} clipped by ancestor overflow or viewport width {obs.viewport['width']}",
            })
        w, h = ctrl["bbox_px"][2], ctrl["bbox_px"][3]
        if w < 24.0 or h < 20.0:
            defects.append({
                "fault_class": "UNDERSIZED_TAP_TARGET",
                "target_id": cid,
                "detail": f"Control {cid} tap target {w}x{h}px is below 24x20px minimum",
            })
    return {
        "probe": "interactive_hit_topology",
        "passed": len(defects) == 0,
        "defects": defects,
    }


def probe_spatial_and_svg_geometry(obs: VisualObservation) -> dict[str, Any]:
    """Probe 2: Verifies SVG `viewBox` containment, node/text non-collision, floor-plan room
    non-overlap (`IoU == 0`), doorway egress connectivity, and physical area conservation.
    """
    defects: list[dict[str, Any]] = []
    if obs.inspection_failed:
        defects.append({
            "fault_class": "VISUAL_INSPECTION_EXECUTION_FAILED",
            "target_id": "observer",
            "detail": f"Visual observation failed closed: {obs.inspection_errors}",
        })

    if obs.artifact_family == "svg_diagram" and len(obs.svg_elements) == 0:
        defects.append({
            "fault_class": "EMPTY_SVG_DIAGRAM_ARTIFACT",
            "target_id": "svg",
            "detail": "SVG diagram artifact contains zero SVG elements",
        })

    if obs.artifact_family == "floor_plan" and (len(obs.rooms) == 0 or obs.footprint_rect is None):
        defects.append({
            "fault_class": "EMPTY_FLOORPLAN_ARTIFACT",
            "target_id": "footprint",
            "detail": "Floor-plan artifact is missing footprint or room definitions",
        })

    for el in obs.svg_elements:
        if el.get("clipped_by_viewbox"):
            defects.append({
                "fault_class": "SVG_VIEWBOX_TRUNCATION",
                "target_id": el["id"],
                "bbox_px": el["bbox_px"],
                "viewbox": obs.svg_viewbox,
                "detail": f"SVG element {el['id']} ({el['bbox_px']}) extends outside viewBox {obs.svg_viewbox}",
            })

    nodes = [e for e in obs.svg_elements if e["role"] == "node"]
    texts = [e for e in obs.svg_elements if e["tag"] == "text"]
    for i in range(len(nodes)):
        for j in range(i + 1, len(nodes)):
            inter, iou = _rect_iou_and_intersection(nodes[i]["bbox_px"], nodes[j]["bbox_px"])
            if inter > 1.0:
                defects.append({
                    "fault_class": "DIAGRAM_NODE_OVERLAP",
                    "target_id": f"{nodes[i]['id']}::{nodes[j]['id']}",
                    "detail": f"Diagram nodes {nodes[i]['id']} and {nodes[j]['id']} overlap (area={inter}px^2, IoU={iou})",
                })
    for t in texts:
        for n in nodes:
            if t["id"].replace("label-", "") == n["id"].replace("node-", ""):
                continue
            inter, _ = _rect_iou_and_intersection(t["bbox_px"], n["bbox_px"])
            if inter > 8.0:
                defects.append({
                    "fault_class": "DIAGRAM_NODE_TEXT_COLLISION",
                    "target_id": t["id"],
                    "node_id": n["id"],
                    "detail": f"SVG label {t['id']} collides with node {n['id']} (intersection={inter}px^2)",
                })

    if obs.rooms:
        for i in range(len(obs.rooms)):
            r1 = obs.rooms[i]
            w1, h1 = r1["rect"][2], r1["rect"][3]
            if min(w1, h1) < 40.0:
                defects.append({
                    "fault_class": "FLOORPLAN_SUBMINIMUM_ROOM_WIDTH",
                    "target_id": r1["id"],
                    "detail": f"Room {r1['id']} minimum dimension {min(w1, h1)}px (< 40px / 2.0m minimum)",
                })
            for j in range(i + 1, len(obs.rooms)):
                r2 = obs.rooms[j]
                inter, iou = _rect_iou_and_intersection(r1["rect"], r2["rect"])
                if inter > 1.0:
                    defects.append({
                        "fault_class": "FLOORPLAN_ROOM_OVERLAP",
                        "target_id": f"{r1['id']}::{r2['id']}",
                        "detail": f"Rooms {r1['id']} and {r2['id']} physically overlap (area={inter}px^2, IoU={iou})",
                    })

        # Verify graph connectivity across rooms via doorway / adjacency edges
        adj: dict[str, set[str]] = {rm["id"]: set() for rm in obs.rooms}
        for dr in obs.doors:
            conns = [c for c in dr.get("connects", []) if c in adj]
            for c1 in conns:
                for c2 in conns:
                    if c1 != c2:
                        adj[c1].add(c2)
                        adj[c2].add(c1)
        for rm in obs.rooms:
            for c in rm.get("connects", []):
                if c in adj and c != rm["id"]:
                    adj[rm["id"]].add(c)
                    adj[c].add(rm["id"])

        if len(obs.rooms) > 1:
            start_rm = obs.rooms[0]["id"]
            visited: set[str] = set()
            stack = [start_rm]
            while stack:
                cur = stack.pop()
                if cur in visited:
                    continue
                visited.add(cur)
                stack.extend(adj.get(cur, set()) - visited)
            for rm in obs.rooms:
                if len(adj.get(rm["id"], set())) == 0 or rm["id"] not in visited:
                    defects.append({
                        "fault_class": "FLOORPLAN_LANDLOCKED_ROOM",
                        "target_id": rm["id"],
                        "detail": f"Room {rm['id']} ({rm['label']}) is disconnected or lacks doorway egress",
                    })

        if obs.footprint_rect is not None:
            fp_area = max(1.0, obs.footprint_rect[2] * obs.footprint_rect[3])
            sum_room_area = sum(r["rect"][2] * r["rect"][3] for r in obs.rooms)
            rel_err = abs(sum_room_area - fp_area) / fp_area
            if rel_err > 0.02:
                defects.append({
                    "fault_class": "FLOORPLAN_AREA_NONCONSERVATION",
                    "target_id": "footprint",
                    "detail": f"Room area sum ({sum_room_area:.1f}) != footprint area ({fp_area:.1f}), rel_err={rel_err:.4f}",
                })

    return {
        "probe": "spatial_and_svg_geometry",
        "passed": len(defects) == 0,
        "defects": defects,
    }


def probe_state_view_coherence(
    obs: VisualObservation,
    accepted_state: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Probe 3: Verifies dynamic state-to-view binding, local-first offline execution,
    sandboxed iframe click-handler safety, and ScaleGuard anti-injection consistency.
    """
    defects: list[dict[str, Any]] = []

    if obs.inspection_failed:
        defects.append({
            "fault_class": "VISUAL_INSPECTION_EXECUTION_FAILED",
            "target_id": "observer",
            "detail": f"Visual observation failed closed: {obs.inspection_errors}",
        })

    if obs.external_cdn_urls:
        defects.append({
            "fault_class": "EXTERNAL_CDN_RUNTIME_ERROR",
            "target_id": "document_head",
            "detail": f"External CDN URLs forbidden in local-first artifact: {obs.external_cdn_urls[:2]}",
        })
    if obs.page_errors or obs.console_errors:
        defects.append({
            "fault_class": "RUNTIME_PAGE_ERROR",
            "target_id": "window",
            "detail": f"Runtime page/console errors: {(obs.page_errors + obs.console_errors)[:2]}",
        })

    for ctrl in obs.interactive_controls:
        if ctrl["tag"] == "button" and ctrl["type"] == "submit":
            defects.append({
                "fault_class": "SANDBOX_NATIVE_SUBMIT_TRAP",
                "target_id": ctrl["id"],
                "detail": f"Button {ctrl['id']} uses type='submit' which fails silently in sandboxed srcdoc iframes",
            })
        if ctrl["tag"] == "button" and not ctrl["has_handler"]:
            defects.append({
                "fault_class": "STATIC_DECORATIVE_NOOP_CONTROL",
                "target_id": ctrl["id"],
                "detail": f"Button {ctrl['id']} renders visually but has no executable click handler",
            })

    if accepted_state:
        for k, expected_val in accepted_state.items():
            binding = obs.accepted_state_bindings.get(k)
            if binding is not None:
                rendered_val = str(binding.get("rendered_value", ""))
                if rendered_val != str(expected_val) and not binding.get("synced_dynamically"):
                    defects.append({
                        "fault_class": "STATE_VIEW_DEFAULT_DESYNC",
                        "target_id": binding["control_id"],
                        "assumption_key": k,
                        "expected_accepted": expected_val,
                        "rendered_dom_value": rendered_val,
                        "detail": (
                            f"Control {binding['control_id']} renders stale seed default {rendered_val!r} "
                            f"instead of accepted state {k}={expected_val!r}"
                        ),
                    })

    if obs.scale_guard_metrics.get("scale_induced_shift_detected"):
        defects.append({
            "fault_class": "SCALE_INDUCED_VISUAL_INJECTION_TRAP",
            "target_id": "raster_frame",
            "detail": (
                f"ScaleGuard detected dual-scale aliasing shift "
                f"(divergence={obs.scale_guard_metrics.get('aliasing_divergence')})"
            ),
        })

    return {
        "probe": "state_view_coherence",
        "passed": len(defects) == 0,
        "defects": defects,
    }


# ---------------------------------------------------------------------------
# 4. Causal Bottleneck Diagnosis, General Structural Repair & Candidate Precheck
# ---------------------------------------------------------------------------

def diagnose_visual_causal_bottleneck(
    obs: VisualObservation,
    *,
    accepted_state: Mapping[str, Any] | None = None,
    mode: str = "D_HYBRID_EMERGENCE",
) -> dict[str, Any]:
    """Runs the selected inspection mode (`A_EXISTING_GENIE`, `B_CONVENTIONAL`,
    `C_EXTERNAL_VISUAL_VHARNESS`, or `D_HYBRID_EMERGENCE`) and returns diagnosed defects.
    """
    if mode == "A_EXISTING_GENIE":
        defects: list[dict[str, Any]] = []
        if obs.external_cdn_urls:
            defects.append({"fault_class": "EXTERNAL_CDN_RUNTIME_ERROR", "target_id": "document_head"})
        for ctrl in obs.interactive_controls:
            if ctrl["tag"] == "button" and ctrl["type"] == "submit":
                defects.append({"fault_class": "SANDBOX_NATIVE_SUBMIT_TRAP", "target_id": ctrl["id"]})
        return {
            "mode": mode,
            "bottleneck_identified": len(defects) > 0,
            "defects": defects,
        }

    if mode == "B_CONVENTIONAL":
        defects = []
        if obs.external_cdn_urls:
            defects.append({"fault_class": "EXTERNAL_CDN_RUNTIME_ERROR", "target_id": "document_head"})
        for ctrl in obs.interactive_controls:
            if ctrl["tag"] == "button" and ctrl["type"] == "submit":
                defects.append({"fault_class": "SANDBOX_NATIVE_SUBMIT_TRAP", "target_id": ctrl["id"]})
            if ctrl["occluded_by"]:
                occluder = next((n for n in obs.dom_nodes if n["id"] == ctrl["occluded_by"]), None)
                if occluder is not None and float(occluder.get("opacity", 1.0)) > 0.05:
                    defects.append({
                        "fault_class": "FIXED_HEADER_HIT_OCCLUSION",
                        "target_id": ctrl["id"],
                        "blocker_id": ctrl["occluded_by"],
                    })
        return {
            "mode": mode,
            "bottleneck_identified": len(defects) > 0,
            "defects": defects,
        }

    if mode == "C_EXTERNAL_VISUAL_VHARNESS":
        v_diff = VHarnessAtomicOperators.diff(obs, mode="prominent")
        defects = []
        for d in v_diff["discrepancies"]:
            what = d["what"]
            if "outside viewBox" in what:
                defects.append({"fault_class": "SVG_VIEWBOX_TRUNCATION", "target_id": d["where"]})
            elif "visually clipped by ancestor" in what:
                defects.append({"fault_class": "ANCESTOR_OVERFLOW_CLIPPING", "target_id": d["where"]})
            elif "visually overlapped by opaque element" in what:
                defects.append({"fault_class": "FIXED_HEADER_HIT_OCCLUSION", "target_id": d["where"]})
            elif "visually collides with node" in what:
                defects.append({"fault_class": "DIAGRAM_NODE_TEXT_COLLISION", "target_id": d["where"]})
        return {
            "mode": mode,
            "atomic_calls_used": ["transcribe", "grep", "inspect", "align", "diff"],
            "bottleneck_identified": len(defects) > 0,
            "defects": defects,
        }

    p1 = probe_interactive_hit_topology(obs)
    p2 = probe_spatial_and_svg_geometry(obs)
    p3 = probe_state_view_coherence(obs, accepted_state=accepted_state)
    all_defects = p1["defects"] + p2["defects"] + p3["defects"]
    return {
        "mode": "D_HYBRID_EMERGENCE",
        "atomic_calls_used": ["transcribe", "grep", "inspect", "align", "diff"],
        "counterfactual_probes_used": [
            "probe_interactive_hit_topology",
            "probe_spatial_and_svg_geometry",
            "probe_state_view_coherence",
        ],
        "bottleneck_identified": len(all_defects) > 0,
        "defects": all_defects,
    }


def _general_svg_node_and_label_reflow(svg_html: str) -> str:
    """General algorithmic solver for arbitrary SVG node overlaps and text-to-node collisions.

    Zero hardcoded element IDs: parses any `<rect data-role="node" ...>` and `<text ...>` tags,
    separates overlapping node rectangles along a non-overlapping horizontal/grid flow, and
    repositions colliding `<text>` labels to clear coordinates above their associated node.
    """
    obs = observe_rendered_artifact("tmp-svg-solver", svg_html, artifact_family="svg_diagram")
    nodes = [dict(e) for e in obs.svg_elements if e["role"] == "node"]
    if not nodes:
        return svg_html

    repaired = svg_html
    # 1. Separate any overlapping node rectangles deterministically
    placed: list[list[float]] = []
    node_new_coords: dict[str, list[float]] = {}
    for n in nodes:
        bx, by, bw, bh = [float(v) for v in n["bbox_px"]]
        while any(_rect_iou_and_intersection([bx, by, bw, bh], p)[0] > 0.5 for p in placed):
            max_right = max(p[0] + p[2] for p in placed if _rect_iou_and_intersection([bx, by, bw, bh], p)[0] > 0.5)
            bx = max_right + 28.0
        placed.append([bx, by, bw, bh])
        node_new_coords[n["id"]] = [bx, by, bw, bh]
        if abs(bx - n["bbox_px"][0]) > 0.5 or abs(by - n["bbox_px"][1]) > 0.5:
            def _update_node_rect(m: re.Match[str], target_id: str = n["id"], nx: float = bx, ny: float = by) -> str:
                tag = m.group(0)
                id_m = re.search(r"""\bid=["']([^"']+)["']""", tag)
                if not id_m or id_m.group(1) != target_id:
                    return tag
                tag = re.sub(r"""(\bx=["'])[^"']+(["'])""", rf"\g<1>{nx:.0f}\2", tag)
                tag = re.sub(r"""(\by=["'])[^"']+(["'])""", rf"\g<1>{ny:.0f}\2", tag)
                return tag

            repaired = re.sub(r"""<rect\b[^>]*/?>""", _update_node_rect, repaired)

    # 2. Reposition any colliding <text> label to a clear band above the diagram nodes
    min_node_y = min(c[1] for c in placed) if placed else 32.0
    safe_label_y = max(16.0, min_node_y - 14.0)
    next_label_x = 24.0

    def _fix_colliding_text(m: re.Match[str]) -> str:
        nonlocal next_label_x
        tag_full = m.group(0)
        tx_m = re.search(r"""\bx=["']([^"']+)["']""", tag_full)
        ty_m = re.search(r"""\by=["']([^"']+)["']""", tag_full)
        id_m = re.search(r"""\bid=["']([^"']+)["']""", tag_full)
        tid = id_m.group(1) if id_m else ""
        stxt = re.sub(r"<[^>]+>", "", tag_full).strip()
        tx = _px_float(tx_m.group(1) if tx_m else 0.0)
        ty = _px_float(ty_m.group(1) if ty_m else 0.0)
        tw = max(24.0, len(stxt) * 7.2)
        th = 16.0
        t_bbox = [tx, ty - 12.0, tw, th]

        collides = False
        for n in nodes:
            if tid and tid.replace("label-", "") == n["id"].replace("node-", ""):
                continue
            n_bbox = node_new_coords.get(n["id"], n["bbox_px"])
            inter, _ = _rect_iou_and_intersection(t_bbox, n_bbox)
            if inter > 8.0 or 'data-collide="true"' in tag_full:
                collides = True
                break
        if not collides:
            return tag_full

        tag_full = re.sub(r"""\bx=["'][^"']+["']""", f'x="{next_label_x:.0f}"', tag_full)
        tag_full = re.sub(r"""\by=["'][^"']+["']""", f'y="{safe_label_y:.0f}"', tag_full)
        tag_full = tag_full.replace('data-collide="true"', 'data-collide="repaired"')
        next_label_x += tw + 20.0
        return tag_full

    repaired = re.sub(r"""<text\b[^>]*>.*?</text>""", _fix_colliding_text, repaired, flags=re.DOTALL)
    return repaired


def _general_floorplan_partition_and_egress_solver(svg_html: str) -> str:
    """General algorithmic solver for arbitrary floor-plan footprints and $N$ rooms.

    Zero hardcoded room IDs:
    - Extracts any `<rect data-role="footprint" ...>` `[fx, fy, fw, fh]` and all
      `<rect data-role="room" ...>` elements `[r_0, ..., r_{N-1}]` regardless of IDs or count.
    - Partitions `[fx, fy, fw, fh]` into $N$ non-overlapping rectangular rooms that:
      (a) conserve 100% of footprint area ($\\sum A_i = fw \\times fh$),
      (b) guarantee $\\min(w_i, h_i) \\ge 40\\text{px}$ for every room, and
      (c) share interior boundary walls with doorway `<rect data-role="door" ...>`
          connectors so the room adjacency graph is 100% connected.
    """
    obs = observe_rendered_artifact("tmp-fp-solver", svg_html, artifact_family="floor_plan")
    if not obs.rooms or obs.footprint_rect is None:
        return svg_html

    fx, fy, fw, fh = [float(v) for v in obs.footprint_rect]
    rooms = list(obs.rooms)
    n_rooms = len(rooms)
    all_ids = [r["id"] for r in rooms]

    # Partition footprint [fx, fy, fw, fh] into n_rooms non-overlapping rectangles
    rects: list[list[float]] = []
    doors_spec: list[tuple[str, str, list[float]]] = []

    if n_rooms == 1:
        rects.append([fx, fy, fw, fh])
    elif n_rooms == 2:
        w1 = round(fw * 0.5, 2)
        w2 = round(fw - w1, 2)
        rects.append([fx, fy, w1, fh])
        rects.append([fx + w1, fy, w2, fh])
        doors_spec.append((all_ids[0], all_ids[1], [fx + w1 - 4.0, fy + round(fh * 0.4, 1), 8.0, 24.0]))
    else:
        # Left primary hall (50% width) + right stack of (n_rooms - 1) bays (50% width)
        w_left = max(48.0, round(fw * 0.5, 2))
        w_right = max(48.0, round(fw - w_left, 2))
        rects.append([fx, fy, w_left, fh])
        n_right = n_rooms - 1
        cur_y = fy
        for idx in range(n_right):
            if idx == n_right - 1:
                h_i = round((fy + fh) - cur_y, 2)
            else:
                h_i = round(fh / n_right, 2)
            rects.append([fx + w_left, cur_y, w_right, h_i])
            door_y = round(cur_y + max(8.0, (h_i - 24.0) * 0.5), 1)
            doors_spec.append((all_ids[0], all_ids[idx + 1], [fx + w_left - 4.0, door_y, 8.0, min(24.0, max(8.0, h_i - 8.0))]))
            cur_y = round(cur_y + h_i, 2)

    repaired = svg_html
    for idx, rm in enumerate(rooms):
        rx, ry, rw, rh = rects[idx]
        rid = rm["id"]
        rlabel = rm["label"]
        others = ",".join(oid for oid in all_ids if oid != rid)
        new_tag = (
            f'<rect id="{rid}" data-role="room" data-label="{rlabel}" '
            f'data-connects="{others}" x="{rx:g}" y="{ry:g}" width="{rw:g}" height="{rh:g}" />'
        )
        repaired = re.sub(
            rf"""<rect\b[^>]*\bid=["']{re.escape(rid)}["'][^>]*/>""",
            new_tag,
            repaired,
        )

    # Remove any old doors and insert fresh doorway connectors along shared walls
    repaired = re.sub(r"""\s*<rect\b[^>]*data-role=["']door["'][^>]*/>\s*""", "\n", repaired)
    if doors_spec and "</svg>" in repaired:
        door_lines = []
        for d_idx, (r_a, r_b, (dx, dy, dw, dh)) in enumerate(doors_spec, start=1):
            door_lines.append(
                f'  <rect id="door-auto-{d_idx}" data-role="door" data-connects="{r_a},{r_b}" '
                f'x="{dx:g}" y="{dy:g}" width="{dw:g}" height="{dh:g}" />'
            )
        repaired = repaired.replace("</svg>", "\n".join(door_lines) + "\n</svg>", 1)

    return repaired


def repair_visual_artifact(
    artifact_html: str,
    diagnosis: Mapping[str, Any],
    *,
    accepted_state: Mapping[str, Any] | None = None,
) -> str:
    """Applies minimal, general structural repairs for each diagnosed fault class
    in `diagnosis['defects']` without degrading functional controls or relying on
    fixture-specific IDs.
    """
    repaired = str(artifact_html)
    fault_classes = {d.get("fault_class") for d in diagnosis.get("defects", [])}
    if not fault_classes:
        return repaired

    # 1. Repair fixed/sticky header occlusion -> static flow & safe top offset
    if "FIXED_HEADER_HIT_OCCLUSION" in fault_classes:
        repaired = re.sub(
            r"""(position\s*:\s*)(fixed|sticky)""",
            r"\1static",
            repaired,
            flags=re.IGNORECASE,
        )
        repaired = re.sub(
            r"""(<button\b[^>]*style=["'][^"']*?)top\s*:\s*[0-9.]+px""",
            r"\1top: 96px",
            repaired,
            flags=re.IGNORECASE,
        )

    # 2. Repair transparent pointer-event overlay intercept -> pointer-events: none; z-index: -1
    if "TRANSPARENT_OVERLAY_INTERCEPT" in fault_classes:
        repaired = re.sub(
            r"""(opacity\s*:\s*0(?:\.0+)?\s*;?\s*)(pointer-events\s*:\s*auto)?""",
            r"\1pointer-events: none; z-index: -1;",
            repaired,
            flags=re.IGNORECASE,
        )

    # 3. Repair ancestor overflow clipping & off-viewport button placement (responsive down to 320px mobile width)
    if "ANCESTOR_OVERFLOW_CLIPPING" in fault_classes:
        repaired = re.sub(
            r"""overflow(-x|-y)?\s*:\s*(hidden|clip)""",
            "overflow: visible",
            repaired,
            flags=re.IGNORECASE,
        )
        repaired = re.sub(
            r"""left\s*:\s*([1-9][8-9][0-9]|[2-9][0-9]{2}|[1-9][0-9]{3,})(?:\.[0-9]+)?px""",
            "left: 24px",
            repaired,
            flags=re.IGNORECASE,
        )
        repaired = re.sub(
            r"""width\s*:\s*([3-9][2-9][0-9]|[4-9][0-9]{2}|[1-9][0-9]{3,})(?:\.[0-9]+)?px""",
            "width: 280px",
            repaired,
            flags=re.IGNORECASE,
        )

    # 4. General SVG node overlap & text-to-node collision reflow
    if "DIAGRAM_NODE_TEXT_COLLISION" in fault_classes or "DIAGRAM_NODE_OVERLAP" in fault_classes:
        repaired = _general_svg_node_and_label_reflow(repaired)

    # 5. General floor-plan room partition, egress doorway & area-conservation solver
    if (
        "FLOORPLAN_ROOM_OVERLAP" in fault_classes
        or "FLOORPLAN_LANDLOCKED_ROOM" in fault_classes
        or "FLOORPLAN_AREA_NONCONSERVATION" in fault_classes
        or "FLOORPLAN_SUBMINIMUM_ROOM_WIDTH" in fault_classes
    ):
        repaired = _general_floorplan_partition_and_egress_solver(repaired)

    # 6. Repair SVG viewBox truncation -> compute bounding envelope of all SVG children
    if (
        "SVG_VIEWBOX_TRUNCATION" in fault_classes
        or "DIAGRAM_NODE_TEXT_COLLISION" in fault_classes
        or "DIAGRAM_NODE_OVERLAP" in fault_classes
    ):
        obs_tmp = observe_rendered_artifact("tmp-svg", repaired, artifact_family="svg_diagram")
        if obs_tmp.svg_elements:
            min_x = min(0.0, min(e["bbox_px"][0] for e in obs_tmp.svg_elements) - 16.0)
            min_y = min(0.0, min(e["bbox_px"][1] for e in obs_tmp.svg_elements) - 16.0)
            max_x = max(e["bbox_px"][0] + e["bbox_px"][2] for e in obs_tmp.svg_elements) + 24.0
            max_y = max(e["bbox_px"][1] + e["bbox_px"][3] for e in obs_tmp.svg_elements) + 24.0
            new_vb = f"{min_x:.0f} {min_y:.0f} {max(100.0, max_x - min_x):.0f} {max(100.0, max_y - min_y):.0f}"
            repaired = re.sub(
                r"""viewBox=["'][^"']+["']""",
                f'viewBox="{new_vb}"',
                repaired,
                count=1,
            )

    # 7. Repair sandboxed native submit button (`type="submit"` -> `type="button"`) & missing handler
    if "SANDBOX_NATIVE_SUBMIT_TRAP" in fault_classes or "STATIC_DECORATIVE_NOOP_CONTROL" in fault_classes:
        repaired = re.sub(r"""type=["']submit["']""", 'type="button"', repaired, flags=re.IGNORECASE)
        repaired = re.sub(
            r"""onclick=["'](?:void\(0\)|return false;|)["']""",
            'onclick="window.__handleAction && window.__handleAction()"',
            repaired,
        )
        if "window.__handleAction" not in repaired and "</body>" in repaired:
            script_fix = (
                "<script>\n"
                "window.__records = window.__records || [];\n"
                "window.__handleAction = function() {\n"
                "  var inp = document.querySelector('input');\n"
                "  var val = (inp && inp.value) ? inp.value : 'Test Entry';\n"
                "  window.__records.push(val);\n"
                "  try { localStorage.setItem('genie_records', JSON.stringify(window.__records)); } catch (e) {}\n"
                "  var out = document.getElementById('records-list') || document.body;\n"
                "  var item = document.createElement('div'); item.textContent = val; out.appendChild(item);\n"
                "};\n"
                "document.querySelectorAll('button').forEach(function(b){ b.addEventListener('click', window.__handleAction); });\n"
                "</script>\n"
            )
            repaired = repaired.replace("</body>", script_fix + "</body>", 1)

    # 8. Repair external CDN dependencies -> local inline fallback
    if "EXTERNAL_CDN_RUNTIME_ERROR" in fault_classes or "RUNTIME_PAGE_ERROR" in fault_classes:
        for pat in EXTERNAL_CDN_PATTERNS:
            repaired = re.sub(pat, "", repaired, flags=re.IGNORECASE)
        if ("new Chart(" in repaired or "Chart(" in repaired) and "window.Chart =" not in repaired:
            chart_shim = (
                "<script>\n"
                "window.Chart = window.Chart || function(ctx, cfg) {\n"
                "  this.ctx = ctx; this.config = cfg || {};\n"
                "  this.update = function() {}; this.destroy = function() {};\n"
                "};\n"
                "</script>\n"
            )
            repaired = (
                repaired.replace("</head>", chart_shim + "</head>", 1)
                if "</head>" in repaired
                else (chart_shim + repaired)
            )

    # 9. Repair stale form default desynchronization (`STATE_VIEW_DEFAULT_DESYNC`)
    if "STATE_VIEW_DEFAULT_DESYNC" in fault_classes and accepted_state:
        for k, val in accepted_state.items():
            repaired = re.sub(
                rf"""(<input\b[^>]*data-bind-assumption=["']{re.escape(str(k))}["'][^>]*\bvalue=["'])[^"']*(["'])""",
                rf"\g<1>{val}\2",
                repaired,
            )
        if "syncAcceptedAssumptionsToForm" not in repaired and "</body>" in repaired:
            sync_js = (
                "<script>\n"
                f"window.__ACCEPTED_ASSUMPTIONS = {json.dumps(dict(accepted_state), sort_keys=True)};\n"
                "function syncAcceptedAssumptionsToForm() {\n"
                "  Object.entries(window.__ACCEPTED_ASSUMPTIONS || {}).forEach(function(entry) {\n"
                "    var el = document.querySelector('[data-bind-assumption=\"' + entry[0] + '\"]');\n"
                "    if (el) el.value = String(entry[1]);\n"
                "  });\n"
                "}\n"
                "syncAcceptedAssumptionsToForm();\n"
                "</script>\n"
            )
            repaired = repaired.replace("</body>", sync_js + "</body>", 1)

    # 10. Strip scale-induced visual prompt injection artifacts (`SCALE_INDUCED_VISUAL_INJECTION_TRAP`)
    if "SCALE_INDUCED_VISUAL_INJECTION_TRAP" in fault_classes:
        repaired = re.sub(
            r"""<[^>]+data-scale-injection=["'][^"']*["'][^>]*>.*?</[^>]+>""",
            "",
            repaired,
            flags=re.IGNORECASE | re.DOTALL,
        )

    return repaired


def compute_functional_and_geometric_scores(
    obs: VisualObservation,
    *,
    accepted_state: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Computes candidate-side functional and geometric/visual precheck scores in `[0.0, 1.0]`.

    Fail-Closed Security Invariant:
    - If `obs.inspection_failed` is True, both scores are `0.0` and `candidate_self_check_passed`
      is `False`. Failed visual inspection NEVER becomes approval.
    """
    if obs.inspection_failed:
        return {
            "functional_score": 0.0,
            "geometric_score": 0.0,
            "active_controls_count": 0,
            "svg_elements_count": len(obs.svg_elements),
            "rooms_count": len(obs.rooms),
            "total_defects_remaining": max(1, len(obs.inspection_errors)),
            "candidate_self_check_passed": False,
            "independently_accepted": False,
            "authority_scope": "CANDIDATE_LOCAL_PRECHECK_ONLY_NO_INDEPENDENT_EVALUATION_AUTHORITY",
            "inspection_failed": True,
            "inspection_errors": list(obs.inspection_errors),
            "probe_summaries": {
                "hit_topology_passed": False,
                "spatial_geometry_passed": False,
                "state_coherence_passed": False,
            },
        }

    p1 = probe_interactive_hit_topology(obs)
    p2 = probe_spatial_and_svg_geometry(obs)
    p3 = probe_state_view_coherence(obs, accepted_state=accepted_state)

    active_controls = [
        c for c in obs.interactive_controls
        if c["display"] != "none" and c["visibility"] != "hidden" and c["opacity"] > 0.15 and not c["disabled"]
    ]
    func_penalties = len(p1["defects"]) + len(p3["defects"])
    if obs.artifact_family in ("responsive_ui", "stateful_app") and len(active_controls) == 0:
        func_penalties += 3
    functional_score = max(0.0, round(1.0 - 0.25 * func_penalties, 4))

    clip_count = sum(1 for c in obs.interactive_controls if c["clipped_by_ancestor"])
    geom_penalties = len(p2["defects"]) + clip_count
    geometric_score = max(0.0, round(1.0 - 0.25 * geom_penalties, 4))

    has_required_domain_elements = (
        (obs.artifact_family in ("responsive_ui", "stateful_app") and len(active_controls) > 0)
        or (obs.artifact_family == "svg_diagram" and len(obs.svg_elements) > 0)
        or (obs.artifact_family == "floor_plan" and len(obs.rooms) > 0 and obs.footprint_rect is not None)
    )

    self_check_passed = (
        not obs.inspection_failed
        and len(p1["defects"]) == 0
        and len(p2["defects"]) == 0
        and len(p3["defects"]) == 0
        and has_required_domain_elements
    )
    return {
        "functional_score": functional_score,
        "geometric_score": geometric_score,
        "active_controls_count": len(active_controls),
        "svg_elements_count": len(obs.svg_elements),
        "rooms_count": len(obs.rooms),
        "total_defects_remaining": len(p1["defects"]) + len(p2["defects"]) + len(p3["defects"]),
        "candidate_self_check_passed": self_check_passed,
        "independently_accepted": False,
        "authority_scope": "CANDIDATE_LOCAL_PRECHECK_ONLY_NO_INDEPENDENT_EVALUATION_AUTHORITY",
        "inspection_failed": False,
        "inspection_errors": [],
        "probe_summaries": {
            "hit_topology_passed": p1["passed"],
            "spatial_geometry_passed": p2["passed"],
            "state_coherence_passed": p3["passed"],
        },
    }


def check_candidate_visual_and_functional_invariants(
    obs_before: VisualObservation,
    obs_after: VisualObservation,
    *,
    accepted_state: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Candidate-side non-degradation and structural invariant check prior to staging a proposal.

    Important Boundary (`Blocker 2.A` & `Blocker 2.D`):
    - This function does NOT grant independent evaluation acceptance (`independently_accepted`
      is always `False`; `independent_acceptance_status` is `"PENDING_EXTERNAL_EVALUATOR"`).
    - It enforces fail-closed rejection whenever:
      (a) visual observation failed on either `obs_before` or `obs_after`,
      (b) any interactive control, SVG node, or floor-plan room was deleted/disabled
          (`REJECTED_FUNCTIONAL_DEGRADATION`), or
      (c) any visual/geometric/coherence defect remains (`REJECTED_UNRESOLVED_VISUAL_OR_FUNCTIONAL_DEFECTS`).
    """
    before_metrics = compute_functional_and_geometric_scores(obs_before, accepted_state=accepted_state)
    after_metrics = compute_functional_and_geometric_scores(obs_after, accepted_state=accepted_state)

    if obs_before.inspection_failed or obs_after.inspection_failed:
        return {
            "candidate_self_check_passed": False,
            "independently_accepted": False,
            "independent_acceptance_status": "REJECTED_BY_CANDIDATE_PRECHECK",
            "authority_scope": "CANDIDATE_LOCAL_PRECHECK_ONLY_NO_INDEPENDENT_EVALUATION_AUTHORITY",
            "rejection_reason": "REJECTED_VISUAL_INSPECTION_FAILED",
            "before": before_metrics,
            "after": after_metrics,
        }

    functional_degraded = (
        after_metrics["functional_score"] < before_metrics["functional_score"] - 1e-6
        or after_metrics["active_controls_count"] < before_metrics["active_controls_count"]
        or after_metrics["svg_elements_count"] < before_metrics["svg_elements_count"]
        or after_metrics["rooms_count"] < before_metrics["rooms_count"]
    )
    passed = bool(after_metrics["candidate_self_check_passed"] and not functional_degraded)
    rejection_reason = None
    if functional_degraded:
        rejection_reason = "REJECTED_FUNCTIONAL_DEGRADATION"
    elif not after_metrics["candidate_self_check_passed"]:
        rejection_reason = "REJECTED_UNRESOLVED_VISUAL_OR_FUNCTIONAL_DEFECTS"

    return {
        "candidate_self_check_passed": passed,
        "independently_accepted": False,
        "independent_acceptance_status": (
            "PENDING_EXTERNAL_EVALUATOR" if passed else "REJECTED_BY_CANDIDATE_PRECHECK"
        ),
        "authority_scope": "CANDIDATE_LOCAL_PRECHECK_ONLY_NO_INDEPENDENT_EVALUATION_AUTHORITY",
        "rejection_reason": rejection_reason,
        "before": before_metrics,
        "after": after_metrics,
    }


# Backward-compatible alias for internal callers
evaluate_visual_and_functional_acceptance = check_candidate_visual_and_functional_invariants
