<template>
  <div v-if="store.selectedDataset" class="bg-gradient-to-br from-indigo-500 to-purple-600 rounded-xl shadow-lg p-6 text-white">
    <div class="flex justify-between items-center mb-6">
      <h2 class="text-xl font-bold">训练配置</h2>
      <div v-if="store.trainingStatus.is_running" class="animate-pulse flex items-center gap-2">
        <span class="w-3 h-3 bg-green-400 rounded-full"></span>
        <span class="font-mono text-sm">运行中</span>
      </div>
    </div>

    <!-- Model Selection -->
    <div class="mb-6">
      <div class="flex justify-between items-center mb-2">
        <label class="block text-sm font-medium opacity-90">预训练模型</label>
        <div class="flex bg-black/20 rounded-lg p-1 gap-1">
            <button 
                @click="activeModelTab = 'preset'"
                class="px-3 py-1 text-xs rounded-md transition-colors"
                :class="activeModelTab === 'preset' ? 'bg-white text-indigo-600 font-bold shadow-sm' : 'text-white/60 hover:text-white hover:bg-white/5'">
                官方预设
            </button>
            <button 
                @click="activeModelTab = 'history'"
                class="px-3 py-1 text-xs rounded-md transition-colors"
                :class="activeModelTab === 'history' ? 'bg-white text-indigo-600 font-bold shadow-sm' : 'text-white/60 hover:text-white hover:bg-white/5'">
                训练历史
            </button>
        </div>
      </div>

      <!-- Preset Models -->
      <div v-if="activeModelTab === 'preset'" class="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div v-for="(model, path) in presetModels" 
             :key="model.path"
             class="border-2 border-white/20 rounded-lg p-3 cursor-pointer hover:bg-white/10 transition-colors"
             :class="selectedModel === model.name ? 'border-white bg-white/20' : ''"
             @click="selectedModel = model.name">
          <div class="font-bold">{{ model.name }}</div>
          <div class="text-xs opacity-70">{{ (model.size / 1024 / 1024).toFixed(1) }} MB</div>
        </div>
      </div>

      <!-- History Models -->
      <div v-else class="grid grid-cols-1 md:grid-cols-2 gap-4 max-h-60 overflow-y-auto pr-1">
        <div v-if="historyModels.length === 0" class="col-span-2 text-center py-8 opacity-50 text-sm border-2 border-dashed border-white/10 rounded-lg">
            暂无训练历史模型
        </div>
        <div v-for="model in historyModels" 
             :key="model.path"
             class="border-2 border-white/20 rounded-lg p-3 cursor-pointer hover:bg-white/10 transition-colors flex flex-col gap-1 relative"
             :class="selectedModel === model.name ? 'border-white bg-white/20' : ''"
             @click="selectedModel = model.name">
          
          <!-- Badge for mAP -->
          <div v-if="model.metrics && model.metrics.map50" class="absolute top-2 right-2 bg-green-500/20 text-green-300 text-[10px] px-1.5 py-0.5 rounded font-mono">
            mAP: {{ (model.metrics.map50 * 100).toFixed(1) }}%
          </div>

          <div class="font-bold text-sm truncate pr-16" :title="model.name">{{ model.name }}</div>
          <div class="flex items-center gap-2 text-[10px] opacity-60">
            <span v-if="model.dataset" class="bg-indigo-500/30 px-1 rounded">{{ model.dataset }}</span>
            <span>{{ (model.size / 1024 / 1024).toFixed(1) }} MB</span>
          </div>
          <div class="text-[10px] opacity-40 font-mono mt-1">
            {{ model.created_at || 'Unknown Date' }}
          </div>
        </div>
      </div>
    </div>

    <!-- Hyperparameters -->
    <div class="mb-6">
      <div class="flex justify-between items-end mb-2">
        <h3 class="text-sm font-medium opacity-90">基础参数</h3>
      </div>
      <div class="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4 mb-4">
        <div v-for="field in basicFields" :key="field.key" :class="field.type === 'checkbox' ? 'flex items-end' : ''">
          <template v-if="field.type === 'checkbox'">
            <label class="flex items-center space-x-2 cursor-pointer bg-white/10 border border-white/20 rounded px-2 py-1.5 hover:bg-white/20 transition-colors w-full h-[30px] mt-auto">
              <input type="checkbox" 
                     v-model="config[field.key]" 
                     class="form-checkbox text-indigo-500 rounded focus:ring-0 bg-transparent border-white/40 w-4 h-4">
              <span class="text-xs font-medium opacity-90 select-none">{{ field.label }}</span>
            </label>
          </template>
          <template v-else>
            <label class="block text-xs font-medium mb-1 opacity-80">{{ field.label }}</label>
            <input type="number" 
                   v-model="config[field.key]" 
                   class="w-full bg-white/10 border border-white/20 rounded px-2 py-1 text-sm focus:outline-none focus:border-white focus:bg-white/20 transition-colors placeholder-white/30"
                   :placeholder="field.placeholder">
          </template>
        </div>
      </div>

      <!-- Imbalance Optimization -->
      <div class="mb-4 p-3 bg-indigo-500/20 border border-indigo-400/30 rounded-lg hover:bg-indigo-500/30 transition-colors">
          <label class="flex items-center space-x-3 cursor-pointer">
              <input type="checkbox" v-model="config.imbalance_optimization" @change="onImbalanceChange" class="form-checkbox text-indigo-400 rounded focus:ring-0 bg-transparent border-white/40 w-5 h-5">
              <div class="flex-1">
                  <div class="flex items-center gap-2">
                    <span class="font-bold text-sm text-white">针对不平衡数据集优化 (Class Imbalance Optimization)</span>
                    <span class="text-[10px] px-1.5 py-0.5 bg-indigo-500 rounded text-white font-mono">Recommended</span>
                  </div>
                  <p class="text-xs opacity-70 mt-0.5">自动启用 Cosine LR，并调整 Mosaic, Mixup, Flip 等增强参数，提升小样本类别检测效果。</p>
              </div>
          </label>
      </div>

      <!-- Advanced Augmentation -->
      <div class="border border-white/20 rounded-lg overflow-hidden bg-black/5">
           <button @click="showAdvanced = !showAdvanced" class="w-full flex justify-between items-center p-3 hover:bg-white/5 transition-colors text-sm font-medium">
              <span class="flex items-center gap-2">
                <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4 opacity-70" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6V4m0 2a2 2 0 100 4m0-4a2 2 0 110 4m-6 8a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4m6 6v10m6-2a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4" />
                </svg>
                高级增强参数 (Advanced Augmentation)
              </span>
              <span class="opacity-50 text-xs transform transition-transform duration-200" :class="showAdvanced ? 'rotate-180' : ''">▼</span>
           </button>
           
           <div v-show="showAdvanced" class="p-4 border-t border-white/10 grid grid-cols-2 md:grid-cols-4 lg:grid-cols-5 gap-4 bg-black/10">
               <div v-for="field in advancedFields" :key="field.key" :class="field.type === 'checkbox' ? 'flex items-end' : ''">
                  <template v-if="field.type === 'checkbox'">
                    <label class="flex items-center space-x-2 cursor-pointer bg-white/10 border border-white/20 rounded px-2 py-1.5 hover:bg-white/20 transition-colors w-full h-[30px] mt-auto">
                      <input type="checkbox" 
                            v-model="config[field.key]" 
                            class="form-checkbox text-indigo-500 rounded focus:ring-0 bg-transparent border-white/40 w-4 h-4">
                      <span class="text-xs font-medium opacity-90 select-none">{{ field.label }}</span>
                    </label>
                  </template>
                  <template v-else>
                    <label class="block text-[10px] uppercase tracking-wider font-medium mb-1 opacity-60">{{ field.label }}</label>
                    <input type="number" 
                          v-model="config[field.key]" 
                          step="0.1"
                          class="w-full bg-white/5 border border-white/10 rounded px-2 py-1 text-xs focus:outline-none focus:border-white/40 focus:bg-white/10 transition-colors placeholder-white/20"
                          :placeholder="field.placeholder">
                  </template>
               </div>
           </div>
      </div>
    </div>

    <!-- Error Message -->
    <div v-if="store.trainingStatus.error" class="mb-6 bg-red-500/20 border border-red-500/50 rounded-lg p-3 text-sm text-red-100">
      <div class="font-bold mb-1">Training Error</div>
      <div>{{ store.trainingStatus.error }}</div>
      <div v-if="store.trainingStatus.log && store.trainingStatus.log.length > 0" class="mt-2 text-xs opacity-80 font-mono max-h-32 overflow-y-auto bg-black/20 p-2 rounded">
        {{ store.trainingStatus.log[store.trainingStatus.log.length - 1] }}
      </div>
    </div>

    <!-- Progress -->
    <div v-if="store.trainingStatus.is_running || store.trainingStatus.progress > 0" class="mb-6">
      <div class="flex justify-between text-sm mb-2">
        <span>{{ store.trainingStatus.message || 'Processing...' }}</span>
        <span class="font-mono">{{ store.trainingStatus.progress }}%</span>
      </div>
      <div class="w-full bg-black/20 rounded-full h-2 overflow-hidden">
        <div class="bg-white h-full transition-all duration-300" 
             :style="{ width: `${store.trainingStatus.progress}%` }"></div>
      </div>
    </div>

    <!-- Real-time Charts -->
    <div v-if="store.trainingStatus.history && store.trainingStatus.history.length > 1" class="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
        <!-- Loss Chart -->
        <div class="bg-black/20 rounded-lg p-4 border border-white/10">
            <div class="flex justify-between items-center mb-2">
                <span class="text-xs font-bold opacity-80">Training Loss</span>
                <div class="flex gap-2 text-[10px]">
                    <span class="text-red-400">Box</span>
                    <span class="text-blue-400">Cls</span>
                    <span class="text-yellow-400">Dfl</span>
                </div>
            </div>
            <svg viewBox="0 0 100 50" class="w-full h-24 overflow-visible" preserveAspectRatio="none">
                <!-- Grid lines -->
                <line x1="0" y1="0" x2="100" y2="0" stroke="white" stroke-opacity="0.1" stroke-width="0.2" />
                <line x1="0" y1="50" x2="100" y2="50" stroke="white" stroke-opacity="0.1" stroke-width="0.2" />
                
                <!-- Box Loss -->
                <polyline :points="getPoints(store.trainingStatus.history, 'box_loss')" 
                          fill="none" stroke="#f87171" stroke-width="0.5" vector-effect="non-scaling-stroke" />
                <!-- Cls Loss -->
                <polyline :points="getPoints(store.trainingStatus.history, 'cls_loss')" 
                          fill="none" stroke="#60a5fa" stroke-width="0.5" vector-effect="non-scaling-stroke" />
                <!-- Dfl Loss -->
                <polyline :points="getPoints(store.trainingStatus.history, 'dfl_loss')" 
                          fill="none" stroke="#facc15" stroke-width="0.5" vector-effect="non-scaling-stroke" />
            </svg>
        </div>

        <!-- Metrics Chart -->
        <div class="bg-black/20 rounded-lg p-4 border border-white/10">
            <div class="flex justify-between items-center mb-2">
                <span class="text-xs font-bold opacity-80">Metrics (mAP)</span>
                <div class="flex gap-2 text-[10px]">
                    <span class="text-green-400">mAP50</span>
                    <span class="text-purple-400">mAP50-95</span>
                </div>
            </div>
            <svg viewBox="0 0 100 50" class="w-full h-24 overflow-visible" preserveAspectRatio="none">
                 <!-- Grid lines -->
                <line x1="0" y1="0" x2="100" y2="0" stroke="white" stroke-opacity="0.1" stroke-width="0.2" />
                <line x1="0" y1="25" x2="100" y2="25" stroke="white" stroke-opacity="0.1" stroke-width="0.2" stroke-dasharray="2" />
                <line x1="0" y1="50" x2="100" y2="50" stroke="white" stroke-opacity="0.1" stroke-width="0.2" />

                <!-- mAP50 -->
                <polyline :points="getMetricsPoints(store.trainingStatus.history, 'map50')" 
                          fill="none" stroke="#4ade80" stroke-width="0.5" vector-effect="non-scaling-stroke" />
                <!-- mAP50-95 -->
                <polyline :points="getMetricsPoints(store.trainingStatus.history, 'map50_95')" 
                          fill="none" stroke="#c084fc" stroke-width="0.5" vector-effect="non-scaling-stroke" />
            </svg>
        </div>
    </div>

    <!-- Actions -->
    <div class="flex justify-end gap-3">
      <button v-if="!store.trainingStatus.is_running"
              @click="startTraining"
              class="bg-green-500 hover:bg-green-600 text-white px-6 py-2 rounded-lg font-semibold shadow-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              :disabled="!isValid">
        Start Training
      </button>
      <button v-else
              @click="stopTraining"
              class="bg-red-500 hover:bg-red-600 text-white px-6 py-2 rounded-lg font-semibold shadow-lg transition-colors">
        Stop Training
      </button>
    </div>
  </div>
</template>

<script setup>
import { useMainStore } from '../stores/main';
import { ref, reactive, computed, onMounted } from 'vue';

const store = useMainStore();

const selectedModel = ref('');
const activeModelTab = ref('preset');

const presetModels = computed(() => {
    return store.pretrainedModels.filter(m => !m.type || m.type !== 'trained');
});

const historyModels = computed(() => {
    return store.pretrainedModels
        .filter(m => m.type === 'trained')
        .sort((a, b) => {
            if (a.created_at && b.created_at) {
                return new Date(b.created_at) - new Date(a.created_at);
            }
            return 0;
        });
});

const showAdvanced = ref(false);

const config = reactive({
  epochs: '',
  batch: '',
  imgsz: 640,
  freeze: '',
  lr0: '',
  rect: false,
  imbalance_optimization: false,
  
  // Advanced
  mosaic: '',
  mixup: '',
  copy_paste: '',
  degrees: '',
  translate: '',
  scale: '',
  shear: '',
  perspective: '',
  flipud: '',
  fliplr: '',
  hsv_h: '',
  hsv_s: '',
  hsv_v: '',
  close_mosaic: '',
  cos_lr: false,
});

const basicFields = [
  { key: 'epochs', label: '轮数(Epochs)', placeholder: '100' },
  { key: 'batch', label: '批次(Batch)', placeholder: '16' },
  { key: 'imgsz', label: '图像尺寸', placeholder: '640' },
  { key: 'freeze', label: '冻结层数', placeholder: '0' },
  { key: 'lr0', label: '初始学习率', placeholder: '0.01' },
  { key: 'rect', label: '矩形训练', type: 'checkbox' },
];

const advancedFields = [
  { key: 'mosaic', label: 'Mosaic (马赛克)', placeholder: '1.0' },
  { key: 'mixup', label: 'Mixup (混合)', placeholder: '0.15' },
  { key: 'copy_paste', label: 'CopyPaste', placeholder: '0.0' },
  { key: 'degrees', label: '旋转角度 (°)', placeholder: '0.0' },
  { key: 'translate', label: '平移 (Translate)', placeholder: '0.1' },
  { key: 'scale', label: '缩放 (Scale)', placeholder: '0.5' },
  { key: 'shear', label: '剪切 (Shear)', placeholder: '0.0' },
  { key: 'flipud', label: '上下翻转', placeholder: '0.0' },
  { key: 'fliplr', label: '左右翻转', placeholder: '0.5' },
  { key: 'hsv_h', label: 'HSV-Hue', placeholder: '0.015' },
  { key: 'hsv_s', label: 'HSV-Saturation', placeholder: '0.7' },
  { key: 'hsv_v', label: 'HSV-Value', placeholder: '0.4' },
  { key: 'close_mosaic', label: '关闭 Mosaic (最后N轮)', placeholder: '10' },
  { key: 'cos_lr', label: 'Cosine LR', type: 'checkbox' },
];

const onImbalanceChange = () => {
    if (config.imbalance_optimization) {
        config.cos_lr = true;
        if (!config.mosaic) config.mosaic = 1.0;
        if (!config.mixup) config.mixup = 0.15;
        if (!config.fliplr) config.fliplr = 0.5;
        if (!config.degrees) config.degrees = 10.0;
    }
};

const getPoints = (data, key, height = 50, width = 100) => {
    if (!data || data.length < 2) return '';
    const values = data.map(d => d[key] || 0);
    const maxVal = Math.max(...values, 0.0001) * 1.1; // 10% padding
    
    return values.map((v, i) => {
        const x = (i / (values.length - 1)) * width;
        const y = height - (v / maxVal) * height;
        return `${x},${y}`;
    }).join(' ');
};

const getMetricsPoints = (data, key, height = 50, width = 100) => {
    if (!data || data.length < 2) return '';
    return data.map((d, i) => {
        const x = (i / (data.length - 1)) * width;
        const y = height - ((d[key] || 0) * height); // 0-1 range
        return `${x},${y}`;
    }).join(' ');
};

const isValid = computed(() => {
  return store.selectedDataset && selectedModel.value;
});

const startTraining = async () => {
  if (!isValid.value) return;
  
  const payload = {
    project_path: store.currentProject.path,
    dataset_name: store.selectedDataset.name,
    dataset_path: store.selectedDataset.path,
    model_name: selectedModel.value,
    training_config: {
      epochs: parseInt(config.epochs) || null,
      batch: parseInt(config.batch) || null,
      imgsz: parseInt(config.imgsz) || null,
      freeze: config.freeze, 
      lr0: parseFloat(config.lr0) || null,
      rect: config.rect || false,
      imbalance_optimization: config.imbalance_optimization || false,
      
      // Advanced
      mosaic: parseFloat(config.mosaic) || null,
      mixup: parseFloat(config.mixup) || null,
      copy_paste: parseFloat(config.copy_paste) || null,
      degrees: parseFloat(config.degrees) || null,
      translate: parseFloat(config.translate) || null,
      scale: parseFloat(config.scale) || null,
      shear: parseFloat(config.shear) || null,
      perspective: parseFloat(config.perspective) || null,
      flipud: parseFloat(config.flipud) || null,
      fliplr: parseFloat(config.fliplr) || null,
      hsv_h: parseFloat(config.hsv_h) || null,
      hsv_s: parseFloat(config.hsv_s) || null,
      hsv_v: parseFloat(config.hsv_v) || null,
      close_mosaic: parseInt(config.close_mosaic) || null,
      cos_lr: config.cos_lr || false
    }
  };
  
  try {
    await store.startTraining(payload);
  } catch (e) {
    alert('Failed to start training: ' + e.message);
  }
};

const stopTraining = () => {
  if (confirm('Are you sure you want to stop training?')) {
    store.stopTraining();
  }
};

onMounted(() => {
  store.fetchModels();
  store.pollTrainingStatus(); // Resume polling if needed
});
</script>