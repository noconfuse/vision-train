"""为模型导出过程补充细粒度进度回调。"""

class ProgressReportingIterable:
    """Wrap one iterable and emit a callback after each consumed item."""

    def __init__(self, iterable, total, on_step):
        """保存被包装迭代器及进度回调参数。"""
        self._iterable = iterable
        self._total = max(int(total or 0), 0)
        self._on_step = on_step

    def __iter__(self):
        """逐项透传数据并在每步后上报进度。"""
        for index, item in enumerate(self._iterable, 1):
            if self._on_step:
                try:
                    self._on_step(index, self._total)
                except Exception:
                    pass
            yield item

    def __len__(self):
        """返回包装迭代器的长度或回退总量。"""
        if hasattr(self._iterable, '__len__'):
            return len(self._iterable)
        return self._total


def attach_export_progress_callbacks(
    model,
    *,
    task_id,
    export_format,
    export_int8,
    update_progress,
):
    """Attach export callbacks and report real progress for normal and INT8 OpenVINO exports."""
    def on_export_start(exporter):
        """在导出开始时初始化普通导出或 INT8 校准进度。"""
        if export_format == 'openvino' and export_int8:
            update_progress(task_id, 10, '开始 OpenVINO INT8 导出，准备校准数据...')
            original_get_dataloader = exporter.get_int8_calibration_dataloader

            def wrapped_get_dataloader(prefix=""):
                """包装 INT8 校准 dataloader 以逐批上报进度。"""
                dataloader = original_get_dataloader(prefix)
                try:
                    total_batches = len(dataloader)
                except Exception:
                    total_batches = 0
                if total_batches > 0:
                    update_progress(
                        task_id,
                        15,
                        f'正在收集 INT8 校准数据，共 {total_batches} 批...',
                    )
                else:
                    update_progress(task_id, 15, '正在收集 INT8 校准数据...')

                def on_calibration_step(current_batch, total):
                    """根据当前校准批次刷新导出进度。"""
                    if total > 0:
                        progress = 15 + int(current_batch / total * 75)
                        message = f'正在执行 INT8 校准 {current_batch}/{total} 批...'
                    else:
                        progress = min(90, 15 + current_batch)
                        message = f'正在执行 INT8 校准，第 {current_batch} 批...'
                    update_progress(task_id, progress, message)

                return ProgressReportingIterable(dataloader, total_batches, on_calibration_step)

            exporter.get_int8_calibration_dataloader = wrapped_get_dataloader
        else:
            update_progress(task_id, 35, f'正在导出 {export_format} 模型...')

    def on_export_end(_exporter):
        """在导出结束时切换到结果整理阶段。"""
        if export_format == 'openvino' and export_int8:
            update_progress(task_id, 95, 'INT8 校准完成，正在整理导出结果...')
        else:
            update_progress(task_id, 95, '导出完成，正在整理文件...')

    model.add_callback('on_export_start', on_export_start)
    model.add_callback('on_export_end', on_export_end)
