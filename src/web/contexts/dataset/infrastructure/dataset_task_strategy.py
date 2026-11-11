"""按数据集任务类型封装数据集读写策略。"""

import os
import shutil
import tempfile

from constants.media import IMAGE_FILE_EXTENSIONS
from contexts.dataset.infrastructure.dataset_layout import (
    STANDARD_DATASET_SPLITS,
    DATASET_SPLIT_TRAIN,
    build_label_relpath,
    extract_classification_class_name,
    get_dataset_auto_labels_dir,
    get_dataset_auto_meta_path,
    get_dataset_images_dir,
    get_dataset_labels_dir,
    get_dataset_legacy_labels_dir,
    get_dataset_split_dir,
    get_dataset_unlabeled_dir,
    normalize_standard_dataset_split,
    resolve_existing_label_path_for_image,
)
from contexts.dataset.infrastructure.overlapping_labels import (
    count_redundant_boxes,
    parse_label_line,
    to_xyxy_box,
)
from protocols.vision_task_type import (
    VISION_TASK_TYPE_CLASSIFY,
    VISION_TASK_TYPE_DETECT,
    VISION_TASK_TYPE_POSE,
    VISION_TASK_TYPE_SEGMENT,
)
from shared.utils.fs_utils import allocate_nonconflicting_path, is_system_hidden_file, is_within_path, move_path, remove_dir_if_empty, remove_empty_dirs_up_to, remove_file_silent, resolve_safe_child_path
from shared.utils.path_utils import resolve_relative_child_path, resolve_storage_path, validate_filename
from shared.utils.zip_utils import split_archive_filename, safe_extract_archive


class BaseDatasetTaskStrategy:
    """定义数据集任务类型策略基类。"""

    vision_task_type = ""

    def _save_upload_payload(self, target_dir, files):
        """把上传的图片 / 压缩包保存到 ``target_dir``，返回已保存文件路径列表。

        单张图片：直接保存。压缩包（zip/tar/tar.gz/tgz）：安全解压后递归
        抽取所有支持后缀的图片复制到 ``target_dir``。

        跳过 macOS 资源分叉 ``._*`` 与常见的系统隐藏文件（``Thumbs.db`` 等），
        避免它们被当成普通图片入库、后续在前端展示时呈现为坏图。
        """
        os.makedirs(target_dir, exist_ok=True)
        saved = []
        for file in files:
            try:
                split_archive_filename(file.filename)
            except ValueError:
                if is_system_hidden_file(file.filename):
                    continue
                try:
                    filename = validate_filename(
                        file.filename,
                        allowed_extensions=IMAGE_FILE_EXTENSIONS,
                        field_name="图片名",
                    )
                except ValueError:
                    continue
                dst = allocate_nonconflicting_path(os.path.join(target_dir, filename))
                file.save(dst)
                saved.append(dst)
                continue

            with tempfile.TemporaryDirectory() as staging:
                staging_zip = os.path.join(staging, "_archive")
                file.save(staging_zip)
                extract_dir = os.path.join(staging, "extracted")
                os.makedirs(extract_dir, exist_ok=True)
                try:
                    safe_extract_archive(staging_zip, extract_dir, original_name=file.filename)
                except Exception:
                    continue
                for sub_root, _dirs, sub_files in os.walk(extract_dir):
                    for name in sub_files:
                        if is_system_hidden_file(name):
                            continue
                        if not name.lower().endswith(IMAGE_FILE_EXTENSIONS):
                            continue
                        src = os.path.join(sub_root, name)
                        dst = allocate_nonconflicting_path(os.path.join(target_dir, name))
                        shutil.copyfile(src, dst)
                        saved.append(dst)
        return saved

    def copy_subset_sample(self, *_args, **_kwargs):
        """把一张样本复制到新子集，返回是否复制成功。"""
        raise NotImplementedError

    def build_image_record(self, *_args, **_kwargs):
        """把单张图片解析为列表接口消费的统一记录。"""
        raise NotImplementedError

    def upload_images(self, *_args, **_kwargs):
        """执行当前任务类型支持的图片上传逻辑。"""
        raise NotImplementedError

    def iter_list_image_paths(self, *_args, **_kwargs):
        """按列表筛选条件返回当前任务类型可见的图片路径。"""
        raise NotImplementedError

    def resolve_image_relative_path(self, *_args, **_kwargs):
        """把绝对图片路径解析为当前任务类型可识别的相对路径。"""
        raise NotImplementedError

    def delete_image(self, *_args, **_kwargs):
        """删除一张图片及其关联标注产物。"""
        raise NotImplementedError

    def move_image(self, *_args, **_kwargs):
        """把一张图片及其关联标注产物搬到目标 split。"""
        raise NotImplementedError

    def _resolve_move_target_split(self, split, target_split):
        """校验移动的目标 split：必须是标准 split，且不能就是当前 split。"""
        target = normalize_standard_dataset_split(target_split)
        if target == str(split or "").strip().lower():
            raise ValueError("目标 split 与图片当前所在 split 相同")
        return target

    def _raise_if_move_conflict(self, target_image_path, image_rel, target_split):
        """目标 split 已有同名图片时拒绝移动，避免覆盖别人的标签或凭空多出副本。"""
        if os.path.exists(target_image_path):
            raise ValueError(
                f"{target_split} 中已存在同名图片 {os.path.basename(str(image_rel))}，请先重命名或删除那边的同名文件"
            )

    def delete_duplicate_image(self, *_args, **_kwargs):
        """删除重复图片，并完成该任务类型要求的后置清理。"""
        raise NotImplementedError

    def resolve_deduplicate_label_paths(self, dataset_root, split, rel_noext):
        """返回去重时需要一并清理的关联标签文件列表。"""
        auto_dir = get_dataset_auto_labels_dir(dataset_root, split)
        auto_path = os.path.join(auto_dir, build_label_relpath(rel_noext))
        return [auto_path, get_dataset_auto_meta_path(auto_path, auto_dir)]

    def count_overlapping_boxes(self, dataset_root, split, image_path):
        """这张图里有几个「被同类另一个框盖住九成以上」的框。

        判据建立在 YOLO 检测框（class + 4 个数）之上：分类任务没有标签文件，
        分割 / 姿态的多边形行解析不成检测框，所以都数不出冗余框。
        """
        del dataset_root, split, image_path
        return 0

    def list_pending_boxes(self, dataset_root, split, image_ref):
        """走查列表要的候选框几何（归一化 x1y1x2y2）。

        只有检测任务画得出框：分割/姿态的标签行不是框，分类整图一个判断，
        这三种就靠列表上的「待复核」点标，不在缩略图上画。
        """
        del dataset_root, split, image_ref
        return []

    def list_label_boxes(self, dataset_root, split, image_ref):
        """走查列表要的人工标签框几何（归一化 x1y1x2y2）。

        和 ``list_pending_boxes`` 同一条收口：只有检测任务画得出框，其余任务类型返回空。
        """
        del dataset_root, split, image_ref
        return []

    def ensure_label_dirs(self, _dataset_root, _label_name):
        """新增分类时按需创建附属产物目录（如分类任务的 split 类别子目录）。

        默认实现为 no-op：检测/分割/姿态任务仅在 ``dataset.yaml`` 中维护 ``names``，
        不会因新增分类在文件系统里产生额外产物。
        """
        return []

    def remove_label_dirs(self, _dataset_root, _label_name):
        """删除分类时按需清理附属产物目录。

        返回 ``{"removed_dirs": [...], "skipped_dirs": [...]}``：
        ``removed_dirs`` 是实际删除的目录；``skipped_dirs`` 记录因仍有内容等原因
        被跳过的目录（如分类任务下该类还有未迁移图片，删除会被拒绝）。

        默认 no-op。
        """
        return {"removed_dirs": [], "skipped_dirs": []}

    def build_dataset_summary_metadata(self, _dataset_root, _data_config):
        """返回任务专属的数据集摘要元信息。"""
        return {}


class DetectDatasetTaskStrategy(BaseDatasetTaskStrategy):
    """目标检测数据集策略。"""

    vision_task_type = VISION_TASK_TYPE_DETECT

    def _resolve_source_image_root(self, dataset_root, image_path):
        """根据图片路径定位其所属的检测 split/images 根目录。"""
        for split in STANDARD_DATASET_SPLITS:
            img_dir = get_dataset_images_dir(dataset_root, split)
            if is_within_path(image_path, img_dir):
                return img_dir
        raise ValueError("图片不在受支持的检测 split/images 目录内")

    def copy_subset_sample(self, source_root, target_root, image_path):
        """复制检测样本及其标签文件到训练子集。"""
        image_path = resolve_storage_path(image_path)
        if not image_path or not os.path.exists(image_path):
            return False
        target_images_dir = get_dataset_images_dir(target_root, DATASET_SPLIT_TRAIN)
        target_labels_dir = get_dataset_labels_dir(target_root, DATASET_SPLIT_TRAIN)
        os.makedirs(target_images_dir, exist_ok=True)
        os.makedirs(target_labels_dir, exist_ok=True)
        relative_path = resolve_relative_child_path(image_path, root=self._resolve_source_image_root(source_root, image_path))
        target_image_path = os.path.join(target_images_dir, relative_path)
        os.makedirs(os.path.dirname(target_image_path), exist_ok=True)
        shutil.copy2(image_path, target_image_path)
        label_path = resolve_existing_label_path_for_image(image_path)
        if label_path:
            target_label_path = os.path.join(target_labels_dir, build_label_relpath(relative_path))
            os.makedirs(os.path.dirname(target_label_path), exist_ok=True)
            shutil.copy2(label_path, target_label_path)
        return True

    def build_image_record(
        self,
        dataset_root,
        split,
        image_path,
        names,
        class_id_set,
        mode,
        unannotated,
        has_auto_label,
    ):
        """把检测图片解析为支持筛选状态的列表项。"""
        img_dir = get_dataset_images_dir(dataset_root, split)
        lbl_dir = get_dataset_labels_dir(dataset_root, split)
        auto_dir = get_dataset_auto_labels_dir(dataset_root, split)
        rel = os.path.relpath(image_path, img_dir)
        label_path = os.path.join(lbl_dir, build_label_relpath(rel))
        auto_label_path = os.path.join(auto_dir, build_label_relpath(rel))
        label_exists = os.path.exists(label_path)
        label_has_content = label_exists and os.path.getsize(label_path) > 0
        auto_label_exists = os.path.exists(auto_label_path)
        auto_label_has_content = auto_label_exists and os.path.getsize(auto_label_path) > 0
        if has_auto_label and not auto_label_exists:
            return None
        if unannotated:
            if label_exists:
                return None
            return {
                "path": image_path,
                "pending": auto_label_has_content,
                "has_auto_label": auto_label_has_content,
                "annotated": label_has_content,
            }
        if class_id_set:
            present = set()
            if label_has_content:
                try:
                    with open(label_path, "r", encoding="utf-8") as handle:
                        for line in handle:
                            parts = line.strip().split()
                            if not parts:
                                continue
                            try:
                                present.add(int(float(parts[0])))
                            except Exception:
                                continue
                except Exception:
                    present = set()
            has_any = bool(present & class_id_set)
            if mode == "exclude":
                if has_any:
                    return None
            elif not has_any:
                return None
        return {
            "path": image_path,
            "pending": auto_label_has_content,
            "has_auto_label": auto_label_has_content,
            "annotated": label_has_content,
        }

    def count_overlapping_boxes(self, dataset_root, split, image_path):
        """检测任务按标签文件数同类重复框；没有标签文件就是 0。"""
        img_dir = get_dataset_images_dir(dataset_root, split)
        lbl_dir = get_dataset_labels_dir(dataset_root, split)
        rel = os.path.relpath(image_path, img_dir)
        return count_redundant_boxes(os.path.join(lbl_dir, build_label_relpath(rel)))

    def list_pending_boxes(self, dataset_root, split, image_ref):
        """读这张图的候选文件，解析成缩略图上能直接画的框；没有候选就是空。"""
        return self._list_boxes(self._auto_label_path(dataset_root, split, image_ref))

    def list_label_boxes(self, dataset_root, split, image_ref):
        """读这张图的人工标签文件，解析成缩略图上能直接画的框；没标过就是空。"""
        return self._list_boxes(self._manual_label_path(dataset_root, split, image_ref))

    def _rel_to_image(self, dataset_root, split, image_ref):
        image_path = resolve_storage_path(image_ref)
        return os.path.relpath(image_path, get_dataset_images_dir(dataset_root, split))

    def _auto_label_path(self, dataset_root, split, image_ref):
        rel = self._rel_to_image(dataset_root, split, image_ref)
        return os.path.join(get_dataset_auto_labels_dir(dataset_root, split), build_label_relpath(rel))

    def _manual_label_path(self, dataset_root, split, image_ref):
        rel = self._rel_to_image(dataset_root, split, image_ref)
        return os.path.join(get_dataset_labels_dir(dataset_root, split), build_label_relpath(rel))

    def _list_boxes(self, label_path):
        """候选和人工标签共用一套行编码，所以缩略图上的框也从同一个解析口出来。"""
        if not os.path.isfile(label_path):
            return []
        boxes = []
        with open(label_path, "r", encoding="utf-8") as handle:
            for line in handle:
                parsed = parse_label_line(line)
                if not parsed:
                    continue
                boxes.append({"class": parsed["class_id"], **to_xyxy_box(parsed["box"])})
        return boxes

    def upload_images(self, dataset_root, split, files):
        """把上传图片保存到检测数据集的 images 目录。"""
        return self._save_upload_payload(get_dataset_images_dir(dataset_root, split), files)

    def iter_list_image_paths(self, dataset_root, split, unannotated=False, has_auto_label=False):
        """检测列表总是从 split/images 目录读取。"""
        del unannotated, has_auto_label
        img_dir = get_dataset_images_dir(dataset_root, split)
        if not os.path.isdir(img_dir):
            return []
        images = []
        for root, dirs, files in os.walk(img_dir):
            dirs.sort()
            files.sort()
            for filename in files:
                if filename.lower().endswith(IMAGE_FILE_EXTENSIONS):
                    images.append(os.path.join(root, filename))
        return images

    def resolve_image_relative_path(self, dataset_root, split, image_path):
        """把检测图片绝对路径解析为 images 根目录下的相对路径。"""
        return resolve_relative_child_path(image_path, root=get_dataset_images_dir(dataset_root, split))

    def delete_image(self, dataset_root, split, image_rel, image_path=None):
        """删除检测图片以及对应人工/自动标签文件。"""
        del image_path
        img_dir = get_dataset_images_dir(dataset_root, split)
        lbl_dir = get_dataset_labels_dir(dataset_root, split)
        auto_dir = get_dataset_auto_labels_dir(dataset_root, split)
        image_path = resolve_safe_child_path(img_dir, image_rel)
        rel_noext = os.path.splitext(image_rel)[0]
        label_path = resolve_safe_child_path(lbl_dir, build_label_relpath(rel_noext))
        auto_path = resolve_safe_child_path(auto_dir, build_label_relpath(rel_noext))
        meta_path = get_dataset_auto_meta_path(auto_path, auto_dir)
        deleted = {"image": False, "label": False, "auto_label": False}
        if os.path.exists(image_path):
            remove_file_silent(image_path)
            deleted["image"] = True
        if os.path.exists(label_path):
            remove_file_silent(label_path)
            deleted["label"] = True
        if os.path.exists(auto_path):
            remove_file_silent(auto_path)
            deleted["auto_label"] = True
        # 元信息文件与标签文件是同一批候选：图片没了就要一起走，否则留下串位的孤档
        if meta_path and os.path.exists(meta_path):
            remove_file_silent(meta_path)
        return deleted

    def move_image(self, dataset_root, split, image_rel, target_split):
        """把检测图片与其人工/自动标签（含审核元信息）一起搬到目标 split。"""
        target_split = self._resolve_move_target_split(split, target_split)
        source_images_dir = get_dataset_images_dir(dataset_root, split)
        image_path = resolve_safe_child_path(source_images_dir, image_rel)
        if not os.path.isfile(image_path):
            raise ValueError("图片不存在")
        self._raise_if_move_conflict(
            resolve_safe_child_path(get_dataset_images_dir(dataset_root, target_split), image_rel),
            image_rel,
            target_split,
        )
        rel_noext = os.path.splitext(image_rel)[0]
        source_auto_dir = get_dataset_auto_labels_dir(dataset_root, split)
        target_auto_dir = get_dataset_auto_labels_dir(dataset_root, target_split)
        source_auto_path = resolve_safe_child_path(source_auto_dir, build_label_relpath(rel_noext))
        moved = {"image": False, "label": False, "auto_label": False}
        move_path(image_path, resolve_safe_child_path(get_dataset_images_dir(dataset_root, target_split), image_rel), ensure_parent=True)
        moved["image"] = True
        source_label_path = resolve_safe_child_path(get_dataset_labels_dir(dataset_root, split), build_label_relpath(rel_noext))
        if os.path.isfile(source_label_path):
            move_path(source_label_path, resolve_safe_child_path(get_dataset_labels_dir(dataset_root, target_split), build_label_relpath(rel_noext)), ensure_parent=True)
            moved["label"] = True
        if os.path.isfile(source_auto_path):
            target_auto_path = resolve_safe_child_path(target_auto_dir, build_label_relpath(rel_noext))
            move_path(source_auto_path, target_auto_path, ensure_parent=True)
            moved["auto_label"] = True
            source_meta_path = get_dataset_auto_meta_path(source_auto_path, source_auto_dir)
            if source_meta_path and os.path.isfile(source_meta_path):
                move_path(source_meta_path, get_dataset_auto_meta_path(target_auto_path, target_auto_dir), ensure_parent=True)
        # 子目录里的图片搬走后可能留下空目录，与 delete_image 的清理口径保持一致
        remove_empty_dirs_up_to(image_path, source_images_dir)
        return moved

    def delete_duplicate_image(self, dataset_root, split, image_path):
        """删除重复检测图片本体，不额外做目录清理。"""
        if not os.path.exists(image_path):
            return False
        remove_file_silent(image_path)
        return True

    def resolve_deduplicate_label_paths(self, dataset_root, split, rel_noext):
        """返回检测图片去重时需要清理的全部标签文件路径。"""
        auto_dir = get_dataset_auto_labels_dir(dataset_root, split)
        auto_path = os.path.join(auto_dir, build_label_relpath(rel_noext))
        return [
            os.path.join(get_dataset_labels_dir(dataset_root, split), build_label_relpath(rel_noext)),
            os.path.join(get_dataset_legacy_labels_dir(dataset_root, split), build_label_relpath(rel_noext)),
            auto_path,
            get_dataset_auto_meta_path(auto_path, auto_dir),
        ]


class ClassifyDatasetTaskStrategy(BaseDatasetTaskStrategy):
    """图像分类数据集策略。"""

    vision_task_type = VISION_TASK_TYPE_CLASSIFY

    def _resolve_source_image_root(self, dataset_root, image_path):
        """根据图片路径定位其所属的分类已标注区或未标注区。"""
        for split in STANDARD_DATASET_SPLITS:
            unlabeled_dir = get_dataset_unlabeled_dir(dataset_root, split)
            if is_within_path(image_path, unlabeled_dir):
                return unlabeled_dir, True
            split_dir = get_dataset_split_dir(dataset_root, split)
            if is_within_path(image_path, split_dir):
                return split_dir, False
        raise ValueError("图片不在受支持的分类 split 目录内")

    def copy_subset_sample(self, source_root, target_root, image_path):
        """复制分类样本到训练子集，并保留已标注/未标注状态。"""
        image_path = resolve_storage_path(image_path)
        if not image_path or not os.path.exists(image_path):
            return False
        source_root_dir, is_unlabeled = self._resolve_source_image_root(source_root, image_path)
        relative_path = resolve_relative_child_path(image_path, root=source_root_dir)
        target_root_dir = get_dataset_unlabeled_dir(target_root, DATASET_SPLIT_TRAIN) if is_unlabeled else get_dataset_split_dir(target_root, DATASET_SPLIT_TRAIN)
        os.makedirs(target_root_dir, exist_ok=True)
        target_path = os.path.join(target_root_dir, relative_path)
        os.makedirs(os.path.dirname(target_path), exist_ok=True)
        shutil.copy2(image_path, target_path)
        return True

    def build_image_record(
        self,
        dataset_root,
        split,
        image_path,
        names,
        class_id_set,
        mode,
        unannotated,
        has_auto_label,
    ):
        """把分类图片解析为统一列表项，并同时覆盖已标注/未标注图片区。"""
        split_dir = get_dataset_split_dir(dataset_root, split)
        unlabeled_dir = get_dataset_unlabeled_dir(dataset_root, split)
        auto_dir = get_dataset_auto_labels_dir(dataset_root, split)
        is_unlabeled = is_within_path(image_path, unlabeled_dir)
        image_root = unlabeled_dir if is_unlabeled else split_dir
        rel = os.path.relpath(image_path, image_root)
        class_name = "" if is_unlabeled else extract_classification_class_name(rel)
        class_name_to_id = {str(name): index for index, name in enumerate(names or [])}
        rel_noext = os.path.splitext(rel)[0]
        auto_label_path = os.path.join(auto_dir, "unlabeled", build_label_relpath(rel_noext)) if is_unlabeled else ""
        auto_class_id = None
        auto_label_exists = bool(auto_label_path and os.path.exists(auto_label_path))
        if auto_label_exists:
            try:
                from contexts.annotation.application.annotation_service import decode_classification_file

                auto_class_id = decode_classification_file(auto_label_path)
            except Exception:
                auto_class_id = None
        if has_auto_label and not auto_label_exists:
            return None
        if unannotated and not is_unlabeled:
            return None
        if not unannotated and not has_auto_label and is_unlabeled:
            class_id = auto_class_id
        else:
            class_id = class_name_to_id.get(class_name)
        if class_id_set:
            has_any = class_id in class_id_set
            if mode == "exclude":
                if has_any:
                    return None
            elif not has_any:
                return None
        return {
            "path": image_path,
            "pending": auto_label_exists,
            "has_auto_label": auto_label_exists,
            "annotated": not is_unlabeled,
        }

    def upload_images(self, dataset_root, split, files):
        """把分类图片上传到按 split 分层的未标注工作区。"""
        return self._save_upload_payload(get_dataset_unlabeled_dir(dataset_root, split), files)

    def iter_list_image_paths(self, dataset_root, split, unannotated=False, has_auto_label=False):
        """分类列表默认同时展示已标注与未标注图片，筛选时优先收窄到未标注工作区。"""
        roots = []
        split_dir = get_dataset_split_dir(dataset_root, split)
        unlabeled_dir = get_dataset_unlabeled_dir(dataset_root, split)
        if unannotated or has_auto_label:
            roots.append(unlabeled_dir)
        else:
            roots.extend([split_dir, unlabeled_dir])
        images = []
        for root_dir in roots:
            if not os.path.isdir(root_dir):
                continue
            for root, dirs, files in os.walk(root_dir):
                dirs.sort()
                files.sort()
                for filename in files:
                    if filename.lower().endswith(IMAGE_FILE_EXTENSIONS):
                        images.append(os.path.join(root, filename))
        return images

    def resolve_image_relative_path(self, dataset_root, split, image_path):
        """把分类图片绝对路径解析为已标注区或未标注区内的相对路径。"""
        split_dir = get_dataset_split_dir(dataset_root, split)
        unlabeled_dir = get_dataset_unlabeled_dir(dataset_root, split)
        if is_within_path(image_path, unlabeled_dir):
            return resolve_relative_child_path(image_path, root=unlabeled_dir)
        return resolve_relative_child_path(image_path, root=split_dir)

    def delete_image(self, dataset_root, split, image_rel, image_path=None):
        """删除分类图片，并在必要时清理已标注区或未标注区的空目录。"""
        split_dir = get_dataset_split_dir(dataset_root, split)
        unlabeled_dir = get_dataset_unlabeled_dir(dataset_root, split)
        if image_path and is_within_path(image_path, unlabeled_dir):
            image_path = resolve_safe_child_path(unlabeled_dir, image_rel)
            auto_label_path = resolve_safe_child_path(
                get_dataset_auto_labels_dir(dataset_root, split),
                "unlabeled",
                build_label_relpath(os.path.splitext(image_rel)[0]),
            )
        else:
            image_path = resolve_safe_child_path(split_dir, image_rel)
            auto_label_path = None
        deleted = {"image": False, "label": False, "auto_label": False}
        deleted["image"] = self.delete_duplicate_image(dataset_root, split, image_path)
        if auto_label_path and os.path.exists(auto_label_path):
            remove_file_silent(auto_label_path)
            deleted["auto_label"] = True
        return deleted

    def move_image(self, dataset_root, split, image_rel, target_split):
        """把分类图片搬到目标 split，保持它所在的类别目录与已标注/未标注区域。"""
        target_split = self._resolve_move_target_split(split, target_split)
        zones = [
            (get_dataset_unlabeled_dir(dataset_root, split), get_dataset_unlabeled_dir(dataset_root, target_split), "unlabeled"),
            (get_dataset_split_dir(dataset_root, split), get_dataset_split_dir(dataset_root, target_split), ""),
        ]
        source_root_dir = image_path = target_image_path = None
        auto_prefix = ""
        for source_dir, target_dir, prefix in zones:
            candidate = resolve_safe_child_path(source_dir, image_rel)
            if os.path.isfile(candidate):
                source_root_dir = source_dir
                image_path = candidate
                target_image_path = resolve_safe_child_path(target_dir, image_rel)
                auto_prefix = prefix
                break
        if not image_path:
            raise ValueError("图片不存在")
        self._raise_if_move_conflict(target_image_path, image_rel, target_split)
        moved = {"image": False, "label": False, "auto_label": False}
        move_path(image_path, target_image_path, ensure_parent=True)
        moved["image"] = True
        if auto_prefix:
            label_rel = build_label_relpath(os.path.splitext(image_rel)[0])
            source_auto_dir = get_dataset_auto_labels_dir(dataset_root, split)
            target_auto_dir = get_dataset_auto_labels_dir(dataset_root, target_split)
            source_auto_path = resolve_safe_child_path(source_auto_dir, auto_prefix, label_rel)
            if os.path.isfile(source_auto_path):
                target_auto_path = resolve_safe_child_path(target_auto_dir, auto_prefix, label_rel)
                move_path(source_auto_path, target_auto_path, ensure_parent=True)
                moved["auto_label"] = True
                source_meta_path = get_dataset_auto_meta_path(source_auto_path, source_auto_dir)
                if source_meta_path and os.path.isfile(source_meta_path):
                    move_path(source_meta_path, get_dataset_auto_meta_path(target_auto_path, target_auto_dir), ensure_parent=True)
        remove_empty_dirs_up_to(image_path, source_root_dir)
        return moved

    def delete_duplicate_image(self, dataset_root, split, image_path):
        """删除重复分类图片，并向上清理已空的类别目录。"""
        if not os.path.exists(image_path):
            return False
        remove_file_silent(image_path)
        current_dir = os.path.dirname(image_path)
        split_root = get_dataset_split_dir(dataset_root, split)
        while current_dir.startswith(split_root) and current_dir != split_root:
            remove_dir_if_empty(current_dir)
            parent_dir = os.path.dirname(current_dir)
            if parent_dir == current_dir:
                break
            current_dir = parent_dir
        return True

    def ensure_label_dirs(self, dataset_root, label_name):
        """分类任务下，为新类别在 train/val split 中创建同名空子目录。"""
        safe_name = validate_leaf_name(label_name, field_name="类别名")
        created_dirs = []
        for split in (DATASET_SPLIT_TRAIN, DATASET_SPLIT_VAL):
            split_dir = os.path.join(get_dataset_split_dir(dataset_root, split), safe_name)
            if not os.path.isdir(split_dir):
                os.makedirs(split_dir, exist_ok=True)
                created_dirs.append(split_dir)
        return created_dirs

    def remove_label_dirs(self, dataset_root, label_name):
        """分类任务下，尝试删除该类别在 train/val 中的子目录；非空则跳过并汇总。"""
        safe_name = validate_leaf_name(label_name, field_name="类别名")
        removed_dirs = []
        skipped_dirs = []
        for split in (DATASET_SPLIT_TRAIN, DATASET_SPLIT_VAL):
            split_dir = os.path.join(get_dataset_split_dir(dataset_root, split), safe_name)
            if not os.path.isdir(split_dir):
                continue
            try:
                entries = os.listdir(split_dir)
            except Exception:
                skipped_dirs.append(split_dir)
                continue
            if entries:
                skipped_dirs.append(split_dir)
                continue
            try:
                os.rmdir(split_dir)
                removed_dirs.append(split_dir)
            except Exception:
                skipped_dirs.append(split_dir)
        if not removed_dirs and skipped_dirs:
            raise ValueError(f"类别「{label_name}」下仍有图片或文件，请先清理后再删除")
        return {"removed_dirs": removed_dirs, "skipped_dirs": skipped_dirs}


class SegmentDatasetTaskStrategy(DetectDatasetTaskStrategy):
    """实例分割数据集策略。"""

    vision_task_type = VISION_TASK_TYPE_SEGMENT


class PoseDatasetTaskStrategy(DetectDatasetTaskStrategy):
    """姿态估计数据集策略。"""

    vision_task_type = VISION_TASK_TYPE_POSE


_DATASET_TASK_STRATEGIES = {
    VISION_TASK_TYPE_DETECT: DetectDatasetTaskStrategy(),
    VISION_TASK_TYPE_CLASSIFY: ClassifyDatasetTaskStrategy(),
    VISION_TASK_TYPE_SEGMENT: SegmentDatasetTaskStrategy(),
    VISION_TASK_TYPE_POSE: PoseDatasetTaskStrategy(),
}


def resolve_dataset_task_strategy(vision_task_type):
    """按任务类型解析数据集操作策略。"""
    strategy = _DATASET_TASK_STRATEGIES.get(vision_task_type)
    if not strategy:
        raise ValueError(f"当前任务类型暂未接入数据集策略: {vision_task_type}")
    return strategy
