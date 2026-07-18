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
          <button type="button" class="hover:text-slate-900 transition" @click="scrollToSection('metrics')">性能</button>
          <button type="button" class="hover:text-slate-900 transition" @click="scrollToSection('faq')">常见问题</button>
        </nav>
        <div class="flex items-center gap-2">
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
            v1.0 · 训练工作台
          </div>
          <h1 class="text-4xl lg:text-5xl font-bold leading-tight text-slate-900 mb-5">
            视觉训练流程<br />
            <span class="text-slate-500">从数据整理到模型产出</span>
            <br />只需 <span class="underline decoration-blue-500 decoration-4 underline-offset-4">四步</span>
          </h1>
          <p class="text-base text-slate-600 leading-relaxed mb-8 max-w-lg">
            一站式管理数据集、训练任务、模型评估与导出。
            面向工业质检、目标检测等场景的视觉训练工作台，重点解决数据管理、标注协同与训练复盘。
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
          <!-- 信任标 -->
          <div class="flex items-center gap-6 text-xs text-gray-500">
            <div class="flex items-center gap-1.5">
              <span class="text-slate-900 font-semibold">YOLOv8/v11</span>
            </div>
            <div class="flex items-center gap-1.5">
              <span class="text-slate-900 font-semibold">OpenVINO</span>
            </div>
            <div class="flex items-center gap-1.5">
              <span class="text-slate-900 font-semibold">ONNX</span>
            </div>
            <div class="flex items-center gap-1.5">
              <span class="text-slate-900 font-semibold">PyTorch</span>
            </div>
          </div>
        </div>

        <!-- 右：产品截图占位 / Hero 可视化 -->
        <div class="relative">
          <div class="bg-slate-900 text-slate-300 border border-slate-800 aspect-[4/3] flex items-center justify-center relative overflow-hidden">
            <!-- 模拟界面 -->
            <div class="absolute inset-0 grid grid-cols-12 grid-rows-6 gap-1 p-2 text-[9px] font-mono">
              <div class="col-span-3 row-span-6 bg-slate-800/60 flex flex-col gap-0.5 p-1">
                <div class="text-slate-500 text-[8px]">PROJECTS</div>
                <div class="bg-blue-500/20 text-blue-300 px-1.5 py-1">test_imort</div>
                <div class="px-1.5 py-1 text-slate-500">ppe</div>
                <div class="px-1.5 py-1 text-slate-500">layer3</div>
              </div>
              <div class="col-span-9 row-span-1 bg-slate-800/40 flex items-center gap-2 px-2">
                <div class="text-slate-500">test_imort</div>
                <div class="text-slate-700">/</div>
                <div class="text-slate-300">voc2007_test</div>
              </div>
              <div class="col-span-9 row-span-5 bg-slate-800/20 flex flex-col gap-1 p-2">
                <div class="flex items-center gap-2">
                  <div class="w-12 h-12 bg-blue-500/30 border border-blue-500/50"></div>
                  <div class="flex-1 space-y-1">
                    <div class="h-1.5 bg-slate-700 w-3/4"></div>
                    <div class="h-1.5 bg-slate-700 w-1/2"></div>
                    <div class="h-1.5 bg-emerald-500/50 w-2/3"></div>
                  </div>
                </div>
                <div class="text-slate-500 mt-2">loss: 0.231 · mAP50: 0.847</div>
                <div class="h-1 bg-slate-700 mt-1">
                  <div class="h-full w-3/4 bg-blue-500"></div>
                </div>
                <div class="text-slate-600 text-[8px]">epoch 100/100 · 2h 13m</div>
                <div class="grid grid-cols-2 gap-1 mt-2">
                  <div class="bg-slate-800/40 px-2 py-1.5">
                    <div class="text-slate-500 text-[7px]">PRECISION</div>
                    <div class="text-emerald-400 text-sm font-semibold">0.913</div>
                  </div>
                  <div class="bg-slate-800/40 px-2 py-1.5">
                    <div class="text-slate-500 text-[7px]">RECALL</div>
                    <div class="text-emerald-400 text-sm font-semibold">0.876</div>
                  </div>
                </div>
              </div>
            </div>
            <!-- 角标 -->
            <div class="absolute top-2 right-2 text-[9px] font-mono text-slate-600">▣ UI PREVIEW</div>
          </div>
          <!-- 浮动小卡片：实时训练中 -->
          <div class="absolute -bottom-4 -left-4 bg-white border border-gray-200 px-3 py-2 shadow-sm">
            <div class="flex items-center gap-2 text-xs">
              <span class="w-1.5 h-1.5 bg-blue-500 rounded-full animate-pulse"></span>
              <span class="text-slate-700 font-medium">voc2007_test</span>
              <span class="text-gray-400">·</span>
              <span class="text-emerald-600 font-mono">100%</span>
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
          <h2 class="text-3xl font-bold text-slate-900 mb-4">为生产环境设计的能力</h2>
          <p class="text-slate-600">
            围绕真实训练流程设计，覆盖项目管理、数据准备、标注、训练、评估与导出。
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
          <h2 class="text-3xl font-bold text-slate-900 mb-4">四步跑通训练闭环</h2>
          <p class="text-slate-600">
            从上传数据集到查看训练结果，全流程在 Web 端完成，无需写代码。
          </p>
        </div>

        <div class="grid md:grid-cols-2 lg:grid-cols-4 gap-4">
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
            <!-- 连接箭头 -->
            <div v-if="i < workflow.length - 1"
                 class="hidden lg:block absolute top-1/2 -right-2 w-4 h-px bg-gray-300 z-10"></div>
          </div>
        </div>
      </div>
    </section>

    <!-- ============ 性能指标 ============ -->
    <section id="metrics" class="bg-slate-900 text-white">
      <div class="max-w-6xl mx-auto px-6 py-20">
        <div class="grid lg:grid-cols-3 gap-12 items-center">
          <div>
            <div class="text-xs text-blue-400 font-mono tracking-wider mb-3">PERFORMANCE</div>
            <h2 class="text-3xl font-bold mb-4">生产级性能</h2>
            <p class="text-slate-400 leading-relaxed">
              充分利用 GPU 资源，支持断点续训、增量训练、并发任务调度。
            </p>
          </div>
          <div class="lg:col-span-2 grid grid-cols-2 gap-4">
            <div v-for="m in metrics" :key="m.label"
                 class="border border-slate-800 p-5">
              <div class="text-3xl font-bold text-blue-400 mb-1 font-mono">{{ m.value }}</div>
              <div class="text-sm text-slate-300 mb-1">{{ m.label }}</div>
              <div class="text-xs text-slate-500">{{ m.note }}</div>
            </div>
          </div>
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
        <h2 class="text-3xl lg:text-4xl font-bold mb-4">准备好开始训练你的视觉模型？</h2>
        <p class="text-slate-400 mb-8 max-w-2xl mx-auto">
          立即登录控制台，上传第一个数据集，10 分钟内跑通完整训练流程。
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
        <div>© 2026 Vision Train · v1.0</div>
        <div class="flex items-center gap-4">
          <router-link to="/" class="hover:text-slate-800">控制台</router-link>
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
  { icon: '📦', title: '数据集管理',     desc: '上传 zip / YOLO 格式数据集；切分 train/val/test；类别管理；去重与合并。' },
  { icon: '🎬', title: '视频抽帧',       desc: '上传工业视频，按时间/帧间隔抽帧；抽帧后直接进入标注流程。' },
  { icon: '✏️', title: '人工 + 自动标注',  desc: '内置轻量标注器；支持基于已训练模型的批量预标注，再人工复核。' },
  { icon: '🚀', title: '一键训练',       desc: 'YOLOv8/v11 等主流预训练模型；可视化配置超参数；实时显示 loss 与 mAP 曲线。' },
  { icon: '🔁', title: '断点续训',       desc: '训练意外中断后可从最近 checkpoint 恢复；增量训练支持。' },
  { icon: '📊', title: '评估与导出',     desc: '查看 mAP / Precision / Recall 等指标；统一管理训练产物与模型导出记录。' },
];

const workflow = [
  {
    tag: 'PREP',
    title: '数据准备',
    desc: '上传、整理、切分、标注数据集',
    points: ['Zip 上传', 'YOLO 格式校验', '类别管理', '数据集去重'],
  },
  {
    tag: 'TRAIN',
    title: '模型训练',
    desc: '选预训练模型，配置超参，启动训练',
    points: ['YOLOv8/v11', '可视化 loss / mAP', '断点续训', '多任务队列'],
  },
  {
    tag: 'EVAL',
    title: '评估',
    desc: '在测试集上跑评估，看模型质量',
    points: ['mAP50 / mAP50-95', 'Precision / Recall', '可视化对比'],
  },
  {
    tag: 'OUTPUT',
    title: '产物管理',
    desc: '查看训练历史、导出模型并继续复盘',
    points: ['训练产物浏览', '模型导出记录', '继续训练', '批量推理验证'],
  },
];

const metrics = [
  { value: '10+', label: 'YOLO 模型支持',     note: 'v8 / v11 全系列' },
  { value: '2x',  label: '训练加速',          note: '相对 CPU' },
  { value: '24/7', label: '后台任务调度',      note: '支持并发' },
  { value: '7d',  label: '会话保持',         note: '免频繁登录' },
];

const faqs = [
  { q: '支持哪些模型？', a: 'YOLOv8 / YOLOv11 全系列（检测 / 分类 / 分割）；后续会扩展到更多 backbone。' },
  { q: '训练用 GPU 吗？', a: '是。默认使用 GPU（CUDA / MPS），Mac 用户走 Apple Silicon 加速；也支持纯 CPU（速度较慢）。' },
  { q: '如何保证数据安全？', a: '数据集全部存放在本地（projects/ 目录），不会上传云端；可启用登录鉴权控制访问。' },
  { q: '系统包含部署能力吗？', a: '当前系统聚焦在数据管理、标注、训练、评估和模型导出。导出的 ONNX / OpenVINO 文件可供你在外部推理或业务系统中继续使用，但系统本身不负责线上部署。' },
  { q: '需要写代码吗？', a: '不需要。所有操作（上传、训练、评估、导出）都在 Web 端完成，鼠标点选即可。' },
];
</script>
