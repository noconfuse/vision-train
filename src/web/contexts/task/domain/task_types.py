"""定义任务类型枚举及训练任务集合。"""

TASK_TYPE_TRAINING = "training"
TASK_TYPE_BATCH_CALIBRATION = "batch_calibration"
TASK_TYPE_EVALUATE = "evaluate"
TASK_TYPE_INFERENCE = "inference"
TASK_TYPE_EXPORT = "export"
TASK_TYPE_TEMPLATE = "template"
TASK_TYPE_FRAME_EXTRACTION = "frame_extraction"
TASK_TYPE_DATASET_SNAPSHOT = "dataset_snapshot"

TRAINING_TASK_TYPES = frozenset(
    (
        TASK_TYPE_TRAINING,
        TASK_TYPE_BATCH_CALIBRATION,
        TASK_TYPE_EVALUATE,
        TASK_TYPE_EXPORT,
        TASK_TYPE_TEMPLATE,
        TASK_TYPE_INFERENCE,
    )
)
