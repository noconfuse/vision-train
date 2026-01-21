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
      <label class="block text-sm font-medium mb-2 opacity-90">预训练模型</label>
      <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div v-for="(model, path) in store.pretrainedModels" 
             :key="path"
             class="border-2 border-white/20 rounded-lg p-3 cursor-pointer hover:bg-white/10 transition-colors"
             :class="selectedModel === model.name ? 'border-white bg-white/20' : ''"
             @click="selectedModel = model.name">
          <div class="font-bold">{{ model.name }}</div>
          <div class="text-xs opacity-70">{{ (model.size / 1024 / 1024).toFixed(1) }} MB</div>
        </div>
      </div>
    </div>

    <!-- Hyperparameters -->
    <div class="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-5 gap-4 mb-6">
      <div v-for="field in configFields" :key="field.key" :class="field.type === 'checkbox' ? 'flex items-end' : ''">
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
const config = reactive({
  epochs: '',
  batch: '',
  imgsz: 640,
  freeze: '',
  lr0: '',
  mosaic: '',
  mixup: '',
  scale: '',
  close_mosaic: '',
  rect: false
});

const configFields = [
  { key: 'epochs', label: '轮数(Epochs)', placeholder: '100' },
  { key: 'batch', label: '批次(Batch)', placeholder: '16' },
  { key: 'imgsz', label: '图像尺寸', placeholder: '640' },
  { key: 'freeze', label: '冻结层数', placeholder: '0' },
  { key: 'lr0', label: '初始学习率', placeholder: '0.01' },
  { key: 'mosaic', label: 'Mosaic增强', placeholder: '1.0' },
  { key: 'mixup', label: 'Mixup增强', placeholder: '0.0' },
  { key: 'scale', label: '缩放(Scale)', placeholder: '0.5' },
  { key: 'close_mosaic', label: '关闭Mosaic', placeholder: '10' },
  { key: 'rect', label: '矩形训练', type: 'checkbox' },
];

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
      freeze: config.freeze, // might be string or int
      lr0: parseFloat(config.lr0) || null,
      mosaic: parseFloat(config.mosaic) || null,
      mixup: parseFloat(config.mixup) || null,
      scale: parseFloat(config.scale) || null,
      close_mosaic: parseInt(config.close_mosaic) || null,
      rect: config.rect || false
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