# 常见问题 FAQ

> 把容易踩的坑集中放在这里。

## 安装 / 启动

**Q1：启动后访问 8080 失败？**

A：先确认后端终端仍在运行，再看当前终端是否有启动异常。首次安装 `ultralytics/torch` 会比较慢，建议重新执行 `python3 src/web/main.py` 并观察最后几行日志。

**Q2：我的 8080 端口被占用了？**

A：直接设置环境变量 `VISION_TRAIN_PORT`，不需要改代码。

**Q3：能不能只跑后端不跑前端？**

A：可以。直接启动后端 `python3 src/web/main.py`，前端可稍后单独运行。

---

## 数据集 / 标注

**Q4：我有现成的 YOLO 数据集，怎么导入？**

A：放到 `projects/<proj>/training/<dataset_name>/` 下，确保有 `dataset.yaml` + `train/{images,labels}/` + `val/{images,labels}/`。重启后端或刷新 UI 即可识别。

**Q5：dataset.yaml 的 `path` 字段我应该写什么？**

A：建议写 `.`（相对当前 yaml 所在目录）。这样最稳，不依赖机器上的绝对路径。

**Q6：能不能两个项目共用一个数据集？**

A：可以，YAML 软链不推荐；推荐用**数据导入**（dataset 合并 SOP）把数据复制到目标项目。如果一定要共享，也可以把 `projects/<proj>/training/<ds>` 替换为符号链接，但要自行保证目标路径长期存在。

**Q7：标签里的 class id 与 dataset.yaml 顺序对不上会怎样？**

A：训练会直接报错退出。需要先 [SOP-6 类别顺序调整](sop/06-class-reorder.md)。

---

## 训练

**Q8：训练到一半卡住？**

A：通常是图片读不到。看后端终端日志是否出现 `FileNotFoundError` 或 `PIL.UnidentifiedImageError`。同时检查 `projects/` 路径是否正确、`images/` 里是否混入非图片文件。

**Q9：能用预训练模型吗？**

A：可以。把权重放到 `pretrained_models/` 即可。Vision Train 也支持 Ultralytics 自动下载 `yolo11n.pt` 等。

**Q10：能多卡训练吗？**

A：当前 UI 只暴露单卡 / CPU。若要扩展多卡能力，可从 `src/web/contexts/training/infrastructure/execution_gateway.py` 的训练参数构建链路入手。下个版本会原生支持。

**Q11：怎么从断点恢复？**

A：训练历史页 → 选 run → **继续训练**。会加载该 run 的 `last.pt`。

---

## 评估 / 导出

**Q12：INT8 导出精度掉太多？**

A：检查校准集是否与验证集重叠（应该不重叠）；调大 `max_images`；检查数据归一化是否与训练一致。

**Q13：ONNX 导出后，NMS 在哪里？**

A：Ultralytics 默认导出**含 NMS**（EfficientNMS），可直接 inference。若要 raw 三输出，需 `model.export(format='onnx', nms=False)`，然后自行实现 NMS。

---

## 部署 / 运维

**Q14：升级 Vision Train 后数据还在吗？**

A：在。数据默认就在仓库下的 `projects/` 与 `pretrained_models/`，升级代码不会自动删除它们。

**Q15：怎么彻底卸载？**

```bash
rm -rf projects/ pretrained_models/
```

**Q16：怎么限制后端只能用某个 GPU？**

A：当前后端的设备选择逻辑在 `src/web/utils.py`。如果要固定 GPU，可在本机环境里设置对应设备可见性变量，或直接修改训练参数中的 `device`。

**Q17：Nginx 反代需要什么 header？**

A：`X-Real-IP` 与 `X-Forwarded-For` 即可。Flask 已开启 CORS，不需要额外处理。

---

## 性能

**Q18：训练多快？**

A：取决于 GPU。RTX 3060 上 yolo11n 跑 640 约 1.5~3 it/s；CPU 模式下慢 20~50 倍。

**Q19：数据预览卡顿？**

A：图片缩略图是按需加载，单页 200 张。如果还是卡，减小分页大小，并检查本机磁盘与图片读取性能。

**Q20：自动标注很慢？**

A：模型加载耗时（首次 5~10s），推理一般 < 0.5s/张。若 0.1 fps 以下，看是否在用 CPU：环境变量加 `CUDA_VISIBLE_DEVICES=0`。
