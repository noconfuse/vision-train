<template>
  <div ref="pageRoot" class="h-screen w-screen overflow-y-auto bg-white text-slate-800">

    <!-- ============ 顶部导航 ============ -->
    <header class="sticky top-0 z-30 bg-white/90 backdrop-blur border-b border-gray-200">
      <div class="max-w-6xl mx-auto px-6 h-14 flex items-center justify-between">
        <router-link to="/" class="flex items-center gap-2 text-slate-800 hover:text-slate-900">
          <div class="w-7 h-7 bg-slate-900 text-white flex items-center justify-center text-sm">🎯</div>
          <span class="font-semibold tracking-wide">Vision Train</span>
        </router-link>
        <nav class="hidden md:flex items-center gap-7 text-sm text-gray-600">
          <button type="button" class="hover:text-slate-900 transition" @click="scrollToSection('features')">核心功能</button>
          <button type="button" class="hover:text-slate-900 transition" @click="scrollToSection('workflow')">工作流</button>
          <button type="button" class="hover:text-slate-900 transition" @click="scrollToSection('tasks')">任务中心</button>
          <button type="button" class="hover:text-slate-900 transition" @click="scrollToSection('faq')">常见问题</button>
        </nav>
        <div class="flex items-center gap-2">
          <a href="https://vision-train-docs.netlify.app"
             target="_blank"
             rel="noopener"
             class="vt-btn-secondary vt-btn-size-md">
            在线文档
          </a>
          <router-link to="/"
                       class="vt-btn-secondary vt-btn-size-md">
            登录控制台
          </router-link>
          <button
             type="button"
             class="vt-btn-solid-primary vt-btn-size-md"
             @click="scrollToSection('cta')">
            立即开始 →
          </button>
        </div>
      </div>
    </header>

    <!-- ============ Hero ============ -->
    <section class="relative overflow-hidden">
      <!-- 装饰：网格 + 渐变光斑 -->
      <div class="absolute inset-0 opacity-[0.03]"
           style="background-image:
                  linear-gradient(rgba(0,0,0,1) 1px, transparent 1px),
                  linear-gradient(90deg, rgba(0,0,0,1) 1px, transparent 1px);
                  background-size: 32px 32px;"></div>
      <div class="absolute -top-40 -right-40 w-[480px] h-[480px] rounded-full bg-blue-500/10 blur-3xl"></div>
      <div class="absolute -bottom-40 -left-40 w-[480px] h-[480px] rounded-full bg-emerald-500/10 blur-3xl"></div>

      <div class="relative max-w-6xl mx-auto px-6 py-20 lg:py-28 grid lg:grid-cols-2 gap-12 items-center">
        <!-- 左：文案 -->
        <div>
          <div class="inline-flex items-center gap-2 px-3 py-1 bg-slate-900 text-white text-xs font-medium mb-6">
            <span class="w-1.5 h-1.5 bg-emerald-400 rounded-full animate-pulse"></span>
            本地一体化工作台 · 训练 + 部署模板
          </div>
          <h1 class="text-4xl lg:text-5xl font-bold leading-tight text-slate-900 mb-5">
            视觉训练流程<br />
            <span class="text-slate-500">从数据整理到可部署模板</span>
            <br />一个工作台 <span class="underline decoration-blue-500 decoration-4 underline-offset-4">闭环</span>
          </h1>
          <p class="text-base text-slate-600 leading-relaxed mb-8 max-w-lg">
            围绕项目 → 数据集 → 标注 → 训练工作流 → 评估 / 导出 / 部署模板，覆盖检测、分类、分割、姿态四类任务。
          </p>
          <div class="flex flex-wrap gap-3 mb-8">
            <button
               type="button"
               class="vt-btn-solid-primary vt-btn-size-lg"
               @click="scrollToSection('cta')">
              免费开始使用
              <span>→</span>
            </button>
            <button
               type="button"
               class="vt-btn-secondary vt-btn-size-lg"
               @click="scrollToSection('workflow')">
              查看工作流
            </button>
          </div>
          <!-- 任务类型标签 -->
          <div class="flex items-center gap-2 text-xs text-gray-500">
            <span class="text-slate-900 font-semibold">Detect</span>
            <span class="text-gray-300">·</span>
            <span class="text-slate-900 font-semibold">Classify</span>
            <span class="text-gray-300">·</span>
            <span class="text-slate-900 font-semibold">Segment</span>
            <span class="text-gray-300">·</span>
            <span class="text-slate-900 font-semibold">Pose</span>
          </div>
        </div>

        <!-- 右：产品截图占位 / Hero 可视化 -->
        <div class="relative">
          <div class="bg-slate-900 text-slate-300 border border-slate-800 aspect-[4/3] flex items-center justify-center relative overflow-hidden">
            <!-- 模拟界面：训练工作流 5 步 -->
            <div class="absolute inset-0 grid grid-cols-12 grid-rows-6 gap-1 p-2 text-[9px] font-mono">
              <div class="col-span-3 row-span-6 bg-slate-800/60 flex flex-col gap-0.5 p-1">
                <div class="text-slate-500 text-[8px]">WORKFLOW</div>
                <div class="bg-slate-700/60 text-slate-200 px-1.5 py-1">训练配置</div>
                <div class="bg-slate-700/60 text-slate-200 px-1.5 py-1">任务详情</div>
                <div class="bg-slate-700/60 text-slate-200 px-1.5 py-1">测试评估</div>
                <div class="bg-slate-700/60 text-slate-200 px-1.5 py-1">模型导出</div>
                <div class="bg-blue-500/20 text-blue-300 px-1.5 py-1">部署模板</div>
              </div>
              <div class="col-span-9 row-span-1 bg-slate-800/40 flex items-center gap-2 px-2">
                <div class="text-slate-500">部署模板</div>
                <div class="text-slate-700">·</div>
                <div class="text-slate-300">fastapi_service</div>
                <div class="ml-auto text-emerald-400">completed</div>
              </div>
              <div class="col-span-9 row-span-5 bg-slate-800/20 flex flex-col gap-1 p-2">
                <div class="flex items-center gap-2 text-slate-400">
                  <span>source:</span>
                  <span class="text-slate-200">best.pt</span>
                  <span class="text-slate-600">→</span>
                  <span class="text-blue-300">template</span>
                </div>
                <div class="grid grid-cols-3 gap-1 mt-1">
                  <div class="bg-slate-800/60 px-2 py-1.5">
                    <div class="text-slate-500 text-[7px]">FASTAPI</div>
                    <div class="text-emerald-400 text-xs font-semibold">ready</div>
                  </div>
                  <div class="bg-slate-800/60 px-2 py-1.5">
                    <div class="text-slate-500 text-[7px]">PYTHON SDK</div>
                    <div class="text-emerald-400 text-xs font-semibold">ready</div>
                  </div>
                  <div class="bg-slate-800/60 px-2 py-1.5">
                    <div class="text-slate-500 text-[7px]">BATCH</div>
                    <div class="text-emerald-400 text-xs font-semibold">ready</div>
                  </div>
                </div>
                <div class="text-slate-500 mt-2">app.py · requirements.txt · manifest.json</div>
                <div class="h-1 bg-slate-700 mt-1">
                  <div class="h-full w-full bg-emerald-500"></div>
                </div>
                <div class="text-slate-600 text-[8px]">download bundle · 1m 12s</div>
              </div>
            </div>
            <div class="absolute top-2 right-2 text-[9px] font-mono text-slate-600">▣ UI PREVIEW</div>
          </div>
          <!-- 浮动小卡片：模板已就绪 -->
          <div class="absolute -bottom-4 -left-4 bg-white border border-gray-200 px-3 py-2 shadow-sm">
            <div class="flex items-center gap-2 text-xs">
              <span class="w-1.5 h-1.5 bg-emerald-500 rounded-full animate-pulse"></span>
              <span class="text-slate-700 font-medium">部署模板</span>
              <span class="text-gray-400">·</span>
              <span class="text-emerald-600 font-mono">可下载</span>
            </div>
          </div>
        </div>
      </div>
    </section>

    <!-- ============ 核心功能 ============ -->
    <section id="features" class="bg-gray-50 border-y border-gray-200">
      <div class="max-w-6xl mx-auto px-6 py-20">
        <div class="mb-12 max-w-2xl">
          <div class="text-xs text-blue-600 font-mono tracking-wider mb-3">FEATURES</div>
          <h2 class="text-3xl font-bold text-slate-900 mb-4">围绕真实训练流程设计</h2>
          <p class="text-slate-600">
            覆盖项目管理、数据准备、标注、训练、评估、导出与部署模板。
          </p>
        </div>

        <div class="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
          <article v-for="f in features" :key="f.title"
                   class="bg-white border border-gray-200 p-6 hover:border-slate-400 transition group">
            <div class="w-10 h-10 bg-slate-900 text-white flex items-center justify-center text-lg mb-4 group-hover:bg-blue-600 transition">
              {{ f.icon }}
            </div>
            <h3 class="text-base font-semibold text-slate-900 mb-2">{{ f.title }}</h3>
            <p class="text-sm text-slate-600 leading-relaxed">{{ f.desc }}</p>
          </article>
        </div>
      </div>
    </section>

    <!-- ============ 工作流 ============ -->
    <section id="workflow" class="bg-white">
      <div class="max-w-6xl mx-auto px-6 py-20">
        <div class="mb-12 max-w-2xl">
          <div class="text-xs text-blue-600 font-mono tracking-wider mb-3">WORKFLOW</div>
          <h2 class="text-3xl font-bold text-slate-900 mb-4">一个工作流跑通训练闭环</h2>
          <p class="text-slate-600">
            以训练工作流为中心：训练配置 → 任务详情 → 测试评估 → 模型导出 → 部署模板。归档与恢复不丢历史产物。
          </p>
        </div>

        <div class="grid md:grid-cols-2 lg:grid-cols-5 gap-4">
          <div v-for="(step, i) in workflow" :key="i"
               class="relative bg-white border border-gray-200 p-6">
            <div class="flex items-center gap-2 mb-4">
              <span class="text-2xl font-bold text-slate-200 font-mono leading-none">{{ String(i + 1).padStart(2, '0') }}</span>
              <span class="text-xs text-gray-500 font-mono uppercase tracking-wider">{{ step.tag }}</span>
            </div>
            <h3 class="text-base font-semibold text-slate-900 mb-2">{{ step.title }}</h3>
            <p class="text-sm text-slate-600 leading-relaxed mb-3">{{ step.desc }}</p>
            <ul class="space-y-1 text-xs text-slate-500">
              <li v-for="(item, j) in step.points" :key="j" class="flex items-start gap-1.5">
                <span class="text-blue-500 mt-0.5">›</span>
                <span>{{ item }}</span>
              </li>
            </ul>
            <div v-if="i < workflow.length - 1"
                 class="hidden lg:block absolute top-1/2 -right-2 w-4 h-px bg-gray-300 z-10"></div>
          </div>
        </div>
      </div>
    </section>

    <!-- ============ 任务中心 ============ -->
    <section id="tasks" class="bg-gray-50 border-y border-gray-200">
      <div class="max-w-6xl mx-auto px-6 py-20">
        <div class="mb-12 max-w-2xl">
          <div class="text-xs text-blue-600 font-mono tracking-wider mb-3">TASK CENTER</div>
          <h2 class="text-3xl font-bold text-slate-900 mb-4">后台任务统一回看</h2>
          <p class="text-slate-600">
            所有长任务（抽帧、标注、训练、测试、导出、部署模板）都在任务中心可见，支持按项目 / 类型 / 状态过滤。
          </p>
        </div>
        <div class="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
          <div v-for="t in taskTypes" :key="t.name"
               class="bg-white border border-gray-200 p-5">
            <div class="flex items-center gap-2 mb-2">
              <span class="text-lg">{{ t.icon }}</span>
              <span class="text-sm font-semibold text-slate-900">{{ t.name }}</span>
            </div>
            <p class="text-xs text-slate-600 leading-relaxed">{{ t.desc }}</p>
          </div>
        </div>

        <!-- 截图预览：用 docs 中已发布的真实截图，避免 landing 自己造 UI 草图 -->
        <div class="mt-10 grid md:grid-cols-3 gap-4">
          <figure class="bg-white border border-gray-200 overflow-hidden">
            <img src="https://vision-train-docs.netlify.app/assets/datasets.png" alt="数据集列表" class="w-full h-auto" loading="lazy" />
            <figcaption class="px-4 py-2 text-xs text-slate-500 border-t border-gray-100">数据集列表</figcaption>
          </figure>
          <figure class="bg-white border border-gray-200 overflow-hidden">
            <img src="https://vision-train-docs.netlify.app/assets/extract.png" alt="视频抽帧结果审查" class="w-full h-auto" loading="lazy" />
            <figcaption class="px-4 py-2 text-xs text-slate-500 border-t border-gray-100">视频抽帧结果审查</figcaption>
          </figure>
          <figure class="bg-white border border-gray-200 overflow-hidden">
            <img src="https://vision-train-docs.netlify.app/assets/template_export.png" alt="部署模板导出" class="w-full h-auto" loading="lazy" />
            <figcaption class="px-4 py-2 text-xs text-slate-500 border-t border-gray-100">部署模板导出</figcaption>
          </figure>
        </div>
      </div>
    </section>

    <!-- ============ FAQ ============ -->
    <section id="faq" class="bg-white border-t border-gray-200">
      <div class="max-w-4xl mx-auto px-6 py-20">
        <div class="mb-12">
          <div class="text-xs text-blue-600 font-mono tracking-wider mb-3">FAQ</div>
          <h2 class="text-3xl font-bold text-slate-900 mb-4">常见问题</h2>
        </div>
        <div class="space-y-3">
          <details v-for="(q, i) in faqs" :key="i"
                   class="group bg-white border border-gray-200">
            <summary class="flex items-center justify-between cursor-pointer px-5 py-4 select-none">
              <span class="text-sm font-medium text-slate-900">{{ q.q }}</span>
              <span class="text-gray-400 group-open:rotate-45 transition-transform text-lg leading-none">＋</span>
            </summary>
            <div class="px-5 pb-4 text-sm text-slate-600 leading-relaxed border-t border-gray-100 pt-3">
              {{ q.a }}
            </div>
          </details>
        </div>
      </div>
    </section>

    <!-- ============ CTA ============ -->
    <section id="cta" class="bg-slate-900 text-white">
      <div class="max-w-4xl mx-auto px-6 py-20 text-center">
        <h2 class="text-3xl lg:text-4xl font-bold mb-4">准备好跑通一个完整的视觉训练闭环？</h2>
        <p class="text-slate-400 mb-8 max-w-2xl mx-auto">
          登录控制台 → 创建项目 → 上传数据集 → 跑训练 → 直接生成部署模板。
        </p>
        <div class="flex flex-wrap items-center justify-center gap-3">
          <router-link to="/"
                       class="vt-btn-solid-primary vt-btn-size-lg">
            登录控制台
            <span>→</span>
          </router-link>
          <button
             type="button"
             class="vt-btn-secondary vt-btn-size-lg border-slate-700 bg-transparent text-white hover:bg-white/5"
             @click="scrollToSection('features')">
            了解更多
          </button>
        </div>
      </div>
    </section>

    <!-- ============ Footer ============ -->
    <footer class="bg-white border-t border-gray-200">
      <div class="max-w-6xl mx-auto px-6 py-8 text-xs text-gray-500 flex flex-col md:flex-row items-center justify-between gap-3">
        <div>© 2026 Vision Train · 本地一体化工作台</div>
        <div class="flex items-center gap-4">
          <router-link to="/" class="hover:text-slate-800">控制台</router-link>
          <a href="https://vision-train-docs.netlify.app" target="_blank" rel="noopener" class="hover:text-slate-800">在线文档</a>
          <button type="button" class="hover:text-slate-800" @click="scrollToSection('features')">功能</button>
          <button type="button" class="hover:text-slate-800" @click="scrollToSection('workflow')">工作流</button>
        </div>
      </div>
    </footer>

  </div>
</template>

<script setup>
import { ref } from 'vue';

const pageRoot = ref(null);

const scrollToSection = (id) => {
  const container = pageRoot.value;
  const target = document.getElementById(id);
  if (!container || !target) return;

  const top = Math.max(0, target.offsetTop - 72);
  container.scrollTo({
    top,
    behavior: 'smooth',
  });
};

const features = [
  { icon: '📦', title: '项目管理',     desc: '按项目隔离数据与训练记录；新建 / 编辑 / 删除 / 切换。' },
  { icon: '🎬', title: '视频抽帧',     desc: '上传工业视频，按时间或目标张数抽帧；抽帧后直接进入数据集。' },
  { icon: '🗂️', title: '数据集版本',   desc: '发布 / 恢复 / 自动引导数据集版本快照，重复恢复会被自动拦截。' },
  { icon: '✏️', title: '人工 + 自动标注', desc: '内置 detect / segment / classify / pose 标注器；支持基于已训练模型预标注再人工复核。' },
  { icon: '🚀', title: '训练工作流',   desc: '以工作流为中心管理多轮训练；可视化 loss / mAP / Precision / Recall；支持断点续训。' },
  { icon: '📦', title: '模型导出',     desc: '导出 ONNX / OpenVINO / TensorRT，可下载产物；多份导出互不覆盖。' },
  { icon: '🧩', title: '部署模板',     desc: '基于 `pt` 或导出后产物一键生成 FastAPI / Python SDK / 批处理 模板包。' },
  { icon: '🗃️', title: '工作流归档',   desc: '归档 / 恢复训练工作流，历史任务与产物保留，可继续迭代。' },
  { icon: '📊', title: '任务中心',     desc: '抽帧、标注、训练、测试、导出、部署模板统一回看，支持项目 / 类型 / 状态过滤。' },
];

const workflow = [
  {
    tag: 'CONFIG',
    title: '训练配置',
    desc: '选基线模型，配置训练参数',
    points: ['YOLO 全系列', '可视化超参', '批次校准', '环境画像'],
  },
  {
    tag: 'RUN',
    title: '任务详情',
    desc: '实时观察 loss / 指标 / 日志',
    points: ['可视化曲线', '断点续训', '可停止 / 可恢复'],
  },
  {
    tag: 'EVAL',
    title: '测试评估',
    desc: '在 test 集上看模型质量',
    points: ['mAP50 / 50-95', 'Precision / Recall', 'pose 任务指标'],
  },
  {
    tag: 'EXPORT',
    title: '模型导出',
    desc: '把当前权重导出为部署格式',
    points: ['ONNX', 'OpenVINO', 'TensorRT'],
  },
  {
    tag: 'DEPLOY',
    title: '部署模板',
    desc: '基于 `pt` 或导出产物一键打包',
    points: ['FastAPI 服务', 'Python SDK', '批处理任务'],
  },
];

const taskTypes = [
  { icon: '🎬', name: '视频抽帧',     desc: '上传视频并按策略抽帧，抽帧后可直接导入数据集。' },
  { icon: '✏️', name: '自动标注',     desc: '用已有模型对数据集预标注，产出"待复核"草稿再人工确认。' },
  { icon: '🚀', name: '模型训练',     desc: '基于预训练模型或历史模型启动一次训练，实时回报进度与日志。' },
  { icon: '📊', name: '测试评估',     desc: '在 test 集上跑评估，给出标准指标。' },
  { icon: '📦', name: '模型导出',     desc: '导出 ONNX / OpenVINO / TensorRT，可下载产物。' },
  { icon: '🧩', name: '部署模板',     desc: '基于源模型生成可下载的部署模板包。' },
];

const faqs = [
  { q: '支持哪些视觉任务类型？', a: '检测（detect）、分类（classify）、分割（segment）、姿态（pose）四类；每类都有独立的标注器与训练模式。' },
  { q: '训练用什么模型？', a: '系统已集成 Ultralytics 系列预训练模型；同项目历史训练产物也可以直接作为基线持续迭代。' },
  { q: '部署模板是什么？', a: '部署模板是独立的产物类型，可基于原始 `pt` 权重或导出后的 ONNX / OpenVINO / TensorRT 一键生成 FastAPI 服务、Python SDK、批处理任务模板，下载即可在业务侧使用。' },
  { q: '数据是否会上传云端？', a: '不会。数据集、训练产物、任务记录都存放在本地（`projects/` 目录 + 本地 SQLite）；如需远程访问，可在 `.env` 启用认证与会话。' },
  { q: '需要写代码吗？', a: '不需要。所有操作（上传、标注、训练、评估、导出、部署模板）都在 Web 端完成；个别高级能力（如自定义训练配置）以结构化表单呈现，无需手写脚本。' },
  { q: '支持多人协作吗？', a: '当前默认单机单项目场景；多用户协作、生产部署、SaaS 化不在当前版本范围。' },
];
</script>