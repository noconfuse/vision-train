# 快速开始

> 用最短路径把 Vision Train 跑起来，并进入第一个项目

## 1. 环境准备

```bash
git clone <your-repo> vision-train
cd vision-train
```

建议环境：

- Python 3.10+
- Node.js 18+
- npm 9+
- 宿主机已安装 `ffmpeg` / `ffprobe`

## 2. 启动后端

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
./scripts/start_backend.sh
```

默认可用地址：

- API 健康检查：<http://localhost:8080/api/health>

## 3. 启动前端

```bash
cd frontend
npm install
npm run dev
```

默认访问地址：

- Web UI：<http://localhost:5173>

开发模式下，前端会把 `/api` 自动代理到 `http://127.0.0.1:8080`。

## 4. 首次进入系统

在浏览器打开前端地址后，通常会先看到登录页：

- 如果后端已启用认证：输入账号密码登录
- 如果后端未启用认证：页面会提示并在几秒后自动进入系统

进入系统后，左侧是项目侧边栏，主区域默认在“数据集 / 视频”两个视图之间切换。

## 5. 跑通第一条主流程

推荐直接按下面顺序验证系统：

1. 按 [SOP-1 项目管理](../sop/01-project.md) 创建一个项目
2. 二选一准备数据：
   - 按 [SOP-3 数据标注](../sop/03-annotation.md) 导入一个现成的 YOLO 数据集
   - 按 [SOP-2 视频抽帧](../sop/02-video-frame-extract.md) 上传视频并抽帧导入数据集
3. 打开数据集详情页，检查标注、过滤和批量操作是否正常
4. 进入 [SOP-7 模型训练](../sop/07-train.md)，新建工作流并启动训练
5. 训练完成后，继续走 [SOP-8 评估与导出](../sop/08-eval-export.md)

## 6. 常见首次问题

- 打开前端后一直停在登录页：确认后端是否启动，以及 `/api/auth/status` 是否可访问
- 视频无法抽帧：优先检查宿主机是否已安装 `ffmpeg`
- 页面能打开但没有项目：这是正常情况，首次使用需要先新建项目
- 想回看后台任务：从侧边栏底部用户菜单进入“任务中心”

## 7. 停止服务

- 在后端终端停止后端进程
- 在前端终端停止 Vite 开发服务
