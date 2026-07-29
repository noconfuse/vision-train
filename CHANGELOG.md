# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).


## [0.1.0] - 2026-07-28


### Bug Fixes

- 修复训练状态处理和前端错误显示 (0529582)

- 修复预训练模型选项过滤问题并改进训练模型标签显示 (b924b62)

- 修复自动调平模式切换逻辑和默认参数 (a8d508d)

- 修复模型测试目录API请求参数解析和图像标注函数 (76767da)


### Code Refactoring

- 重构训练面板和数据集列表的UI布局 (5562811)

- 更新SOP落地页并补充SOP文档示例 (d486e45)

- 优化路由与错误处理，切换至dataset_id作为稳定标识 (8f57d5d)


### Documentation

- 更新并重构项目文档内容 (fa9fef7)

- refresh user docs and netlify config (cb38fb6)

- 更新README文档，补充最新项目能力与配置细节 (c32117c)

- 添加MIT许可证文件并更新README添加许可证章节 (55ea5ec)


### Features

- 添加前端Vue3项目结构和后端Flask API基础框架 (8508f0e)

- 添加数据集下载和标签顺序调整功能 (0bfa5eb)

- feat (8d80a93)

- feat (f3d26b3)

- 支持数据集标签功能并增强训练历史查询 (a7a87d5)

- 添加更多训练参数配置选项 (c3909ed)

- 添加训练记录删除和产物查看功能 (036cf27)

- 添加自动标注状态查询和进度显示功能 (761456d)

- 添加待复核数据筛选功能 (cdfce4b)

- 改进图像标注组件的缩放和交互逻辑 (8c4ce5c)

- feat(ImageAnnotator): 移除自动生成框的过滤逻辑 (486281b)

- 添加全选本页按钮并修改自动标注文案 (f54e8da)

- 添加视频帧提取的健壮模式处理 (5c0c6b1)

- 添加批量删除图片功能 (cea2cc7)

- 添加框选删除图片功能并改进视频抽帧鲁棒性 (e369798)

- feat (e5231fb)

- feat (df5a89e)

- 支持删除数据集标签并批量更新标注文件 (1ca504a)

- 添加基于 MD5 的图片去重功能 (97949f3)

- 添加合并数据集功能 (007b5c1)

- feat (b3dc1f1)

- feat (e1da76c)

- 添加训练历史图表以实时可视化损失和指标 (fa9abd3)

- 在训练面板中增加历史模型标签页 (8bcf75d)

- 添加人员标注审核功能 (a40127a)

- 添加Person疑似误标复核筛选功能 (02b7790)

- 在数据集预览和标注界面显示疑似误标人物框 (072e95f)

- 添加弱类补偿采样功能以平衡数据集类别 (bd1b9a4)

- 添加预览功能并支持按目标占比自动计算参数 (c8e5ed4)

- 支持多类别弱类补偿采样并添加模型评估脚本 (2cda68a)

- 添加批量测试集推理功能 (e79d3a2)

- 在数据集列表页添加批量推理功能并移除独立训练历史组件 (a513b26)

- 添加测试子目录选择功能并改进推理结果可视化 (560ea7a)

- 添加推理结果预览模态框并增强数据集增强功能 (727fb5e)

- 引入路由并重构为多页面应用 (16aa75a)

- 添加训练产物可视化、模型导出和批量推理功能 (52f781e)

- 支持基于筛选条件的批量自动标注并增强导出文件展示 (7be4965)

- 支持OpenVINO模型自动标注并展示导出模型 (d1b2e75)

- 初始化Vision Train并完成全栈架构重构 (99352c7)

- 重构项目架构，完善视觉训练全链路支持 (3ac2fef)

- 新增分割/姿态估计、部署模板与数据集版本管理 (0ae2716)

- 集成DVC数据集版本管理，新增类别增删与数据集快照功能 (e39bd50)


### Miscellaneous

- 更新前端代理配置并添加项目文件下载工具 (4a5c9c0)

- 配置 release-please 自动发布流程 (32e59ea)


