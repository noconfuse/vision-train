import math


def _remove_near_duplicates(points, min_dist=0.5):
    pts = []
    for p in points or []:
        x = float(p[0])
        y = float(p[1])
        if not pts:
            pts.append((x, y))
            continue
        lx, ly = pts[-1]
        if math.hypot(x - lx, y - ly) >= float(min_dist):
            pts.append((x, y))
    if len(pts) >= 2:
        fx, fy = pts[0]
        lx, ly = pts[-1]
        if math.hypot(fx - lx, fy - ly) < float(min_dist):
            pts.pop()
    return pts


def _polygon_perimeter(points):
    pts = points or []
    if len(pts) < 2:
        return 0.0
    peri = 0.0
    for idx, (x1, y1) in enumerate(pts):
        x2, y2 = pts[(idx + 1) % len(pts)]
        peri += math.hypot(x2 - x1, y2 - y1)
    return peri


def _resample_closed_polygon(points, spacing_px):
    pts = _remove_near_duplicates(points, min_dist=0.5)
    if len(pts) < 3:
        return pts
    spacing = max(1.0, float(spacing_px))
    peri = _polygon_perimeter(pts)
    if not math.isfinite(peri) or peri <= 0:
        return pts
    target_count = max(3, int(round(peri / spacing)))
    step = peri / float(target_count)
    if not math.isfinite(step) or step <= 0:
        return pts

    out = []
    cur_seg = 0
    cur_dist = 0.0
    for k in range(target_count):
        target = k * step
        guard = 0
        while cur_seg < len(pts) and guard < len(pts) * 2:
            guard += 1
            x1, y1 = pts[cur_seg]
            x2, y2 = pts[(cur_seg + 1) % len(pts)]
            seg_len = math.hypot(x2 - x1, y2 - y1)
            if seg_len <= 0:
                cur_seg += 1
                continue
            if cur_dist + seg_len >= target:
                t = (target - cur_dist) / seg_len
                out.append((x1 + (x2 - x1) * t, y1 + (y2 - y1) * t))
                break
            cur_dist += seg_len
            cur_seg += 1
    return _remove_near_duplicates(out, min_dist=0.1)


def _parse_points_to_pixels(points, width, height):
    pts = []
    deduped = []
    for p in points or []:
        x = float(p.get("x") if isinstance(p, dict) else p[0])
        y = float(p.get("y") if isinstance(p, dict) else p[1])
        if 0.0 <= x <= 1.0 and 0.0 <= y <= 1.0:
            px = int(round(x * (width - 1)))
            py = int(round(y * (height - 1)))
        else:
            px = int(round(x))
            py = int(round(y))
        px = max(0, min(width - 1, px))
        py = max(0, min(height - 1, py))
        pts.append((px, py))
    for px, py in pts:
        if not deduped:
            deduped.append((px, py))
            continue
        lx, ly = deduped[-1]
        if math.hypot(px - lx, py - ly) >= 1.0:
            deduped.append((px, py))
    if len(deduped) >= 2:
        fx, fy = deduped[0]
        lx, ly = deduped[-1]
        if math.hypot(fx - lx, fy - ly) < 1.0:
            deduped.pop()
    return deduped


def _build_ridge_response(image, kernel_size=13):
    import cv2
    import numpy as np

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    kernel = np.ones((int(kernel_size), int(kernel_size)), np.uint8)
    blackhat = cv2.morphologyEx(blur, cv2.MORPH_BLACKHAT, kernel)
    ridge = cv2.normalize(blackhat, None, 0, 255, cv2.NORM_MINMAX)
    return gray, ridge


def _collect_patch_indices(points, point_idx, radius_px):
    pts = points or []
    total = len(pts)
    if total < 3 or point_idx < 0 or point_idx >= total:
        return [], {}

    distances = {int(point_idx): 0.0}
    backward = [int(point_idx)]
    dist = 0.0
    cur = int(point_idx)
    for _ in range(total - 1):
        prev_idx = (cur - 1 + total) % total
        dist += math.hypot(pts[cur][0] - pts[prev_idx][0], pts[cur][1] - pts[prev_idx][1])
        if dist > float(radius_px):
            break
        backward.append(prev_idx)
        distances[prev_idx] = min(distances.get(prev_idx, float("inf")), dist)
        cur = prev_idx

    forward = [int(point_idx)]
    dist = 0.0
    cur = int(point_idx)
    for _ in range(total - 1):
        next_idx = (cur + 1) % total
        dist += math.hypot(pts[cur][0] - pts[next_idx][0], pts[cur][1] - pts[next_idx][1])
        if dist > float(radius_px):
            break
        forward.append(next_idx)
        distances[next_idx] = min(distances.get(next_idx, float("inf")), dist)
        cur = next_idx

    ordered = list(reversed(backward[1:])) + [int(point_idx)] + forward[1:]
    return ordered, distances


def _snap_point_to_ridge(pt, ridge, radius_px=6):
    height, width = ridge.shape[:2]
    x = max(0, min(width - 1, int(round(float(pt[0])))))
    y = max(0, min(height - 1, int(round(float(pt[1])))))
    radius = max(1, int(round(float(radius_px or 6))))

    best_x = x
    best_y = y
    best_score = float(ridge[y, x]) if 0 <= y < height and 0 <= x < width else 0.0
    for dy in range(-radius, radius + 1):
        yy = y + dy
        if yy < 0 or yy >= height:
            continue
        for dx in range(-radius, radius + 1):
            xx = x + dx
            if xx < 0 or xx >= width:
                continue
            dist = math.hypot(dx, dy)
            score = float(ridge[yy, xx]) - dist * 4.0
            if score > best_score:
                best_score = score
                best_x = xx
                best_y = yy
    return float(best_x), float(best_y)


def refine_polygon_with_grabcut(image_path, stroke_points, spacing_px=10, iterations=3, snap_radius_px=6):
    try:
        import cv2
        import numpy as np
    except Exception as exc:
        raise ValueError("当前环境缺少 OpenCV，无法执行传统分割拟合") from exc

    image = cv2.imread(str(image_path))
    if image is None:
        raise ValueError("无法读取图片")
    height, width = image.shape[:2]
    pts = _parse_points_to_pixels(stroke_points, width, height)
    if len(pts) < 3:
        raise ValueError("包围轨迹过短")

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    blackhat = cv2.morphologyEx(blur, cv2.MORPH_BLACKHAT, np.ones((13, 13), np.uint8))
    ridge = cv2.normalize(blackhat, None, 0, 255, cv2.NORM_MINMAX)

    roi_mask = np.zeros((height, width), dtype=np.uint8)
    contour = np.array(pts, dtype=np.int32).reshape((-1, 1, 2))
    cv2.fillPoly(roi_mask, [contour], 255)
    roi_area = int(np.count_nonzero(roi_mask))
    if roi_area < 16:
        raise ValueError("包围区域过小")
    ys, xs = np.where(roi_mask > 0)
    roi_x1 = int(xs.min())
    roi_y1 = int(ys.min())
    roi_x2 = int(xs.max()) + 1
    roi_y2 = int(ys.max()) + 1
    roi_w = max(1, roi_x2 - roi_x1)
    roi_h = max(1, roi_y2 - roi_y1)

    roi_ridge = ridge[roi_mask > 0]
    roi_gray = gray[roi_mask > 0]
    if roi_ridge.size < 1 or roi_gray.size < 1:
        raise ValueError("引导区域无效")
    darkness = (255.0 - gray.astype(np.float32))
    response = ridge.astype(np.float32) * 0.68 + darkness * 0.32
    roi_response = response[roi_mask > 0]

    ridge_strong_thr = float(np.percentile(roi_ridge, 90))
    ridge_mid_thr = float(np.percentile(roi_ridge, 76))
    dark_thr = float(np.percentile(roi_gray, 30))
    response_thr = float(np.percentile(roi_response, 86))
    candidate = (
        (
            (ridge >= ridge_strong_thr)
            | (response >= response_thr)
            | ((gray <= dark_thr) & (ridge >= ridge_mid_thr))
        )
        & (roi_mask > 0)
    ).astype(np.uint8) * 255

    work = cv2.morphologyEx(candidate, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8), iterations=max(1, min(2, int(iterations))))
    work = cv2.morphologyEx(work, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8), iterations=1)
    work = cv2.bitwise_and(work, roi_mask)

    inner_margin = max(4, int(round(min(roi_w, roi_h) * 0.12)))
    inner_mask = cv2.erode(
        roi_mask,
        np.ones((inner_margin * 2 + 1, inner_margin * 2 + 1), np.uint8),
        iterations=1,
    )
    if np.count_nonzero(inner_mask) < 8:
        inner_mask = roi_mask.copy()

    seed_y, seed_x = np.unravel_index(np.argmax(np.where(inner_mask > 0, response, -1.0)), response.shape)
    seed_mask = np.zeros((height, width), dtype=np.uint8)
    seed_radius = max(6, int(round(min(roi_w, roi_h) * 0.08)))
    cv2.circle(seed_mask, (int(seed_x), int(seed_y)), seed_radius, 255, -1)

    _num_labels, labels, stats, _centroids = cv2.connectedComponentsWithStats(work, connectivity=8)
    keep = np.zeros((height, width), dtype=np.uint8)
    min_area = max(6, int(round(roi_area * 0.00015)))
    border_band = cv2.subtract(roi_mask, cv2.erode(roi_mask, np.ones((5, 5), np.uint8), iterations=1))
    best_label = 0
    best_score = -1e18
    for label_id in range(1, int(_num_labels)):
        area = int(stats[label_id, cv2.CC_STAT_AREA])
        if area < min_area:
            continue
        w = int(stats[label_id, cv2.CC_STAT_WIDTH])
        h = int(stats[label_id, cv2.CC_STAT_HEIGHT])
        if w < 2 or h < 2:
            continue
        comp_mask = labels == label_id
        aspect = max(w, h) / max(1.0, float(min(w, h)))
        fill_ratio = area / max(1.0, float(w * h))
        area_ratio = area / max(1.0, float(roi_area))
        mean_ridge = float(ridge[comp_mask].mean())
        mean_dark = float(darkness[comp_mask].mean())
        border_ratio = float(np.count_nonzero(comp_mask & (border_band > 0))) / max(1.0, float(area))
        touches_seed = bool(np.any(comp_mask & (seed_mask > 0)))
        cx = float(stats[label_id, cv2.CC_STAT_LEFT] + w / 2.0)
        cy = float(stats[label_id, cv2.CC_STAT_TOP] + h / 2.0)
        center_dist = math.hypot(cx - float(seed_x), cy - float(seed_y))
        score = 0.0
        score += 600.0 if touches_seed else 0.0
        score += mean_ridge * 2.2
        score += mean_dark * 0.6
        score += aspect * 42.0
        score -= fill_ratio * 180.0
        score -= area_ratio * 220.0
        score -= border_ratio * 260.0
        score -= center_dist * 0.45
        if score > best_score:
            best_score = score
            best_label = label_id

    if best_label > 0:
        keep[labels == best_label] = 255
        grown = cv2.dilate(keep, np.ones((5, 5), np.uint8), iterations=1)
        for label_id in range(1, int(_num_labels)):
            if label_id == best_label:
                continue
            comp_mask = (labels == label_id)
            if not np.any(comp_mask):
                continue
            if np.any(comp_mask & (grown > 0)):
                comp_ridge = float(ridge[comp_mask].mean())
                comp_area = int(stats[label_id, cv2.CC_STAT_AREA])
                if comp_area >= min_area and comp_ridge >= ridge_mid_thr:
                    keep[comp_mask] = 255

    if np.count_nonzero(keep) == 0:
        seed_labels = set(int(v) for v in labels[seed_mask > 0].tolist() if int(v) > 0)
        for label_id in seed_labels:
            keep[labels == label_id] = 255
    if np.count_nonzero(keep) == 0:
        keep = cv2.bitwise_and(candidate, cv2.dilate(seed_mask, np.ones((9, 9), np.uint8), iterations=1))
    if np.count_nonzero(keep) == 0:
        keep = candidate

    keep = cv2.morphologyEx(keep, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8), iterations=1)
    keep = cv2.dilate(keep, np.ones((3, 3), np.uint8), iterations=1)
    keep = cv2.bitwise_and(keep, roi_mask)

    fg_mask = keep

    contours, _hier = cv2.findContours(fg_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    if not contours:
        raise ValueError("未找到可用轮廓")
    contours = sorted(contours, key=cv2.contourArea, reverse=True)
    best = contours[0]
    if cv2.contourArea(best) <= 0:
        raise ValueError("未找到可用轮廓")

    raw = [(float(p[0][0]), float(p[0][1])) for p in best]
    resampled = _resample_closed_polygon(raw, spacing_px=spacing_px)
    if len(resampled) < 3:
        raise ValueError("轮廓解析失败")
    return {
        "width": width,
        "height": height,
        "points": [{"x": float(x), "y": float(y)} for x, y in resampled],
    }


def refine_polygon_boundary_patch(
    image_path,
    polygon_points,
    point_idx,
    target_point,
    spacing_px=10,
    patch_arc_px=56,
    snap_radius_px=8,
):
    try:
        import cv2
    except Exception as exc:
        raise ValueError("当前环境缺少 OpenCV，无法执行局部边界精修") from exc

    image = cv2.imread(str(image_path))
    if image is None:
        raise ValueError("无法读取图片")
    height, width = image.shape[:2]
    polygon_pts = _parse_points_to_pixels(polygon_points, width, height)
    if len(polygon_pts) < 3:
        raise ValueError("当前多边形无效")

    point_idx = int(point_idx)
    if point_idx < 0 or point_idx >= len(polygon_pts):
        raise ValueError("边界点索引无效")

    target_pts = _parse_points_to_pixels([target_point], width, height)
    if len(target_pts) != 1:
        raise ValueError("目标点无效")
    target_px = target_pts[0]

    patch_indices, arc_dist = _collect_patch_indices(polygon_pts, point_idx, radius_px=patch_arc_px)
    if len(patch_indices) < 3:
        raise ValueError("局部边界片段过短")

    _, ridge = _build_ridge_response(image, kernel_size=13)

    center = polygon_pts[point_idx]
    drag_vec = (float(target_px[0] - center[0]), float(target_px[1] - center[1]))
    drag_len = math.hypot(drag_vec[0], drag_vec[1])
    if drag_len <= 0.5:
        return {
            "width": width,
            "height": height,
            "points": [{"x": float(x), "y": float(y)} for x, y in polygon_pts],
        }

    max_disp = max(12.0, float(patch_arc_px) * 0.9)
    if drag_len > max_disp:
        scale = max_disp / drag_len
        drag_vec = (drag_vec[0] * scale, drag_vec[1] * scale)

    updated = list((float(x), float(y)) for x, y in polygon_pts)
    patch_radius = max(16.0, float(patch_arc_px))
    for idx in patch_indices:
        distance = float(arc_dist.get(idx, float("inf")))
        if not math.isfinite(distance) or distance > patch_radius:
            continue
        weight = 0.5 * (1.0 + math.cos(math.pi * min(1.0, distance / patch_radius)))
        base = updated[idx]
        moved = (
            base[0] + drag_vec[0] * weight,
            base[1] + drag_vec[1] * weight,
        )
        snapped = _snap_point_to_ridge(moved, ridge, radius_px=snap_radius_px)
        blend = 0.82 if idx == point_idx else 0.45 * weight
        updated[idx] = (
            moved[0] * (1.0 - blend) + snapped[0] * blend,
            moved[1] * (1.0 - blend) + snapped[1] * blend,
        )

    resampled = _resample_closed_polygon(updated, spacing_px=spacing_px)
    if len(resampled) < 3:
        raise ValueError("局部边界精修失败")
    return {
        "width": width,
        "height": height,
        "points": [{"x": float(x), "y": float(y)} for x, y in resampled],
    }


def erase_polygon_with_stroke(
    image_path,
    polygon_points,
    stroke_points,
    spacing_px=10,
    stroke_width_px=12,
):
    try:
        import cv2
        import numpy as np
    except Exception as exc:
        raise ValueError("当前环境缺少 OpenCV，无法执行橡皮擦微调") from exc

    image = cv2.imread(str(image_path))
    if image is None:
        raise ValueError("无法读取图片")
    height, width = image.shape[:2]
    polygon_pts = _parse_points_to_pixels(polygon_points, width, height)
    stroke_pts = _parse_points_to_pixels(stroke_points, width, height)
    if len(polygon_pts) < 3:
        raise ValueError("当前多边形无效")
    if len(stroke_pts) < 2:
        raise ValueError("橡皮擦轨迹过短")

    stroke_width_px = int(round(float(stroke_width_px or 12)))
    stroke_width_px = max(3, stroke_width_px)
    effective_width_px = max(3, int(round(float(stroke_width_px) * 0.7)))

    poly_mask = np.zeros((height, width), dtype=np.uint8)
    cv2.fillPoly(poly_mask, [np.array(polygon_pts, dtype=np.int32).reshape((-1, 1, 2))], 255)

    erase_mask = np.zeros((height, width), dtype=np.uint8)
    cv2.polylines(
        erase_mask,
        [np.array(stroke_pts, dtype=np.int32).reshape((-1, 1, 2))],
        isClosed=False,
        color=255,
        thickness=effective_width_px,
    )
    if effective_width_px >= 6:
        erase_mask = cv2.dilate(erase_mask, np.ones((3, 3), np.uint8), iterations=1)
    erase_mask = cv2.bitwise_and(erase_mask, poly_mask)

    gray, ridge = _build_ridge_response(image, kernel_size=13)
    ridge_vals = ridge[poly_mask > 0]
    protect_thr = float(np.percentile(ridge_vals, 88)) if ridge_vals.size else 255.0
    protect = (ridge >= protect_thr).astype(np.uint8) * 255
    erase_mask = cv2.bitwise_and(erase_mask, cv2.bitwise_not(protect))

    kept = cv2.bitwise_and(poly_mask, cv2.bitwise_not(erase_mask))
    ys, xs = np.where(erase_mask > 0)
    if ys.size > 0 and xs.size > 0:
        margin = max(10, int(round(float(stroke_width_px) * 1.2)))
        x1 = int(max(0, int(xs.min()) - margin))
        y1 = int(max(0, int(ys.min()) - margin))
        x2 = int(min(width, int(xs.max()) + margin + 1))
        y2 = int(min(height, int(ys.max()) + margin + 1))
        patch = kept[y1:y2, x1:x2].copy()
        patch = cv2.morphologyEx(patch, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8), iterations=1)
        kept[y1:y2, x1:x2] = patch

    contours, _hier = cv2.findContours(kept, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    if not contours:
        return {"width": width, "height": height, "polygons": []}

    polys = []
    min_area = max(10, int(round(float(stroke_width_px) * float(stroke_width_px) * 0.5)))
    for c in contours:
        area = float(cv2.contourArea(c))
        if area < float(min_area):
            continue
        raw = [(float(p[0][0]), float(p[0][1])) for p in c]
        resampled = _resample_closed_polygon(raw, spacing_px=spacing_px)
        if len(resampled) < 3:
            continue
        polys.append({"points": [{"x": float(x), "y": float(y)} for x, y in resampled], "area": area})

    polys = sorted(polys, key=lambda item: float(item.get("area") or 0.0), reverse=True)
    for item in polys:
        item.pop("area", None)
    return {"width": width, "height": height, "polygons": polys}


def repair_polygon_with_local_grabcut(
    image_path,
    polygon_points,
    stroke_points,
    mode="expand",
    spacing_px=10,
    iterations=2,
    stroke_width_px=12,
    margin_px=64,
):
    try:
        import cv2
        import numpy as np
    except Exception as exc:
        raise ValueError("当前环境缺少 OpenCV，无法执行局部分割修正") from exc

    image = cv2.imread(str(image_path))
    if image is None:
        raise ValueError("无法读取图片")
    height, width = image.shape[:2]
    stroke_width_px = int(round(float(stroke_width_px or 12)))
    margin_px = int(round(float(margin_px or 64)))

    polygon_pts = _parse_points_to_pixels(polygon_points, width, height)
    stroke_pts = _parse_points_to_pixels(stroke_points, width, height)
    if len(polygon_pts) < 3:
        raise ValueError("当前多边形无效")
    if len(stroke_pts) < 2:
        raise ValueError("局部修正轨迹过短")

    full_mask = np.zeros((height, width), dtype=np.uint8)
    cv2.fillPoly(full_mask, [np.array(polygon_pts, dtype=np.int32).reshape((-1, 1, 2))], 255)
    stroke_mask = np.zeros((height, width), dtype=np.uint8)
    cv2.polylines(
        stroke_mask,
        [np.array(stroke_pts, dtype=np.int32).reshape((-1, 1, 2))],
        isClosed=False,
        color=255,
        thickness=max(3, stroke_width_px),
    )
    seed_mask = cv2.dilate(stroke_mask, np.ones((5, 5), np.uint8), iterations=1)

    xs = [p[0] for p in stroke_pts]
    ys = [p[1] for p in stroke_pts]
    x1 = int(max(0, min(xs) - margin_px))
    y1 = int(max(0, min(ys) - margin_px))
    x2 = int(min(width, max(xs) + margin_px + 1))
    y2 = int(min(height, max(ys) + margin_px + 1))
    if x2 - x1 < 8 or y2 - y1 < 8:
        raise ValueError("局部修正区域过小")

    crop = image[y1:y2, x1:x2]
    crop_existing = full_mask[y1:y2, x1:x2]
    crop_seed = seed_mask[y1:y2, x1:x2]
    crop_stroke = stroke_mask[y1:y2, x1:x2]
    h, w = crop.shape[:2]

    mode = str(mode or "expand").strip().lower()
    if mode not in {"expand", "shrink"}:
        mode = "expand"

    local_mask = np.full((h, w), cv2.GC_BGD, dtype=np.uint8)
    corridor_r = max(8, int(round(float(stroke_width_px) * 2.0)))
    corridor_kernel = np.ones((corridor_r * 2 + 1, corridor_r * 2 + 1), np.uint8)
    corridor = cv2.dilate(crop_stroke, corridor_kernel, iterations=1)
    local_mask[corridor > 0] = cv2.GC_PR_BGD
    local_mask[cv2.bitwise_and(crop_existing, corridor) > 0] = cv2.GC_PR_FGD

    if mode == "expand":
        local_mask[crop_seed > 0] = cv2.GC_FGD
        sure_existing = cv2.erode(crop_existing, np.ones((3, 3), np.uint8), iterations=1)
        local_mask[cv2.bitwise_and(sure_existing, corridor) > 0] = cv2.GC_FGD
    else:
        local_mask[crop_seed > 0] = cv2.GC_BGD
        safe_keep = cv2.erode(crop_existing, np.ones((5, 5), np.uint8), iterations=1)
        safe_keep = cv2.bitwise_and(safe_keep, cv2.bitwise_not(corridor))
        local_mask[safe_keep > 0] = cv2.GC_FGD

    border = np.zeros((h, w), dtype=np.uint8)
    border[0, :] = 255
    border[-1, :] = 255
    border[:, 0] = 255
    border[:, -1] = 255
    local_mask[border > 0] = cv2.GC_BGD

    bgd_model = np.zeros((1, 65), np.float64)
    fgd_model = np.zeros((1, 65), np.float64)
    cv2.grabCut(crop, local_mask, None, bgd_model, fgd_model, int(iterations), cv2.GC_INIT_WITH_MASK)

    local_fg = np.where((local_mask == cv2.GC_FGD) | (local_mask == cv2.GC_PR_FGD), 255, 0).astype("uint8")
    if mode == "expand":
        local_fg = cv2.bitwise_or(local_fg, crop_existing)
        local_fg = cv2.bitwise_or(local_fg, crop_stroke)
    else:
        local_fg = cv2.bitwise_and(local_fg, crop_existing)
    local_fg = cv2.morphologyEx(local_fg, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8), iterations=1)
    local_fg = cv2.bitwise_and(local_fg, corridor)

    merged = full_mask.copy()
    patch = merged[y1:y2, x1:x2].copy()
    patch[corridor > 0] = local_fg[corridor > 0]
    merged[y1:y2, x1:x2] = patch

    contours, _hier = cv2.findContours(merged, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    if not contours:
        raise ValueError("未找到可用轮廓")
    best = max(contours, key=cv2.contourArea)
    if cv2.contourArea(best) <= 0:
        raise ValueError("未找到可用轮廓")
    raw = [(float(p[0][0]), float(p[0][1])) for p in best]
    resampled = _resample_closed_polygon(raw, spacing_px=spacing_px)
    if len(resampled) < 3:
        raise ValueError("轮廓解析失败")
    return {
        "width": width,
        "height": height,
        "points": [{"x": float(x), "y": float(y)} for x, y in resampled],
    }
