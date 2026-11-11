"""近似重复帧的判据：dHash 指纹 + 汉明距离分组。

参数沿用 scripts/curate_ppe_dataset.py 在一万三千张高空作业图上跑通的那一套：
8×9 灰度相邻像素差分 → 64 bit 指纹，汉明距离 ≤ 6 归为一组。
实测单张 640×640 jpg 指纹 2.9 ms（含解码），所以按页现算不慢。

它只回答「像不像」，回答不了「是不是同一个东西」：连拍帧、同一镜头的轻微位移在这里
长一样，但每张图该判成什么还得各判各的，所以这份判据只用于列表折叠显示。
"""

DHASH_SIZE = 8
# 与离线整理脚本的 --dup-threshold 默认值一致
NEAR_DUPLICATE_THRESHOLD = 6


def image_dhash(image_path, size=DHASH_SIZE):
    """算一张图的 dHash 指纹；图片读不出来返回 None（坏图不参与相似判断）。"""
    from PIL import Image

    try:
        with Image.open(image_path) as image:
            gray = image.convert("L").resize((size + 1, size), Image.BILINEAR)
            pixels = gray.tobytes()
    except Exception:
        return None
    bits = 0
    stride = size + 1
    for row in range(size):
        offset = row * stride
        for col in range(size):
            bits = (bits << 1) | (1 if pixels[offset + col] > pixels[offset + col + 1] else 0)
    return bits


def hamming_distance(left, right):
    """两个指纹差几个比特；64 bit 里差得越少越像。"""
    return (int(left) ^ int(right)).bit_count()


def group_by_distance(values, threshold=NEAR_DUPLICATE_THRESHOLD):
    """把一组指纹按「汉明距离 ≤ threshold」连通成组，返回每个位置所属的组号。

    组号按首次出现顺序从 0 递增；指纹缺失（None）的图各自单独成组，绝不并进别人的组。
    两两比要 N² 次，所以先把指纹切成 8 段各 8 bit 做候选粗筛，再对候选逐条比真实距离，
    与离线脚本同一套做法——同一批图在两边分出来的组一致。
    """
    values = list(values or [])
    parent = list(range(len(values)))

    def find(node):
        while parent[node] != node:
            parent[node] = parent[parent[node]]
            node = parent[node]
        return node

    def union(left, right):
        left_root, right_root = find(left), find(right)
        if left_root != right_root:
            parent[max(left_root, right_root)] = min(left_root, right_root)

    band_bits = 8
    bands = {}
    for index, value in enumerate(values):
        if value is None:
            continue
        for band in range(DHASH_SIZE):
            key = (band, (int(value) >> (band * band_bits)) & 0xFF)
            bands.setdefault(key, []).append(index)
    for indices in bands.values():
        for position, index in enumerate(indices):
            for other in indices[position + 1:]:
                if hamming_distance(values[index], values[other]) <= threshold:
                    union(index, other)

    group_of = {}
    for index in range(len(values)):
        root = find(index)
        if root not in group_of:
            group_of[root] = len(group_of)
    return [group_of[find(index)] for index in range(len(values))]
