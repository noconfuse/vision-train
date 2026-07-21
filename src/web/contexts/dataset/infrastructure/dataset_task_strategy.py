"""按数据集任务类型封装数据集读写策略。"""

import os
import shutil

from constants.media import IMAGE_FILE_EXTENSIONS
from contexts.dataset.infrastructure.dataset_layout import (
    STANDARD_DATASET_SPLITS,
    DATASET_SPLIT_TRAIN,
    build_label_relpath,
    extract_classification_class_name,
    get_dataset_auto_labels_dir,
    get_dataset_images_dir,
    get_dataset_labels_dir,
    get_dataset_legacy_labels_dir,
    get_dataset_split_dir,
    get_dataset_unlabeled_dir,
    resolve_existing_label_path_for_image,
)
from protocols.vision_task_type import VISION_TASK_TYPE_CLASSIFY, VISION_TASK_TYPE_DETECT
from shared.utils.fs_utils import allocate_nonconflicting_path, is_within_path, remove_dir_if_empty, remove_file_silent, resolve_safe_child_path
from shared.utils.path_utils import resolve_relative_child_path, resolve_storage_path, validate_filename


class BaseDatasetTaskStrategy:
    """定义数据集任务类型策略基类。"""

    vision_task_type = ""

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

    def delete_duplicate_image(self, *_args, **_kwargs):
        """删除重复图片，并完成该任务类型要求的后置清理。"""
        raise NotImplementedError

    def resolve_deduplicate_label_paths(self, dataset_root, split, rel_noext):
        """返回去重时需要一并清理的关联标签文件列表。"""
        return [os.path.join(get_dataset_auto_labels_dir(dataset_root, split), build_label_relpath(rel_noext))]


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

    def upload_images(self, dataset_root, split, files):
        """把上传图片保存到检测数据集的 images 目录。"""
        target_dir = get_dataset_images_dir(dataset_root, split)
        os.makedirs(target_dir, exist_ok=True)
        saved = []
        for file in files:
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
        return saved

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
        return deleted

    def delete_duplicate_image(self, dataset_root, split, image_path):
        """删除重复检测图片本体，不额外做目录清理。"""
        if not os.path.exists(image_path):
            return False
        remove_file_silent(image_path)
        return True

    def resolve_deduplicate_label_paths(self, dataset_root, split, rel_noext):
        """返回检测图片去重时需要清理的全部标签文件路径。"""
        return [
            os.path.join(get_dataset_labels_dir(dataset_root, split), build_label_relpath(rel_noext)),
            os.path.join(get_dataset_legacy_labels_dir(dataset_root, split), build_label_relpath(rel_noext)),
            os.path.join(get_dataset_auto_labels_dir(dataset_root, split), build_label_relpath(rel_noext)),
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
                from contexts.annotation.infrastructure.annotation_io import decode_classification_file

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
        target_dir = get_dataset_unlabeled_dir(dataset_root, split)
        os.makedirs(target_dir, exist_ok=True)
        saved = []
        for file in files:
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
        return saved

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


_DATASET_TASK_STRATEGIES = {
    VISION_TASK_TYPE_DETECT: DetectDatasetTaskStrategy(),
    VISION_TASK_TYPE_CLASSIFY: ClassifyDatasetTaskStrategy(),
}


def resolve_dataset_task_strategy(vision_task_type):
    """按任务类型解析数据集操作策略。"""
    strategy = _DATASET_TASK_STRATEGIES.get(vision_task_type)
    if not strategy:
        raise ValueError(f"当前任务类型暂未接入数据集策略: {vision_task_type}")
    return strategy
