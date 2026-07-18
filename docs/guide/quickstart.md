# 快速开始

> 5 分钟内把 Vision Train 跑起来

## 1. 准备

```bash
git clone <your-repo> vision-train
cd vision-train
```

要求：

- Python 3.10+
- Node.js 18+
- npm 9+
- 建议宿主机已安装 `ffmpeg` / `ffprobe`

## 2. 启动后端

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
# 先准备配置（复制并按需修改）
cp .env.example .env
./scripts/start_backend.sh
```

默认监听：

- 后端 API：<http://localhost:8080/api/health>

## 3. 启动前端

```bash
cd frontend
npm install
npm run dev
```

默认访问：

- 前端 UI：<http://localhost:5173>

开发模式下，Vite 会把 `/api` 自动代理到 `http://127.0.0.1:8080`。

## 4. 验证安装

在浏览器打开前端 <http://localhost:5173>，应能看到：

- 左侧“项目列表”为空（首次启动无项目）
- 主体提示“请从左侧选择一个项目开始”

此时按 [SOP-1 创建项目](sop/01-project.md) 走一遍即可。

## 5. 停服

- 终止后端终端进程
- 终止前端终端进程
