from ultralytics import YOLO

model = YOLO('/hy-tmp/vision-train/projects/layer3_behavior_detection/training_outputs/datasets_ex_online_super_merged_person/20260324_094709/weights/best.pt')

# Run validation on the dataset
metrics = model.val(data='/hy-tmp/vision-train/projects/layer3_behavior_detection/training/datasets_ex_online_super_merged_person/dataset.yaml', split='val')

# Print overall metrics
print("\n--- Overall Metrics ---")
print(f"mAP50: {metrics.box.map50}")
print(f"mAP50-95: {metrics.box.map}")
print(f"Precision: {metrics.box.mp}")
print(f"Recall: {metrics.box.mr}")

# Print class-specific metrics
print("\n--- Class-specific Metrics ---")
names = model.names
for i, class_id in enumerate(metrics.box.ap_class_index):
    name = names[class_id]
    # The arrays are ordered by the index in ap_class_index
    p = metrics.box.p[i]
    r = metrics.box.r[i]
    ap50 = metrics.box.ap50[i]
    print(f"Class '{name}' (ID {class_id}): Precision={p:.4f}, Recall={r:.4f}, mAP50={ap50:.4f}")

