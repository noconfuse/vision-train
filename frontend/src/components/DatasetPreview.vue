<template>
  <div
    class="bg-white flex flex-col transition-all duration-300 h-full min-h-0 p-4"
    :class="isFullScreen ? 'fixed inset-0 z-40 h-screen mb-0' : ''"
  >
    <!-- Row 1: 标题 + 视图操作 -->
    <div class="flex items-start justify-between gap-3 mb-3">
      <div class="min-w-0">
        <h2 class="text-base font-semibold text-slate-800">数据集预览：{{ store.selectedDataset?.name || '数据集' }}</h2>
      </div>
      <div class="flex items-center gap-2">
        <button
          class="vt-icon-btn"
          :aria-label="isFullScreen ? '退出全屏数据集预览' : '全屏数据集预览'"
          @click="isFullScreen = !isFullScreen"
        >
          <AppIcon :name="isFullScreen ? 'minimize' : 'maximize'" class="h-4 w-4" />
        </button>
        <button
          class="vt-btn-secondary vt-btn-size-md"
          :class="selectionMode
            ? 'vt-selectable--selected'
            : ''"
          @click="toggleSelectionMode"
        >
          <AppIcon :name="selectionMode ? 'check' : 'select'" class="h-4 w-4" />
          {{ selectionMode ? '退出选择模式' : '选择模式' }}
        </button>
        <button
          v-if="uploadImagesGuard.visible"
          class="vt-btn-solid-primary vt-btn-size-md"
          :disabled="!store.selectedDataset || !uploadImagesGuard.enabled"
          @click="openUploadImagesModal"
        >
          <AppIcon name="upload" class="h-4 w-4" />
          上传图片
        </button>
      </div>
    </div>

    <!-- Row 2: 选择模式操作条（只在选择模式显示） -->
    <div v-if="selectionMode" class="vt-surface-info mb-3 flex items-center justify-between gap-2 border p-2.5 flex-wrap">
      <div class="text-xs">
        已选 <span class="font-mono font-semibold">{{ selectedCount }}</span> 张图
      </div>
      <div class="flex items-center gap-2 flex-wrap">
        <button class="vt-btn-secondary vt-btn-size-sm"
                @click="selectAllCurrentPage">全选本页</button>
        <button v-if="createSubsetGuard.visible" class="vt-btn-solid-primary vt-btn-size-sm"
                :disabled="selectedCount === 0 || !createSubsetGuard.enabled"
                @click="openCreateSubset">
          生成子集
        </button>
        <button class="vt-btn-solid-danger vt-btn-size-sm"
                :disabled="selectedCount === 0 || deleting"
                @click="batchDelete">
          {{ deleting ? '删除中...' : '删除选中' }}
        </button>
      </div>
    </div>

    <!-- Row 4: 筛选条件 + 分页 -->
    <div class="mb-3 rounded-lg border border-gray-200 bg-gray-50 p-2.5">
      <div class="mb-2 flex items-start justify-between gap-3 flex-wrap">
        <div v-if="datasetInfo" class="flex flex-wrap items-center gap-1.5">
          <div class="mr-1 inline-flex h-7 items-center text-xs text-gray-500">
            类别筛选
          </div>
          <div class="inline-flex h-7 items-center text-xs text-slate-500">
            {{ datasetMetricLabel }}
            <span class="ml-1 font-mono font-medium text-slate-700">{{ datasetMetricValue }}</span>
          </div>
          <span
            v-for="s in datasetInfo.class_stats || []"
            :key="s.id"
            class="vt-chip group relative"
            :class="selectedClassIds.includes(s.id) ? 'vt-chip--selected' : ''"
            @click="toggleClass(s.id)"
          >
            <span class="font-medium">{{ s.name }}</span>
            <span class="font-mono text-[10px] opacity-70">{{ s.count }}·{{ s.percentage }}%</span>
            <button
              v-if="hasDatasetOperation(DATASET_OPERATION.DELETE_LABEL)"
              type="button"
              class="ml-0.5 inline-flex h-4 w-4 items-center justify-center rounded text-slate-500 opacity-0 transition-opacity hover:bg-rose-100 hover:text-rose-600 group-hover:opacity-100 focus:opacity-100"
              :disabled="deletingLabelId === s.id"
              :aria-label="`删除类别 ${s.name}`"
              @click.stop="onDeleteClassChip(s)"
            >
              <AppIcon name="close" class="h-3 w-3" />
            </button>
          </span>
          <span
            v-if="!(datasetInfo.class_stats && datasetInfo.class_stats.length)"
            class="inline-flex h-7 items-center text-xs text-gray-400"
          >
            暂无类别
          </span>
          <button
            v-if="selectedClassIds.length > 0"
            class="vt-btn-link h-7 text-xs"
            @click="clearClasses"
          >
            清空已选 {{ selectedClassIds.length }}
          </button>
          <!-- 加号：点击展开输入框，Enter 或点 ✓ 创建类别，失焦仅关闭面板 -->
          <div class="relative">
            <button
              type="button"
              class="vt-chip inline-flex h-7 items-center justify-center w-7 !px-0 text-slate-500 hover:!border-slate-400"
              :disabled="!canAddClass"
              :title="canAddClass ? '添加类别' : '当前数据集暂不支持添加类别'"
              :aria-label="'添加类别'"
              @click="toggleAddClassInput"
            >
              <AppIcon name="plus" class="h-3.5 w-3.5" />
            </button>
            <div
              v-if="showAddClassInput"
              class="absolute left-0 top-full z-20 mt-1 flex items-center gap-1 rounded border border-slate-200 bg-white px-2 py-1 shadow-md"
              @mousedown.prevent
              @click.stop
            >
              <input
                ref="addClassInput"
                v-model="newClassName"
                type="text"
                class="vt-input !h-7 !w-32 !py-0 !px-2 text-xs"
                placeholder="新类别名"
                :disabled="addingClass"
                @keydown.enter.prevent="commitAddClass"
                @keydown.esc="cancelAddClass"
                @blur="cancelAddClass"
              />
              <button
                type="button"
                class="vt-btn-solid-primary vt-btn-size-sm flex items-center justify-center !h-7 !w-7"
                :disabled="addingClass || !String(newClassName || '').trim()"
                :title="'确认添加'"
                :aria-label="'确认添加类别'"
                @mousedown.prevent
                @click="commitAddClass"
              >
                <AppIcon name="check" class="h-3.5 w-3.5" />
              </button>
            </div>
          </div>
        </div>

        <div v-if="datasetInfo" class="flex items-center gap-2 shrink-0 ml-auto">
          <div v-if="hasDatasetOperation(DATASET_OPERATION.AUTO_ANNOTATE)" class="relative" @mouseenter="showAutoAnnotateHelp = true" @mouseleave="showAutoAnnotateHelp = false">
            <button
              @click="showAutoAnnotateModal = true"
              class="vt-btn-solid-primary vt-btn-size-sm"
              :disabled="!store.selectedDataset"
            >
              <AppIcon name="sparkles" class="h-4 w-4" />
              <span>自动标注</span>
              <span class="inline-flex items-center justify-center w-3.5 h-3.5 rounded-full border border-white/30 bg-white/12 text-[10px] font-bold text-white/90 cursor-help">?</span>
            </button>
            <Transition name="fade">
              <div v-if="showAutoAnnotateHelp"
                   class="absolute right-0 top-full mt-1.5 z-30 bg-slate-800 text-white text-xs rounded-lg shadow-lg w-64 p-3 leading-relaxed">
                <div class="font-semibold mb-1 text-indigo-200">作用范围</div>
                <div class="text-slate-200">对<strong class="text-white">当前筛选条件</strong>（split / 类别 / 未标注等）下的图片，使用选定模型自动预标注。</div>
                <div class="text-slate-300 mt-1.5 text-[11px]">结果保存为「待复核」状态，可手动确认或修正。</div>
                <div class="absolute -top-1.5 right-3 w-3 h-3 bg-slate-800 rotate-45"></div>
              </div>
            </Transition>
          </div>
          <div v-if="hasAdvancedOperations" class="relative" ref="advancedMenuRef">
            <button
              class="vt-btn-secondary vt-btn-size-sm"
              @click="showAdvancedMenu = !showAdvancedMenu"
              :disabled="!store.selectedDataset"
            >
              <AppIcon name="settings" class="h-4 w-4" />
              <span>高级操作</span>
              <AppIcon name="chevronDown" class="h-3.5 w-3.5 text-gray-400" />
            </button>
            <div v-if="showAdvancedMenu"
                 class="absolute right-0 top-full z-30 mt-1 w-44 border border-gray-200 bg-white py-1 shadow-sm">
              <button v-if="canReorderLabels" class="w-full px-3 py-1.5 text-left text-xs hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-50"
                      :disabled="!canReorderLabels || reorderingLabels"
                      @click="onAdvanced(openReorderLabels)">
                调整类别顺序
                <span v-if="reorderingLabels" class="text-gray-400 text-[10px]">处理中...</span>
              </button>
              <div v-if="canReorderLabels && hasDatasetOperations" class="border-t border-gray-100 my-1"></div>
              <button v-if="hasDatasetOperation(DATASET_OPERATION.DEDUPLICATE_IMAGES)" class="w-full text-left px-3 py-1.5 text-xs hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
                      :disabled="deduplicatingImages"
                      @click="onAdvanced(deduplicateImages)">
                图片去重（MD5）
                <span v-if="deduplicatingImages" class="text-gray-400 text-[10px]">处理中...</span>
              </button>
              <button v-if="hasDatasetOperation(DATASET_OPERATION.MERGE_DATASETS)" class="w-full text-left px-3 py-1.5 text-xs hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
                      :disabled="mergingDatasets || mergeCandidates.length === 0"
                      @click="onAdvanced(openMergeDatasets)">
                合并数据集
                <span v-if="mergingDatasets" class="text-gray-400 text-[10px]">处理中...</span>
              </button>
              <template v-if="hasDatasetOperation(DATASET_OPERATION.AUTO_ANNOTATE)">
                <div class="border-t border-gray-100 my-1"></div>
                <button
                  class="w-full text-left px-3 py-1.5 text-xs text-rose-600 hover:bg-rose-50 disabled:opacity-50 disabled:cursor-not-allowed"
                  :disabled="clearingAutoLabels"
                  @click="onAdvanced(clearAutoLabels)"
                >
                  清除待复核标注
                  <span v-if="clearingAutoLabels" class="text-rose-300 text-[10px]">处理中...</span>
                </button>
              </template>
              <div v-if="(hasDatasetOperation(DATASET_OPERATION.AUTO_ANNOTATE) || hasDatasetOperations) && hasDatasetOperation(DATASET_OPERATION.AUGMENT_DATASET)" class="border-t border-gray-100 my-1"></div>
              <button v-if="hasDatasetOperation(DATASET_OPERATION.AUGMENT_DATASET)" class="w-full text-left px-3 py-1.5 text-xs hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
                      :disabled="isActionPending(AUGMENT_PREVIEW_ACTION_KEY) || isActionPending(AUGMENT_SUBMIT_ACTION_KEY)"
                      @click="onAdvanced(openAugmentSubsetModal)">
                弱类补偿采样
                <span
                  v-if="isActionPending(AUGMENT_PREVIEW_ACTION_KEY) || isActionPending(AUGMENT_SUBMIT_ACTION_KEY)"
                  class="text-gray-400 text-[10px]"
                >处理中...</span>
              </button>
            </div>
          </div>
        </div>
      </div>

      <div class="flex items-center justify-between gap-3 flex-wrap">
        <!-- 左侧：筛选 -->
        <div class="vt-toolbar">
        <select v-model="filters.split" class="vt-select vt-control-sm vt-control-auto min-w-[4.5rem] font-medium text-slate-800">
          <option value="train">train</option>
          <option value="val">val</option>
          <option value="test">test</option>
        </select>

        <label class="vt-toolbar-check cursor-pointer">
          <input type="checkbox" v-model="filters.unannotated" class="vt-checkbox h-3.5 w-3.5">
          未标注
        </label>

        <label class="vt-toolbar-check cursor-pointer">
          <input type="checkbox" v-model="filters.has_auto_label" class="vt-checkbox h-3.5 w-3.5">
          待复核
        </label>

        <button
          class="vt-btn-secondary vt-btn-size-sm"
          :disabled="loading"
          @click="applyFilters"
        >
          {{ loading ? '筛选中...' : '应用筛选' }}
        </button>
        </div>

        <!-- 右侧：分页 -->
        <div class="vt-toolbar vt-toolbar--nowrap shrink-0">
        <button
          class="vt-icon-btn vt-icon-btn--sm"
          :disabled="loading || currentPage <= 1"
          @click="goPrevPage"
        >
          <AppIcon name="previous" class="h-3.5 w-3.5" />
        </button>
        <input
          v-model.number="pageInput"
          type="number"
          min="1"
          :max="totalPages"
          class="vt-input vt-control-sm vt-control-page px-1.5 text-center"
          @keydown.enter.prevent="jumpPage"
        />
        <span class="text-xs text-gray-500">/ {{ totalPages }}</span>
        <button
          class="vt-icon-btn vt-icon-btn--sm"
          :disabled="loading || currentPage >= totalPages"
          @click="goNextPage"
        >
          <AppIcon name="next" class="h-3.5 w-3.5" />
        </button>
        </div>
      </div>
    </div>

    <!-- Image Grid -->
    <div class="flex-1 overflow-y-auto min-h-0 bg-gray-50 rounded-lg p-4 border border-gray-100">
        <div v-if="loading" class="flex justify-center items-center h-full">
        <div class="h-12 w-12 animate-spin rounded-full border-2 border-[var(--vt-color-primary-border)] border-t-[var(--vt-color-primary)]"></div>
      </div>

      <div v-else-if="images.length === 0" class="flex flex-col items-center justify-center h-full text-gray-400">
        <span class="text-4xl mb-2">📷</span>
        <p>暂无图片</p>
      </div>

      <div v-else :class="imageGridClass" :style="imageGridStyle">
        <div
          v-for="img in images"
          :key="img.path"
          class="group relative aspect-square overflow-hidden rounded-lg bg-gray-200 transition-all cursor-pointer hover:ring-2 hover:ring-[var(--vt-color-primary)]"
          @click="onImageClick(img)"
        >
          <img :src="img.url" class="w-full h-full object-cover" loading="lazy" />
          
          <div class="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
            <span class="max-w-full px-2 text-center text-xs font-mono text-white">
              {{ img.name }}
            </span>
          </div>

          <!-- Status Indicators -->
          <div class="absolute top-2 right-2 flex gap-1">
            <UiTooltip v-if="img.pending" side="top" align="center">
              <template #trigger>
                <span class="vt-status-dot vt-status-dot--warn shadow-sm"></span>
              </template>
              待复核
            </UiTooltip>
            <UiTooltip v-else-if="img.annotated" side="top" align="center">
              <template #trigger>
                <span class="vt-status-dot vt-status-dot--success shadow-sm"></span>
              </template>
              已标注
            </UiTooltip>
          </div>

          <div v-if="selectionMode" class="absolute top-2 left-2">
            <div
              class="vt-selection-indicator h-5 w-5 rounded shadow-sm"
              :class="isSelected(img.path) ? 'vt-selection-indicator--selected' : ''"
            >
              ✓
            </div>
          </div>
        </div>
      </div>
    </div>
    
    <!-- Footer Actions -->
    <div class="mt-4 pt-4 border-t border-gray-100 flex justify-between items-center">
       <span class="text-sm text-gray-500">共 {{ total }} 张图片</span>
       <button
         @click="goToTrain"
         :disabled="!store.selectedDataset || !trainGuard.enabled"
         :title="trainGuard.reason || ''"
         class="vt-btn-solid-primary vt-btn-size-lg"
       >
         <AppIcon name="train" class="h-4 w-4" />
         <span>{{ trainGuard.enabled ? '去训练' : '暂不可训练' }}</span>
         <AppIcon name="next" class="h-4 w-4" />
       </button>
    </div>
    
    <!-- Auto Annotate Progress Modal -->
    <div v-if="autoAnnotating" class="vt-modal-backdrop">
      <div class="vt-modal-panel vt-modal-panel--md p-5 text-center">
        <h3 class="text-lg font-bold mb-4">自动标注中...</h3>
        
        <div class="mb-4">
          <div class="flex justify-between text-sm mb-1 text-gray-600">
            <span>{{ autoAnnotateStatus.message }}</span>
            <span>{{ autoAnnotateStatus.progress }}%</span>
          </div>
          <div class="vt-meter h-2.5">
            <div class="vt-meter__bar vt-meter__bar--info rounded-full transition-all duration-300" :style="{ width: `${autoAnnotateStatus.progress}%` }"></div>
          </div>
        </div>
        
        <div class="grid grid-cols-2 gap-4 text-sm">
          <div class="bg-gray-50 p-3 rounded-lg">
            <div class="text-gray-500 mb-1">新增标注</div>
            <div class="font-mono font-bold text-lg text-green-600">{{ autoAnnotateStatus.added }}</div>
          </div>
          <div class="bg-gray-50 p-3 rounded-lg">
            <div class="text-gray-500 mb-1">新增待复核</div>
            <div class="font-mono font-bold text-lg text-orange-500">{{ autoAnnotateStatus.pending }}</div>
          </div>
        </div>
      </div>
    </div>

    <!-- Auto Annotate Modal -->
    <div v-if="showAutoAnnotateModal" class="vt-modal-backdrop">
      <div class="vt-modal-panel vt-modal-panel--md p-5">
        <h3 class="text-lg font-bold mb-4">自动标注配置</h3>
        
        <div class="mb-4">
          <label class="block text-sm font-medium text-gray-700 mb-2">选择模型</label>
          <div class="flex gap-2 mb-2">
            <button 
              @click="autoAnnotateType = 'pretrained'" 
              class="vt-btn-secondary flex-1 justify-center py-2 text-sm"
              :class="autoAnnotateType === 'pretrained' ? 'vt-selectable--selected' : ''"
            >预训练模型</button>
            <button 
              @click="autoAnnotateType = 'trained'" 
              class="vt-btn-secondary flex-1 justify-center py-2 text-sm"
              :class="autoAnnotateType === 'trained' ? 'vt-selectable--selected' : ''"
            >已训练模型</button>
          </div>
          
          <select v-if="autoAnnotateType === 'pretrained'" v-model="selectedModelPath" class="vt-select">
             <option v-for="m in pretrainedModelOptions" :key="m.path" :value="m.path">{{ m.name }}</option>
          </select>
          
          <select v-else v-model="selectedModelPath" class="vt-select">
             <option v-if="trainedModelOptions.length === 0" disabled>无可用历史模型</option>
             <option v-for="opt in trainedModelOptions" :key="opt.key" :value="opt.value">{{ opt.label }}</option>
          </select>
        </div>
        
        <div class="flex justify-end gap-2">
          <button @click="showAutoAnnotateModal = false" class="vt-btn-secondary vt-btn-size-md" :disabled="isActionPending(AUTO_ANNOTATE_ACTION_KEY)">取消</button>
          <AsyncButton
            @click="runAutoAnnotate"
            class="vt-btn-solid-primary vt-btn-size-md"
            :disabled="!selectedModelPath || autoAnnotating"
            :pending="isActionPending(AUTO_ANNOTATE_ACTION_KEY)"
            loading-text="启动中..."
          >
            开始标注
          </AsyncButton>
        </div>
      </div>
    </div>

    <!-- Annotator Modal -->
    <ImageAnnotator 
      v-if="currentImage && store.selectedDataset?.name && annotationMode === DATASET_ANNOTATION_MODE.DETECT_BOXES"
      :image="currentImage"
      :class-list="classList"
      :dataset-name="store.selectedDataset?.name || ''"
      :split="filters.split"
      @close="currentImage = null"
      @prev="navImage(-1)"
      @next="navImage(1)"
      @update="onImageUpdate"
    />
    <ClassificationAnnotator
      v-if="currentImage && store.selectedDataset?.name && annotationMode === DATASET_ANNOTATION_MODE.IMAGE_CLASS"
      :image="currentImage"
      :class-list="classList"
      :dataset-name="store.selectedDataset?.name || ''"
      :split="filters.split"
      @close="currentImage = null"
      @prev="navImage(-1)"
      @next="navImage(1)"
      @update="onImageUpdate"
    />
    <SegmentAnnotator
      v-if="currentImage && store.selectedDataset?.name && annotationMode === DATASET_ANNOTATION_MODE.SEGMENT_POLYGONS"
      :image="currentImage"
      :class-list="classList"
      :dataset-name="store.selectedDataset?.name || ''"
      :split="filters.split"
      @close="currentImage = null"
      @prev="navImage(-1)"
      @next="navImage(1)"
      @update="onImageUpdate"
    />
    <PoseAnnotator
      v-if="currentImage && store.selectedDataset?.name && annotationMode === DATASET_ANNOTATION_MODE.POSE_KEYPOINTS"
      :image="currentImage"
      :class-list="classList"
      :dataset-name="store.selectedDataset?.name || ''"
      :split="filters.split"
      @close="currentImage = null"
      @prev="navImage(-1)"
      @next="navImage(1)"
      @update="onImageUpdate"
    />

    <div v-if="showCreateSubsetModal" class="vt-modal-backdrop" @click.self="!isActionPending(CREATE_SUBSET_ACTION_KEY) && closeCreateSubset()">
      <div class="vt-modal-panel vt-modal-panel--md p-5">
        <h3 class="text-lg font-bold mb-4">生成独立数据集</h3>
        <div class="mb-4 text-sm text-gray-600">已选择 <span class="font-mono">{{ selectedCount }}</span> 张图片</div>
        <div class="mb-6">
          <label class="block text-sm font-medium text-gray-700 mb-2">新数据集名称</label>
          <input v-model.trim="subsetName" class="vt-input" :disabled="isActionPending(CREATE_SUBSET_ACTION_KEY)" placeholder="例如：datasets_04_subset" />
        </div>
        <div class="flex justify-end gap-2">
          <button class="vt-btn-secondary vt-btn-size-md" :disabled="isActionPending(CREATE_SUBSET_ACTION_KEY)" @click="closeCreateSubset">取消</button>
          <AsyncButton
            class="vt-btn-solid-primary vt-btn-size-md"
            :disabled="!subsetName"
            :pending="isActionPending(CREATE_SUBSET_ACTION_KEY)"
            loading-text="创建中..."
            @click="createSubset"
          >
            创建
          </AsyncButton>
        </div>
      </div>
    </div>

    <div v-if="showAugmentSubsetModal" class="vt-modal-backdrop" @click.self="closeAugmentSubsetModal">
      <div class="vt-modal-panel vt-modal-panel--xl p-5">
        <h3 class="text-lg font-bold mb-4">弱类补偿采样</h3>
        <div class="grid grid-cols-1 gap-4 md:grid-cols-2">
            <div class="md:col-span-2">
              <label class="mb-2 block text-sm font-medium text-gray-700">新数据集名称</label>
              <input v-model.trim="augmentConfig.newDatasetName" class="vt-input" placeholder="例如：datasets_person_comp_20260323" />
            </div>

            <div>
              <label class="vt-field-label">
                <span>从哪个分组生成训练集</span>
                <UiTooltip side="top" align="start" content-class="max-w-[18rem] break-words text-left">
                  <template #trigger>
                    <button type="button" class="vt-icon-btn vt-icon-btn--sm" aria-label="来源分组说明">
                      <AppIcon name="help" class="h-3.5 w-3.5" />
                    </button>
                  </template>
                  选择要抽样和补强的来源分组。
                </UiTooltip>
              </label>
              <select v-model="augmentConfig.split" class="vt-select">
                <option value="train">train</option>
                <option value="val">val</option>
                <option value="test">test</option>
              </select>
            </div>

            <div>
              <label class="vt-field-label">
                <span>添加要补强的类别</span>
              </label>
              <PopoverRoot v-model:open="augmentTargetClassPickerOpen">
                <PopoverTrigger as-child>
                  <button
                    type="button"
                    class="vt-input flex min-h-8 w-full items-center justify-between gap-3 text-left"
                    :class="augmentTargetClassPickerOpen ? 'ring-1 ring-[var(--vt-color-primary-border)]' : ''"
                  >
                    <span class="flex min-w-0 items-center gap-2 truncate text-sm text-slate-800">
                      <AppIcon name="target" class="h-4 w-4 shrink-0 text-slate-400" />
                      <span class="min-w-0 truncate">{{ augmentTargetClassSummary }}</span>
                    </span>
                    <AppIcon name="chevronDown" class="h-4 w-4 shrink-0 text-slate-400" />
                  </button>
                </PopoverTrigger>
                <PopoverPortal>
                  <PopoverContent
                    side="bottom"
                    align="start"
                    :side-offset="8"
                    :collision-padding="8"
                    class="z-50 w-[var(--reka-popover-trigger-width)] border border-gray-200 bg-white p-2 shadow-lg"
                  >
                    <div class="mb-2 flex items-center justify-between gap-2 px-1">
                      <span class="text-xs font-medium text-slate-700">选择目标类</span>
                      <button type="button" class="text-[11px] text-slate-500 hover:text-slate-900" @click="clearAugmentTargetClasses">
                        清空
                      </button>
                    </div>
                    <div class="max-h-56 space-y-1 overflow-y-auto pr-1">
                      <button
                        v-for="c in augmentClassOptions"
                        :key="c.id"
                        type="button"
                        class="vt-choice-card vt-choice-card--compact vt-choice-card--interactive flex w-full items-center justify-between gap-3"
                        :class="isAugmentTargetClassSelected(c.id) ? 'vt-choice-card--selected' : ''"
                        @click="toggleAugmentTargetClass(c.id)"
                      >
                        <div class="min-w-0">
                          <div class="truncate text-sm font-medium">{{ c.name }}</div>
                          <div class="text-[11px] text-slate-500">当前含该类的图片 {{ c.count }} 张</div>
                        </div>
                        <input
                          type="checkbox"
                          class="vt-checkbox pointer-events-none"
                          :checked="isAugmentTargetClassSelected(c.id)"
                          tabindex="-1"
                          aria-hidden="true"
                        >
                      </button>
                    </div>
                  </PopoverContent>
                </PopoverPortal>
              </PopoverRoot>
            </div>

            <div class="md:col-span-2">
              <label class="vt-field-label">
                <span>已选目标类</span>
              </label>
              <div v-if="selectedAugmentClasses.length" class="grid grid-cols-1 gap-3 md:grid-cols-2">
                <div
                  v-for="option in selectedAugmentClasses"
                  :key="option.classId"
                  class="vt-config-card vt-config-card--muted"
                >
                  <div class="flex items-start justify-between gap-3">
                    <div class="min-w-0">
                      <div class="truncate text-sm font-medium text-slate-800">{{ option.name }}</div>
                      <div class="mt-1 text-xs text-slate-500">当前图片 {{ option.count }} 张</div>
                    </div>
                    <button
                      type="button"
                      class="vt-icon-btn vt-icon-btn--sm shrink-0 text-slate-400"
                      :aria-label="`移除目标类 ${option.name}`"
                      @click="removeAugmentTargetClass(option.classId)"
                    >
                      <AppIcon name="close" class="h-3.5 w-3.5" />
                    </button>
                  </div>
                  <div class="mt-3">
                    <label class="mb-1 block text-xs font-medium text-slate-500">目标倍数</label>
                    <input
                      :value="option.targetMultiplier"
                      type="number"
                      min="1"
                      max="30"
                      step="0.5"
                      class="vt-input"
                      @input="updateAugmentTargetMultiplier(option.classId, $event.target.value)"
                      @blur="updateAugmentTargetMultiplier(option.classId, $event.target.value)"
                    />
                  </div>
                </div>
              </div>
              <div v-else class="vt-config-card vt-config-card--muted vt-config-card--dashed flex items-center gap-3 text-sm text-slate-500">
                <AppIcon name="target" class="h-4 w-4 shrink-0 text-slate-400" />
                <span>先添加目标类</span>
              </div>
            </div>

            <div class="md:col-span-2 border-t border-slate-200"></div>

            <div>
              <label class="vt-field-label">
                <span>非目标图片保留比例</span>
                <UiTooltip side="top" align="start" content-class="max-w-[18rem] break-words text-left">
                  <template #trigger>
                    <button type="button" class="vt-icon-btn vt-icon-btn--sm" aria-label="非目标图片保留比例说明">
                      <AppIcon name="help" class="h-3.5 w-3.5" />
                    </button>
                  </template>
                  `1` 表示全部保留，`0.5` 表示大约保留一半。
                </UiTooltip>
              </label>
              <input v-model.number="augmentConfig.nonTargetKeepRatio" type="number" min="0" max="1" step="0.05" class="vt-input" />
            </div>

            <div>
              <label class="vt-field-label">
                <span>颜色增强强度</span>
                <UiTooltip side="top" align="start" content-class="max-w-[18rem] break-words text-left">
                  <template #trigger>
                    <button type="button" class="vt-icon-btn vt-icon-btn--sm" aria-label="颜色增强强度说明">
                      <AppIcon name="help" class="h-3.5 w-3.5" />
                    </button>
                  </template>
                  值越大，颜色变化越明显。
                </UiTooltip>
              </label>
              <input v-model.number="augmentConfig.colorJitter" type="number" min="0" max="0.8" step="0.05" class="vt-input" />
            </div>

            <div class="md:col-span-2">
              <label class="vt-field-label">
                <span>增强方式</span>
              </label>
              <div class="flex flex-wrap gap-2">
                <label class="vt-toolbar-check cursor-pointer">
                  <input v-model="augmentConfig.enableHflip" type="checkbox" class="vt-checkbox h-3.5 w-3.5">
                  水平翻转
                </label>
                <label class="vt-toolbar-check cursor-pointer">
                  <input v-model="augmentConfig.enableVflip" type="checkbox" class="vt-checkbox h-3.5 w-3.5">
                  垂直翻转
                </label>
              </div>
            </div>

            <div class="md:col-span-2">
              <label class="vt-field-label">
                <span>val/test 处理方式</span>
              </label>
              <div class="flex flex-wrap gap-2">
                <label class="vt-toolbar-check cursor-pointer" :class="augmentEvalMode === 'keep' ? 'vt-selectable--selected' : ''">
                  <input v-model="augmentEvalMode" type="radio" value="keep" class="vt-radio h-3.5 w-3.5">
                  保留原 val/test
                </label>
                <label class="vt-toolbar-check cursor-pointer" :class="augmentEvalMode === 'rebuild' ? 'vt-selectable--selected' : ''">
                  <input v-model="augmentEvalMode" type="radio" value="rebuild" class="vt-radio h-3.5 w-3.5">
                  重新整理 val/test
                </label>
              </div>
            </div>

            <div v-if="augmentEvalMode === 'rebuild'" class="md:col-span-2">
              <label class="vt-field-label">
                <span>val/test 目标类覆盖比例</span>
                <UiTooltip side="top" align="start" content-class="max-w-[18rem] break-words text-left">
                  <template #trigger>
                    <button type="button" class="vt-icon-btn vt-icon-btn--sm" aria-label="val/test 中目标类占比说明">
                      <AppIcon name="help" class="h-3.5 w-3.5" />
                    </button>
                  </template>
                  留空时按源数据集自动估算。
                </UiTooltip>
              </label>
              <input v-model.number="augmentConfig.evalTargetRatio" type="number" min="0" max="1" step="0.01" class="vt-input" placeholder="例如 0.06 表示大约 6%" />
            </div>

            <div class="md:col-span-2 border-t border-slate-200 pt-1">
              <button type="button" class="vt-btn-link" @click="showAugmentAdvancedOptions = !showAugmentAdvancedOptions">
                <AppIcon :name="showAugmentAdvancedOptions ? 'chevronDown' : 'chevronRight'" class="h-3.5 w-3.5" />
                <span>{{ showAugmentAdvancedOptions ? '收起高级设置' : '展开高级设置' }}</span>
              </button>
            </div>

            <div v-if="showAugmentAdvancedOptions" class="md:col-span-2">
              <div class="grid grid-cols-1 gap-4 md:grid-cols-2">
                <div>
                  <label class="vt-field-label">
                    <span>随机种子</span>
                    <UiTooltip side="top" align="start" content-class="max-w-[18rem] break-words text-left">
                      <template #trigger>
                        <button type="button" class="vt-icon-btn vt-icon-btn--sm" aria-label="随机种子说明">
                          <AppIcon name="help" class="h-3.5 w-3.5" />
                        </button>
                      </template>
                      相同参数配合相同种子时，结果更容易复现。
                    </UiTooltip>
                  </label>
                  <input v-model.number="augmentConfig.seed" type="number" min="1" class="vt-input" />
                </div>
              </div>
            </div>
        </div>
        <div v-if="augmentPreview" class="mt-4 space-y-4">
          <div class="grid grid-cols-1 gap-3 md:grid-cols-3">
            <div class="vt-stat-card">
              <div class="vt-stat-label">预计训练集总数</div>
              <div class="vt-stat-value text-slate-800">{{ augmentPreview.estimated_output_total }}</div>
            </div>
            <div class="vt-stat-card">
              <div class="vt-stat-label">预计目标类图片</div>
              <div class="vt-stat-value text-slate-800">{{ augmentPreview.estimated_output_target }}</div>
            </div>
            <div class="vt-stat-card">
              <div class="vt-stat-label">预计目标类占比</div>
              <div class="vt-stat-value text-slate-800">{{ augmentPreview.estimated_output_target_ratio }}%</div>
            </div>
          </div>
          <div class="vt-table-shell">
            <table class="vt-table">
              <thead class="vt-table-head">
                <tr>
                  <th class="vt-table-head-cell">目标类</th>
                  <th class="vt-table-head-cell">当前样本</th>
                  <th class="vt-table-head-cell">目标倍数</th>
                  <th class="vt-table-head-cell">计划新增</th>
                  <th class="vt-table-head-cell">预计总计</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="row in augmentTargetPlanRows" :key="row.classId" class="vt-table-row">
                  <td class="vt-table-cell font-medium text-slate-800">{{ row.name }}</td>
                  <td class="vt-table-cell font-mono">{{ row.source }}</td>
                  <td class="vt-table-cell font-mono">{{ row.targetMultiplier }}x</td>
                  <td class="vt-table-cell font-mono">+{{ row.augmented }}</td>
                  <td class="vt-table-cell font-mono">{{ row.output }}</td>
                </tr>
              </tbody>
            </table>
          </div>
          <div
            v-if="augmentPreview.rebalance_eval_splits && (augmentPreview.estimated_eval?.val || augmentPreview.estimated_eval?.test)"
            class="grid grid-cols-1 gap-3 md:grid-cols-2"
          >
            <div v-if="augmentPreview.estimated_eval?.val" class="vt-stat-card">
              <div class="vt-stat-label">预计 val</div>
              <div class="mt-2 flex items-baseline justify-between gap-3">
                <span class="text-sm text-slate-500">总样本</span>
                <span class="font-mono text-lg font-semibold text-slate-800">{{ augmentPreview.estimated_eval.val.total }}</span>
              </div>
              <div class="mt-1 flex items-baseline justify-between gap-3">
                <span class="text-sm text-slate-500">目标类图片</span>
                <span class="font-mono text-sm font-semibold text-slate-800">{{ augmentPreview.estimated_eval.val.target }}</span>
              </div>
            </div>
            <div v-if="augmentPreview.estimated_eval?.test" class="vt-stat-card">
              <div class="vt-stat-label">预计 test</div>
              <div class="mt-2 flex items-baseline justify-between gap-3">
                <span class="text-sm text-slate-500">总样本</span>
                <span class="font-mono text-lg font-semibold text-slate-800">{{ augmentPreview.estimated_eval.test.total }}</span>
              </div>
              <div class="mt-1 flex items-baseline justify-between gap-3">
                <span class="text-sm text-slate-500">目标类图片</span>
                <span class="font-mono text-sm font-semibold text-slate-800">{{ augmentPreview.estimated_eval.test.target }}</span>
              </div>
            </div>
          </div>
        </div>
        <div class="flex justify-end gap-2 mt-6">
          <button
            class="vt-btn-secondary vt-btn-size-md"
            :disabled="isActionPending(AUGMENT_PREVIEW_ACTION_KEY) || isActionPending(AUGMENT_SUBMIT_ACTION_KEY)"
            @click="closeAugmentSubsetModal"
          >取消</button>
          <AsyncButton
            class="vt-btn-secondary vt-btn-size-md"
            :pending="isActionPending(AUGMENT_PREVIEW_ACTION_KEY)"
            :disabled="isActionPending(AUGMENT_SUBMIT_ACTION_KEY)"
            loading-text="处理中..."
            @click="runAugmentPreview"
          >
            先预估
          </AsyncButton>
          <AsyncButton
            class="vt-btn-solid-primary vt-btn-size-md"
            :pending="isActionPending(AUGMENT_SUBMIT_ACTION_KEY)"
            :disabled="isActionPending(AUGMENT_PREVIEW_ACTION_KEY) || !augmentConfig.newDatasetName"
            loading-text="生成中..."
            @click="runAugmentSubset"
          >
            开始生成
          </AsyncButton>
        </div>
      </div>
    </div>

    <div v-if="showMergeDatasetsModal" class="vt-modal-backdrop" @click.self="closeMergeDatasets">
      <div class="vt-modal-panel vt-modal-panel--lg p-5">
        <h3 class="text-lg font-bold mb-4">合并两个数据集</h3>
        <div class="mb-4 text-sm text-gray-600">仅支持类别完全一致的数据集合并；将合并 train/val/test 的 images 与 labels。</div>

        <div class="grid grid-cols-1 gap-4">
          <div class="text-sm text-gray-700">
            当前数据集：<span class="font-mono">{{ store.selectedDataset?.name }}</span>
          </div>

          <div>
            <label class="block text-sm font-medium text-gray-700 mb-2">选择另一个数据集</label>
            <select v-model="mergeOtherDataset" class="vt-select">
              <option v-for="n in mergeCandidates" :key="n" :value="n">{{ n }}</option>
            </select>
          </div>

          <div>
            <label class="block text-sm font-medium text-gray-700 mb-2">新数据集名称</label>
            <input v-model.trim="mergeNewDatasetName" class="vt-input" placeholder="例如：datasets_merge_01" />
          </div>
        </div>

        <div class="flex justify-end gap-2 mt-6">
          <button class="vt-btn-secondary vt-btn-size-md" :disabled="mergingDatasets" @click="closeMergeDatasets">取消</button>
          <button class="vt-btn-solid-primary vt-btn-size-md" :disabled="mergingDatasets || !mergeOtherDataset || !mergeNewDatasetName" @click="runMergeDatasets">
            {{ mergingDatasets ? '合并中...' : '开始合并' }}
          </button>
        </div>
      </div>
    </div>

    <div v-if="showReorderLabelsModal" class="vt-modal-backdrop" @click.self="closeReorderLabels">
      <div class="vt-modal-panel vt-modal-panel--lg p-5">
        <h3 class="text-lg font-bold mb-4">调整类别顺序</h3>
        <div class="mb-3 text-sm text-gray-600">该操作会批量重写当前数据集的标注文件（train/val/test 及 auto_labels）。</div>

        <div class="max-h-[420px] overflow-auto border border-gray-200 rounded-lg">
          <div
            v-for="(it, idx) in reorderItems"
            :key="it.oldIndex"
            class="flex items-center gap-2 px-3 py-2 border-b border-gray-100 last:border-b-0"
          >
            <div class="w-10 text-right font-mono text-sm text-gray-500">{{ idx }}</div>
            <div class="flex-1 text-sm text-gray-800 truncate">{{ it.name }}</div>
            <div class="flex gap-1">
              <button
                class="vt-btn-secondary vt-btn-size-sm"
                :disabled="idx === 0 || reorderingLabels"
                @click="moveReorderItem(idx, -1)"
              >
                上移
              </button>
              <button
                class="vt-btn-secondary vt-btn-size-sm"
                :disabled="idx === reorderItems.length - 1 || reorderingLabels"
                @click="moveReorderItem(idx, 1)"
              >
                下移
              </button>
            </div>
          </div>
        </div>

        <div class="flex justify-end gap-2 mt-4">
          <button class="vt-btn-secondary vt-btn-size-md" :disabled="reorderingLabels" @click="closeReorderLabels">取消</button>
          <button class="vt-btn-solid-primary vt-btn-size-md" :disabled="reorderingLabels || reorderItems.length === 0" @click="applyReorderLabels">
            {{ reorderingLabels ? '处理中...' : '应用' }}
          </button>
        </div>
      </div>
    </div>


    <UploadDatasetImagesModal
      :visible="showUploadImagesModal"
      :dataset-name="store.selectedDataset?.name || '数据集'"
      :split="uploadTargetSplit"
      @close="showUploadImagesModal = false"
      @submit="handleUploadImages"
    />

  </div>
</template>

<script setup>
import { ref, reactive, watch, onMounted, onUnmounted, computed, nextTick } from 'vue';
import {
  PopoverContent,
  PopoverPortal,
  PopoverRoot,
  PopoverTrigger,
} from 'reka-ui';
import { useRouter } from 'vue-router';
import { useMainStore } from '../stores/main';
import api from '../api';
import { useToast } from '../composables/useToast';
import { useApiCall } from '../composables/useApiCall';
import { useAsyncAction } from '../composables/useAsyncAction';
import { useConfirm } from '../composables/useConfirm';
import { useDatasetCapabilities } from '../composables/useDatasetCapabilities';
import { useDatasets } from '../composables/useDatasets';
import { useAutoFillGrid } from '../composables/useAutoFillGrid';
import {
  DATASET_ANNOTATION_MODE,
  DATASET_OPERATION,
} from '../utils/datasetCapabilities';
import { assertCapabilityGuard } from '../utils/capabilityGuards';
import { CATEGORY_NAME_PATTERN, validateCategoryName } from '../utils';
import { resolveTrainingDatasetGuard } from '../utils/trainingActionGuards';
import ClassificationAnnotator from './ClassificationAnnotator.vue';
import ImageAnnotator from './ImageAnnotator.vue';
import PoseAnnotator from './PoseAnnotator.vue';
import SegmentAnnotator from './SegmentAnnotator.vue';
import UploadDatasetImagesModal from './UploadDatasetImagesModal.vue';
import AppIcon from './ui/AppIcon.vue';
import AsyncButton from './ui/AsyncButton.vue';
import UiTooltip from './ui/Tooltip.vue';

const store = useMainStore();
const toast = useToast();
const apiCall = useApiCall();
const asyncAction = useAsyncAction();
const router = useRouter();
const { confirm: showConfirm } = useConfirm();
const { allDatasets, findDataset } = useDatasets();
const images = ref([]);
const loading = ref(false);
const total = ref(0);
const classList = ref([]);
const datasetInfo = ref(null);
const currentImage = ref(null);
const showAutoAnnotateModal = ref(false);
const autoAnnotateType = ref('pretrained');
const selectedModelPath = ref('');
const selectionMode = ref(false);
const selectedClassIds = ref([]);
const selectedMap = ref({});
const showCreateSubsetModal = ref(false);
const subsetName = ref('');
const deleting = ref(false);
const showReorderLabelsModal = ref(false);
const reorderItems = ref([]);
const reorderingLabels = ref(false);
const deletingLabelId = ref(null);
const showAddClassInput = ref(false);
const addClassInput = ref(null);
const newClassName = ref('');
const addingClass = ref(false);
const deduplicatingImages = ref(false);
const clearingAutoLabels = ref(false);
const showMergeDatasetsModal = ref(false);
const mergeOtherDataset = ref('');
const mergeNewDatasetName = ref('');
const mergingDatasets = ref(false);
const showAugmentSubsetModal = ref(false);
const augmentPreview = ref(null);
const AUGMENT_PREVIEW_ACTION_KEY = 'dataset-preview:augment-preview';
const AUGMENT_SUBMIT_ACTION_KEY = 'dataset-preview:augment-submit';
const augmentTargetClassPickerOpen = ref(false);
const showAugmentAdvancedOptions = ref(false);
const augmentConfig = reactive({
  targetClassConfigs: [],
  split: 'train',
  nonTargetKeepRatio: 1.0,
  evalTargetRatio: null,
  colorJitter: 0.2,
  seed: 42,
  enableHflip: true,
  enableVflip: false,
  copyEvalSplits: true,
  rebalanceEvalSplits: false,
  newDatasetName: ''
});
const pageInput = ref(1);
const isFullScreen = ref(false);
let activeImageRequestController = null;
const { gridClass: imageGridClass, gridStyle: imageGridStyle } = useAutoFillGrid(isFullScreen, {
  compactTile: 112,
  regularTile: 136,
  gapClass: 'gap-4',
});
const showAdvancedMenu = ref(false);
const showAutoAnnotateHelp = ref(false);
const advancedMenuRef = ref(null);
const showUploadImagesModal = ref(false);
const uploadTargetSplit = ref('train');
const buildDatasetNameSuffix = () => {
  const datePart = new Date().toISOString().slice(0, 10).replaceAll('-', '');
  const randomPart = Math.random().toString(36).slice(2, 6);
  return `${datePart}_${randomPart}`;
};
const buildDerivedDatasetName = (baseName, kind) => `${baseName || 'dataset'}_${kind}_${buildDatasetNameSuffix()}`;
const CREATE_SUBSET_ACTION_KEY = 'dataset-preview:create-subset';
const AUTO_ANNOTATE_ACTION_KEY = 'dataset-preview:auto-annotate-start';
const isActionPending = (key) => asyncAction.isPending(key);
const onAdvanced = (fn) => {
  showAdvancedMenu.value = false;
  fn && fn();
};

const openCreatedDataset = async (datasetName) => {
  const nextName = String(datasetName || '').trim();
  if (!nextName) return null;
  const nextProject = store.projects.find(p => p.id === store.currentProject?.id)
    || store.projects.find(p => p.path === store.currentProject?.path)
    || store.currentProject;
  const nextDataset = findDataset(nextName)
    || (nextProject?.datasets || []).find(d => d.name === nextName)
    || allDatasets.value.find(d => d.path?.endsWith(`/training/${nextName}`))
    || null;
  if (nextProject) store.selectProject(nextProject);
  if (nextDataset) {
    store.selectDataset(nextDataset);
    await router.push({
      name: 'dataset-detail',
      params: {
        project: encodeURIComponent(nextProject?.name || store.currentProject?.name || ''),
        name: encodeURIComponent(nextDataset.name),
      },
      query: {
        dataset_id: nextDataset.dataset_id || '',
      },
    });
  }
  return nextDataset;
};

const refreshSelectedDataset = async () => {
  const selectedName = store.selectedDataset?.name || '';
  const selectedPath = store.selectedDataset?.path || '';
  await store.fetchProjects({ silent: true });
  const nextDataset = findDataset(selectedName)
    || allDatasets.value.find(d => d.path === selectedPath)
    || null;
  if (nextDataset) {
    store.selectDataset(nextDataset);
  }
  return nextDataset;
};

const openUploadImagesModal = () => {
  uploadTargetSplit.value = String(filters.split || 'train');
  showUploadImagesModal.value = true;
};

const autoAnnotating = ref(false);
const autoAnnotateStatus = ref({ progress: 0, message: '', added: 0, pending: 0 });
const autoAnnotateTaskId = ref('');
let autoAnnotateTimer = null;

const stopAutoAnnotatePolling = () => {
  if (autoAnnotateTimer) {
    clearInterval(autoAnnotateTimer);
    autoAnnotateTimer = null;
  }
};

const filters = reactive({
  split: 'train',
  mode: 'include',
  unannotated: false,
  has_auto_label: false,
  offset: 0,
  limit: 60
});

const openAnnotator = (img) => {
  if (!manualAnnotationGuard.value.enabled) return;
  currentImage.value = img;
};

const selectedCount = computed(() => Object.keys(selectedMap.value).length);
const selectedDatasetSource = computed(() => datasetInfo.value || store.selectedDataset || null);
const { annotationMode, hasDatasetOperation, getDatasetOperationGuard } = useDatasetCapabilities(selectedDatasetSource);
const uploadImagesGuard = computed(() => getDatasetOperationGuard(DATASET_OPERATION.UPLOAD_IMAGES));
const manualAnnotationGuard = computed(() => getDatasetOperationGuard(DATASET_OPERATION.MANUAL_ANNOTATION));
const trainGuard = computed(() => resolveTrainingDatasetGuard(selectedDatasetSource.value));
const createSubsetGuard = computed(() => getDatasetOperationGuard(DATASET_OPERATION.CREATE_SUBSET));
const autoAnnotateGuard = computed(() => getDatasetOperationGuard(DATASET_OPERATION.AUTO_ANNOTATE, {
  visibleWhenUnsupported: true,
}));
const deduplicateGuard = computed(() => getDatasetOperationGuard(DATASET_OPERATION.DEDUPLICATE_IMAGES));
const mergeDatasetsGuard = computed(() => getDatasetOperationGuard(DATASET_OPERATION.MERGE_DATASETS));
const augmentDatasetGuard = computed(() => getDatasetOperationGuard(DATASET_OPERATION.AUGMENT_DATASET));
const datasetMetricLabel = computed(() => annotationMode.value === DATASET_ANNOTATION_MODE.IMAGE_CLASS ? '总样本' : '总目标');
const datasetMetricValue = computed(() => annotationMode.value === DATASET_ANNOTATION_MODE.IMAGE_CLASS
  ? Number(datasetInfo.value?.image_count || 0)
  : Number(datasetInfo.value?.total_objects || 0));
const canReorderLabels = computed(() => {
  if (!hasDatasetOperation(DATASET_OPERATION.REORDER_LABELS)) return false;
  const v = classList.value;
  if (Array.isArray(v)) return v.length > 0;
  if (v && typeof v === 'object') return Object.keys(v).length > 0;
  return false;
});
const hasDatasetOperations = computed(() => hasDatasetOperation(DATASET_OPERATION.DEDUPLICATE_IMAGES) || hasDatasetOperation(DATASET_OPERATION.MERGE_DATASETS));
const hasAdvancedOperations = computed(() => {
  return canReorderLabels.value
    || hasDatasetOperations.value
    || hasDatasetOperation(DATASET_OPERATION.AUTO_ANNOTATE)
    || hasDatasetOperation(DATASET_OPERATION.AUGMENT_DATASET);
});
const canAddClass = computed(() => hasDatasetOperation(DATASET_OPERATION.ADD_LABEL));
const totalPages = computed(() => Math.max(1, Math.ceil((total.value || 0) / (filters.limit || 1))));
const currentPage = computed(() => Math.min(totalPages.value, Math.floor((filters.offset || 0) / (filters.limit || 1)) + 1));
const mergeCandidates = computed(() => {
  const cur = store.selectedDataset?.name;
  return allDatasets.value
    .map(x => x?.name)
    .filter(n => n && n !== cur)
    .sort((a, b) => String(a).localeCompare(String(b)));
});
const augmentClassOptions = computed(() => {
  const stats = datasetInfo.value?.class_stats || [];
  return (stats || [])
    .map(s => ({ id: Number(s.id), name: String(s.name ?? ''), count: Number(s.count ?? 0) }))
    .filter(x => Number.isFinite(x.id) && x.name);
});
const clampAugmentTargetMultiplier = (value, fallback = 8) => {
  const numericValue = Number(value);
  if (!Number.isFinite(numericValue)) return fallback;
  return Math.max(1, Math.min(30, numericValue));
};
const augmentClassOptionMap = computed(() => {
  return new Map(augmentClassOptions.value.map(option => [Number(option.id), option]));
});
const selectedAugmentClasses = computed(() => {
  return (augmentConfig.targetClassConfigs || [])
    .map((config) => {
      const classId = Number(config.classId);
      const option = augmentClassOptionMap.value.get(classId);
      if (!option) return null;
      return {
        id: classId,
        classId,
        name: option.name,
        count: Number(option.count || 0),
        targetMultiplier: clampAugmentTargetMultiplier(config.targetMultiplier, 8),
      };
    })
    .filter(Boolean);
});
const augmentTargetClassSummary = computed(() => {
  const selected = selectedAugmentClasses.value;
  if (selected.length === 0) return '添加目标类';
  if (selected.length <= 2) {
    return selected.map(option => option.name).join('，');
  }
  return `已添加 ${selected.length} 个目标类`;
});
const augmentClassNameMap = computed(() => {
  return new Map(
    augmentClassOptions.value.map(option => [Number(option.id), String(option.name || option.id)])
  );
});
const augmentEvalMode = computed({
  get: () => (augmentConfig.rebalanceEvalSplits ? 'rebuild' : 'keep'),
  set: (value) => {
    const nextMode = String(value || 'keep');
    augmentConfig.rebalanceEvalSplits = nextMode === 'rebuild';
    augmentConfig.copyEvalSplits = nextMode !== 'rebuild';
  },
});
const augmentTargetPlanRows = computed(() => {
  const plan = augmentPreview.value?.target_class_plan;
  if (!plan) return [];
  const sourceCounts = plan.source_counts || {};
  const augmentedCounts = plan.planned_augmented_counts || {};
  const outputCounts = plan.estimated_output_counts || {};
  const targetMultipliers = plan.target_multipliers || {};
  const classIds = Array.from(
    new Set([
      ...Object.keys(sourceCounts),
      ...Object.keys(augmentedCounts),
      ...Object.keys(outputCounts),
    ])
  )
    .map(value => Number(value))
    .filter(Number.isFinite)
    .sort((a, b) => a - b);
  return classIds.map((classId) => ({
    classId,
    name: augmentClassNameMap.value.get(classId) || `ID ${classId}`,
    source: Number(sourceCounts[classId] || 0),
    targetMultiplier: Number(targetMultipliers[classId] || 1),
    augmented: Number(augmentedCounts[classId] || 0),
    output: Number(outputCounts[classId] || 0),
  }));
});

const isAugmentTargetClassSelected = (classId) => {
  return (augmentConfig.targetClassConfigs || []).some(item => Number(item.classId) === Number(classId));
};

const toggleAugmentTargetClass = (classId) => {
  const nextId = Number(classId);
  if (!Number.isFinite(nextId)) return;
  const exists = isAugmentTargetClassSelected(nextId);
  augmentConfig.targetClassConfigs = exists
    ? augmentConfig.targetClassConfigs.filter(item => Number(item.classId) !== nextId)
    : [...augmentConfig.targetClassConfigs, { classId: nextId, targetMultiplier: 8 }];
};

const clearAugmentTargetClasses = () => {
  augmentConfig.targetClassConfigs = [];
};

const removeAugmentTargetClass = (classId) => {
  augmentConfig.targetClassConfigs = augmentConfig.targetClassConfigs.filter(item => Number(item.classId) !== Number(classId));
};

const updateAugmentTargetMultiplier = (classId, value) => {
  const nextClassId = Number(classId);
  augmentConfig.targetClassConfigs = augmentConfig.targetClassConfigs.map((item) => {
    if (Number(item.classId) !== nextClassId) return item;
    return {
      ...item,
      targetMultiplier: clampAugmentTargetMultiplier(value, item.targetMultiplier),
    };
  });
};

watch(augmentClassOptions, (options) => {
  const validIds = new Set(options.map(option => Number(option.id)));
  augmentConfig.targetClassConfigs = (augmentConfig.targetClassConfigs || []).filter(item => validIds.has(Number(item.classId)));
});

const pretrainedModelOptions = computed(() => {
  return (store.autoAnnotateModels || []).filter((model) => model.type === 'pretrained');
});

const trainedModelOptions = computed(() => {
  return (store.autoAnnotateModels || [])
    .filter((model) => model.type === 'trained')
    .sort((a, b) => {
      if (a.created_at && b.created_at) {
        return new Date(b.created_at) - new Date(a.created_at);
      }
      return 0;
    })
    .map((model) => {
      const dataset = model?.dataset || store.selectedDataset?.name || 'Unknown Dataset';
      const runId = model?.source_run || '';
      return {
        key: `${runId}:${model.path}`,
        value: model.path,
        label: `[${dataset}] ${runId} - ${model.name}`,
      };
    });
});

const ensureAutoAnnotateModelsLoaded = async (type) => {
  if (!store.autoAnnotateModels.length) {
    await store.fetchModels(store.selectedDataset?.vision_task_type, 'auto_annotate');
  }
  if (type === 'pretrained' && pretrainedModelOptions.value.length > 0) {
    selectedModelPath.value = pretrainedModelOptions.value[0].path;
    return;
  }
  if (trainedModelOptions.value.length > 0) {
    selectedModelPath.value = trainedModelOptions.value[0].value;
  } else {
    selectedModelPath.value = '';
  }
};

watch(() => showAutoAnnotateModal.value, (val) => {
  if (val) {
    ensureAutoAnnotateModelsLoaded(autoAnnotateType.value).catch(() => {});
  }
});

watch(autoAnnotateType, (val) => {
  if (showAutoAnnotateModal.value) {
    ensureAutoAnnotateModelsLoaded(val).catch(() => {});
  }
});

const isSelected = (path) => !!selectedMap.value[path];

const toggleSelectionMode = () => {
  selectionMode.value = !selectionMode.value;
  selectedMap.value = {};
};

const selectAllCurrentPage = () => {
  const next = { ...selectedMap.value };
  images.value.forEach(img => {
    next[img.path] = true;
  });
  selectedMap.value = next;
};

const toggleClass = (id) => {
  if (selectedClassIds.value.includes(id)) {
    selectedClassIds.value = selectedClassIds.value.filter(x => x !== id);
  } else {
    selectedClassIds.value = [...selectedClassIds.value, id];
  }
};

const clearClasses = () => {
  selectedClassIds.value = [];
};

const onImageClick = (img) => {
  if (!selectionMode.value) {
    openAnnotator(img);
    return;
  }
  if (isSelected(img.path)) {
    const next = { ...selectedMap.value };
    delete next[img.path];
    selectedMap.value = next;
  } else {
    selectedMap.value = { ...selectedMap.value, [img.path]: true };
  }
};

const navImage = (dir) => {
  if (!currentImage.value) return;
  const idx = images.value.findIndex(i => i.path === currentImage.value.path);
  if (idx === -1) return;
  
  const newIdx = idx + dir;
  if (newIdx >= 0 && newIdx < images.value.length) {
    currentImage.value = images.value[newIdx];
  } else if (newIdx >= images.value.length) {
    if (currentPage.value < totalPages.value) {
      toast.info('已到达当前页末尾，请切换到下一页');
    }
  }
};

const onImageUpdate = (img) => {
  const targetIndex = images.value.findIndex(i => i.path === img.old_path || i.path === img.path);
  if (targetIndex !== -1) {
    images.value[targetIndex] = {
      ...images.value[targetIndex],
      ...img,
    };
  }
  if (currentImage.value && (currentImage.value.path === img.old_path || currentImage.value.path === img.path)) {
    currentImage.value = targetIndex !== -1 ? images.value[targetIndex] : {
      ...currentImage.value,
      ...img,
    };
  }
  if (filters.unannotated || filters.has_auto_label) {
    fetchImages(false);
  }
};

const fetchDatasetInfo = async () => {
  try {
    const infoRes = await api.getDatasetInfo({
      project_path: store.currentProject.path,
      dataset_name: store.selectedDataset.name
    });
    if (infoRes) {
      datasetInfo.value = infoRes || null;
      classList.value = infoRes?.names || [];
    }
  } catch (e) { console.error('Failed to load classes', e); }
};

const fetchImages = async (reset = false) => {
  if (!store.currentProject || !store.selectedDataset) return;
  
  if (reset) {
    images.value = [];
    filters.offset = 0;
    pageInput.value = 1;
  }
  
  if (activeImageRequestController) {
    activeImageRequestController.abort();
  }
  const controller = new AbortController();
  activeImageRequestController = controller;
  loading.value = true;
  try {
    const params = {
      project_path: store.currentProject.path,
      dataset_name: store.selectedDataset.name,
      split: filters.split,
      offset: filters.offset,
      limit: filters.limit,
      classes: selectedClassIds.value.length > 0 ? selectedClassIds.value.join(',') : undefined,
      unannotated: filters.unannotated,
      has_auto_label: filters.has_auto_label
    };
    const res = await api.getDatasetImages({ ...params }, { signal: controller.signal });
    images.value = res.items;
    total.value = res.total;
  } catch (err) {
    if (err?.code === 'ERR_CANCELED' || err?.name === 'CanceledError') return;
    console.error('Failed to fetch images:', err);
  } finally {
    if (activeImageRequestController === controller) {
      activeImageRequestController = null;
      loading.value = false;
    }
  }
};

const listFilteredImagePaths = async () => {
  const pageSize = 500;
  let offset = 0;
  const pathSet = new Set();

  while (true) {
    const params = {
      project_path: store.currentProject.path,
      dataset_name: store.selectedDataset.name,
      split: filters.split,
      offset,
      limit: pageSize,
      classes: selectedClassIds.value.length > 0 ? selectedClassIds.value.join(',') : undefined,
      unannotated: filters.unannotated,
      has_auto_label: filters.has_auto_label
    };
    const res = await api.getDatasetImages({ ...params });
    const pageItems = Array.isArray(res.items) ? res.items : [];
    pageItems.forEach(it => {
      if (it?.path) {
        pathSet.add(it.path);
      }
    });
    const totalCount = Number(res.total || 0);
    offset += pageItems.length;
    if (pageItems.length === 0 || offset >= totalCount) {
      break;
    }
  }

  return Array.from(pathSet);
};

const applyFilters = () => {
  selectedMap.value = {};
  filters.offset = 0;
  pageInput.value = 1;
  fetchImages(true);
};

const handleUploadImages = async ({ split, files, onProgress, onDone }) => {
  try {
    const formData = new FormData();
    formData.append('project_path', store.currentProject.path);
    formData.append('dataset_name', store.selectedDataset.name);
    formData.append('split', split);
    for (const file of files || []) {
      formData.append('files', file);
    }
    const res = await api.uploadDatasetImages(formData, onProgress);
    await refreshSelectedDataset();
    await fetchDatasetInfo();
    if (filters.split !== split) {
      filters.split = split;
    } else {
      applyFilters();
    }
    toast.success(`已上传 ${res?.count || 0} 张图片到 ${split}`);
    showUploadImagesModal.value = false;
    onDone && onDone();
  } catch (err) {
    onDone && onDone(err);
  }
};

const goPrevPage = () => {
  if (loading.value) return;
  if (currentPage.value <= 1) return;
  pageInput.value = currentPage.value - 1;
  jumpPage();
};

const goNextPage = () => {
  if (loading.value) return;
  if (currentPage.value >= totalPages.value) return;
  pageInput.value = currentPage.value + 1;
  jumpPage();
};

const jumpPage = () => {
  if (loading.value) return;
  const p = Math.max(1, Math.min(totalPages.value, Number(pageInput.value || 1)));
  pageInput.value = p;
  if (!selectionMode.value) {
    selectedMap.value = {};
  }
  filters.offset = (p - 1) * filters.limit;
  fetchImages(false);
};

// 跳转到训练页
const goToTrain = () => {
  if (!store.selectedDataset) return;
  if (!assertCapabilityGuard(trainGuard.value, toast.warn)) return;
  router.push({
    name: 'dataset-train',
    params: {
      project: encodeURIComponent(store.currentProject?.name || ''),
      name: encodeURIComponent(store.selectedDataset.name),
    },
    query: {
      dataset_id: store.selectedDataset.dataset_id || '',
    },
  });
};

const openCreateSubset = () => {
  if (!createSubsetGuard.value.enabled) return;
  const base = store.selectedDataset?.name || 'dataset';
  subsetName.value = buildDerivedDatasetName(base, 'subset');
  showCreateSubsetModal.value = true;
};

const closeCreateSubset = () => {
  showCreateSubsetModal.value = false;
  subsetName.value = '';
};

const openAugmentSubsetModal = () => {
  if (!augmentDatasetGuard.value.enabled) return;
  const classes = augmentClassOptions.value;
  const first = classes[0];
  const base = store.selectedDataset?.name || 'dataset';
  if (!augmentConfig.targetClassConfigs || augmentConfig.targetClassConfigs.length === 0) {
    if (first) {
       augmentConfig.targetClassConfigs = [{ classId: first.id, targetMultiplier: 8 }];
    }
  }
  augmentConfig.split = 'train';
  augmentConfig.nonTargetKeepRatio = 1.0;
  augmentConfig.evalTargetRatio = null;
  augmentConfig.colorJitter = 0.2;
  augmentConfig.seed = 42;
  augmentConfig.enableHflip = true;
  augmentConfig.enableVflip = false;
  augmentConfig.copyEvalSplits = true;
  augmentConfig.rebalanceEvalSplits = false;
  showAugmentAdvancedOptions.value = false;
  augmentConfig.newDatasetName = buildDerivedDatasetName(base, 'comp');
  augmentPreview.value = null;
  showAugmentSubsetModal.value = true;
};

const closeAugmentSubsetModal = () => {
  showAugmentSubsetModal.value = false;
  showAugmentAdvancedOptions.value = false;
  augmentPreview.value = null;
};

const buildAugmentPayload = (withDryRun = false) => {
  const nonTargetKeepRatio = Math.max(0, Math.min(1, Number(augmentConfig.nonTargetKeepRatio || 0)));
  const colorJitter = Math.max(0, Math.min(0.8, Number(augmentConfig.colorJitter || 0)));
  const payload = {
    project_path: store.currentProject.path,
    source_dataset: store.selectedDataset.name,
    new_dataset_name: augmentConfig.newDatasetName,
    split: augmentConfig.split,
    target_class_configs: selectedAugmentClasses.value.map(option => ({
      class_id: Number(option.id),
      name: String(option.name || option.id),
      target_multiplier: clampAugmentTargetMultiplier(option.targetMultiplier, 8),
    })),
    non_target_keep_ratio: nonTargetKeepRatio,
    seed: Number(augmentConfig.seed || 42),
    copy_eval_splits: !!augmentConfig.copyEvalSplits,
    rebalance_eval_splits: !!augmentConfig.rebalanceEvalSplits,
    enable_hflip: !!augmentConfig.enableHflip,
    enable_vflip: !!augmentConfig.enableVflip,
    color_jitter: colorJitter
  };
  if (augmentConfig.rebalanceEvalSplits && augmentConfig.evalTargetRatio !== null && augmentConfig.evalTargetRatio !== '' && Number.isFinite(Number(augmentConfig.evalTargetRatio))) {
    payload.eval_target_ratio = Math.max(0, Math.min(1, Number(augmentConfig.evalTargetRatio)));
  }
  if (withDryRun) {
    payload.dry_run = true;
  }
  return payload;
};

const runAugmentPreview = async () => {
  if (!store.currentProject?.path || !store.selectedDataset?.name) return;
  await asyncAction.run(AUGMENT_PREVIEW_ACTION_KEY, async () => {
    await apiCall(api.previewAugmentedSubset(buildAugmentPayload(true)), {
      errorMsg: '预估失败',
      onSuccess: (data) => {
        augmentPreview.value = data;
      },
    });
  });
};

const runAugmentSubset = async () => {
  if (!store.currentProject?.path || !store.selectedDataset?.name) return;
  if (!augmentConfig.newDatasetName) return;
  if (!augmentConfig.targetClassConfigs || augmentConfig.targetClassConfigs.length === 0) {
    toast.warn('请选择至少一个目标类别');
    return;
  }
  const nonTargetKeepRatio = Math.max(0, Math.min(1, Number(augmentConfig.nonTargetKeepRatio || 0)));
  const evalMode = augmentConfig.rebalanceEvalSplits ? '重建 val/test' : (augmentConfig.copyEvalSplits ? '复制原 val/test' : '不生成 val/test');
  const targetClassText = selectedAugmentClasses.value
    .map(option => `${option.name} × ${clampAugmentTargetMultiplier(option.targetMultiplier, 8)}`)
    .join('\n');
  if (!await showConfirm({
    message: `确定生成增强子集吗？\n目标类设置:\n${targetClassText}\n非目标图片保留比例: ${nonTargetKeepRatio}\n评估集策略: ${evalMode}`,
    title: '生成增强子集',
    confirmText: '生成',
  })) return;

  await asyncAction.run(AUGMENT_SUBMIT_ACTION_KEY, async () => {
    await apiCall(api.createAugmentedSubset(buildAugmentPayload(false)), {
      onSuccess: async (data) => {
        await store.fetchProjects({ silent: true });
        await openCreatedDataset(augmentConfig.newDatasetName);
        closeAugmentSubsetModal();
        toast.success(data.message || '增强子集创建成功');
      },
      errorMsg: '增强子集创建失败',
    });
  });
};

const openReorderLabels = () => {
  if (!canReorderLabels.value) return;
  const v = classList.value;
  let names = [];
  if (Array.isArray(v)) {
    names = v;
  } else if (v && typeof v === 'object') {
    names = Object.keys(v)
      .map(k => ({ k: Number(k), name: v[k] }))
      .sort((a, b) => a.k - b.k)
      .map(x => x.name);
  }
  reorderItems.value = (names || []).map((name, idx) => ({ oldIndex: idx, name }));
  showReorderLabelsModal.value = true;
};

const closeReorderLabels = () => {
  showReorderLabelsModal.value = false;
  reorderItems.value = [];
};

// 顶部 chip 区直接删除类别：复用同一 deleteDatasetLabel 接口，删除前二次确认。
const onDeleteClassChip = async (s) => {
  if (!s || deletingLabelId.value !== null) return;
  if (!await showConfirm({
    message: `确定要删除类别「${s.name}」吗？\n该操作会批量修改标注文件，且不可撤销。`,
    title: '删除类别',
    danger: true,
    confirmText: '删除',
  })) return;
  deletingLabelId.value = s.id;
  await apiCall(api.deleteDatasetLabel({
    project_path: store.currentProject.path,
    dataset_name: store.selectedDataset.name,
    class_id: s.id,
  }), {
    errorMsg: '删除类别失败',
    onSuccess: async (data) => {
      const delId = Number(data.deleted_label_id);
      selectedClassIds.value = (selectedClassIds.value || [])
        .filter(x => x !== delId)
        .map(x => (x > delId ? x - 1 : x));
      await fetchDatasetInfo();
      applyFilters();
      toast.success(`已删除「${data.deleted_label_name}」`);
    },
    finally: () => { deletingLabelId.value = null; },
  });
};

// 顶部 chip 区加号：点击展开输入；Enter 或点 ✓ 创建类别；Esc / blur 仅关闭面板不调接口。
const toggleAddClassInput = async () => {
  if (!canAddClass.value) return;
  showAddClassInput.value = !showAddClassInput.value;
  if (showAddClassInput.value) {
    await nextTick();
    addClassInput.value && addClassInput.value.focus();
  }
};
const cancelAddClass = () => {
  if (!showAddClassInput.value) return;
  showAddClassInput.value = false;
  newClassName.value = '';
};
const commitAddClass = async () => {
  const raw = String(newClassName.value || '').trim();
  if (!raw) return;
  if (addingClass.value) return;
  if (!CATEGORY_NAME_PATTERN.test(raw)) {
    toast.warn(`类别名「${raw}」${validateCategoryName(raw)}`);
    newClassName.value = '';
    return;
  }
  addingClass.value = true;
  await apiCall(api.addDatasetLabel({
    project_path: store.currentProject.path,
    dataset_name: store.selectedDataset.name,
    label_name: raw,
  }), {
    errorMsg: '添加类别失败',
    onSuccess: async (data) => {
      newClassName.value = '';
      await fetchDatasetInfo();
      toast.success(`已添加类别「${data?.added_label_name || raw}」`);
    },
  });
  addingClass.value = false;
  // 成功或失败都保持面板打开，便于连续添加；追加 focus 防止 input 因 toast 重排导致焦点丢失。
  if (showAddClassInput.value) {
    await nextTick();
    addClassInput.value && addClassInput.value.focus();
  }
};

const deduplicateImages = async () => {
  if (!deduplicateGuard.value.enabled || deduplicatingImages.value) return;
  if (!store.currentProject?.path || !store.selectedDataset?.name) return;
  if (!await showConfirm({
    message: '确定要按图片MD5去重吗？\n该操作会删除重复图片及其对应的标签文件，且不可撤销。',
    title: '图片去重',
    danger: true,
    confirmText: '去重',
  })) return;
  deduplicatingImages.value = true;
  await apiCall(api.deduplicateDatasetImages({
    project_path: store.currentProject.path,
    dataset_name: store.selectedDataset.name,
    keep_split: 'train'
  }), {
    errorMsg: '处理失败',
    onSuccess: async (data) => {
      await fetchDatasetInfo();
      applyFilters();
      toast.success(`去重完成：扫描 ${data.scanned_images || 0} 张，唯一 ${data.unique_images || 0} 张，删除重复 ${data.deleted_images || 0} 张，删除标签文件 ${data.deleted_label_files || 0} 个`);
    },
    finally: () => { deduplicatingImages.value = false; },
  });
};

const clearAutoLabels = async () => {
  if (!store.currentProject?.path || !store.selectedDataset?.name || clearingAutoLabels.value) return;
  if (!assertCapabilityGuard(autoAnnotateGuard.value, toast.warn)) return;
  if (!await showConfirm({
    message: '确定要清除当前数据集中的所有待复核标注吗？\n该操作只会删除自动标注文件，不会删除人工标签，且不可撤销。',
    title: '清除待复核标注',
    danger: true,
    confirmText: '清除',
  })) return;
  clearingAutoLabels.value = true;
  await apiCall(api.clearDatasetAutoLabels({
    project_path: store.currentProject.path,
    dataset_name: store.selectedDataset.name,
  }), {
    errorMsg: '清除失败',
    onSuccess: async (data) => {
      if (currentImage.value) {
        currentImage.value = {
          ...currentImage.value,
          pending: false,
          has_auto_label: false,
        };
      }
      await fetchDatasetInfo();
      applyFilters();
      toast.success(`已清除待复核标注：删除 ${data.deleted_auto_label_files || 0} 个自动标注文件`);
    },
    finally: () => { clearingAutoLabels.value = false; },
  });
};

const normalizeNames = (v) => {
  if (Array.isArray(v)) return v.map(x => String(x));
  if (v && typeof v === 'object') {
    return Object.keys(v)
      .map(k => ({ k: Number(k), name: v[k] }))
      .filter(x => Number.isFinite(x.k))
      .sort((a, b) => a.k - b.k)
      .map(x => String(x.name));
  }
  return [];
};

const openMergeDatasets = () => {
  if (!mergeDatasetsGuard.value.enabled) return;
  const cand = mergeCandidates.value;
  mergeOtherDataset.value = cand[0] || '';
  const a = store.selectedDataset?.name || 'dataset';
  const b = mergeOtherDataset.value || 'dataset';
  mergeNewDatasetName.value = `${a}_merge_${b}_${new Date().toISOString().slice(0, 10).replaceAll('-', '')}`;
  showMergeDatasetsModal.value = true;
};

const closeMergeDatasets = () => {
  showMergeDatasetsModal.value = false;
  mergeOtherDataset.value = '';
  mergeNewDatasetName.value = '';
};

const runMergeDatasets = async () => {
  if (!store.currentProject?.path || !store.selectedDataset?.name || mergingDatasets.value) return;
  const other = String(mergeOtherDataset.value || '').trim();
  const newName = String(mergeNewDatasetName.value || '').trim();
  if (!other || !newName) return;
  if (!await showConfirm({
    message: `确定要合并数据集吗？\n${store.selectedDataset.name} + ${other} => ${newName}\n该操作会创建新数据集目录，并复制图片与标签。`,
    title: '合并数据集',
    confirmText: '合并',
  })) return;

  mergingDatasets.value = true;
  const otherInfo = await apiCall(api.getDatasetInfo({
    project_path: store.currentProject.path,
    dataset_name: other
  }), {
    errorMsg: '无法读取另一个数据集信息',
    finally: () => { mergingDatasets.value = false; },
  });
  if (!otherInfo) return;
  const curNames = normalizeNames(classList.value);
  const otherNames = normalizeNames(otherInfo?.names);
  if (curNames.join('\n') !== otherNames.join('\n')) {
    toast.error('两个数据集类别不一致，无法合并');
    mergingDatasets.value = false;
    return;
  }

  await apiCall(api.mergeDatasets({
    project_path: store.currentProject.path,
    dataset_a: store.selectedDataset.name,
    dataset_b: other,
    new_dataset_name: newName
  }), {
    errorMsg: '处理失败',
    onSuccess: async (data) => {
      await store.fetchProjects({ silent: true });
      await openCreatedDataset(newName);
      closeMergeDatasets();
      toast.success(data?.message || '合并完成，正在建立初始快照');
    },
    finally: () => { mergingDatasets.value = false; },
  });
};

const moveReorderItem = (idx, dir) => {
  const nextIdx = idx + dir;
  if (nextIdx < 0 || nextIdx >= reorderItems.value.length) return;
  const arr = [...reorderItems.value];
  const tmp = arr[idx];
  arr[idx] = arr[nextIdx];
  arr[nextIdx] = tmp;
  reorderItems.value = arr;
};

const applyReorderLabels = async () => {
  if (reorderingLabels.value) return;
  const order = reorderItems.value.map(it => it.oldIndex);
  if (order.length === 0) return;
  if (!await showConfirm({
    message: '确定要应用当前类别顺序吗？这会批量修改标注文件。',
    title: '应用类别顺序',
    danger: true,
    confirmText: '应用',
  })) return;
  reorderingLabels.value = true;
  await apiCall(api.reorderDatasetLabels({
    project_path: store.currentProject.path,
    dataset_name: store.selectedDataset.name,
    order
  }), {
    errorMsg: '处理失败',
    onSuccess: async (data) => {
      const map = {};
      order.forEach((oldIdx, newIdx) => { map[oldIdx] = newIdx; });
      selectedClassIds.value = (selectedClassIds.value || [])
        .map(oldIdx => map[oldIdx])
        .filter(v => v !== undefined && v !== null);
      closeReorderLabels();
      await fetchDatasetInfo();
      applyFilters();
      toast.success(`已更新：文件 ${data.updated_files || 0} 个，行 ${data.updated_lines || 0} 行`);
    },
    finally: () => { reorderingLabels.value = false; },
  });
};

const createSubset = async () => {
  if (!subsetName.value) return;
  const imagePaths = Object.keys(selectedMap.value);
  if (imagePaths.length === 0) return;
  const nextSubsetName = subsetName.value;
  await asyncAction.run(CREATE_SUBSET_ACTION_KEY, async () => {
    const data = await apiCall(api.createDatasetSubset({
      project_path: store.currentProject.path,
      source_dataset: store.selectedDataset.name,
      new_dataset_name: nextSubsetName,
      image_paths: imagePaths
    }), {
      errorMsg: '创建失败',
    });
    if (!data) return;
    await store.fetchProjects({ silent: true });
    await openCreatedDataset(nextSubsetName);
    closeCreateSubset();
    selectionMode.value = false;
    selectedMap.value = {};
    toast.success(data.message || '创建成功');
  });
};

const batchDelete = async () => {
  if (deleting.value) return;
  const imagePaths = Object.keys(selectedMap.value);
  if (imagePaths.length === 0) return;
  if (!await showConfirm({
    message: `确定要删除选中的 ${imagePaths.length} 张图片及其标注文件吗？`,
    title: '删除图片',
    danger: true,
    confirmText: '删除',
  })) return;
  deleting.value = true;
  await apiCall(api.batchDeleteDatasetImages({
    project_path: store.currentProject.path,
    dataset_name: store.selectedDataset.name,
    split: filters.split,
    image_paths: imagePaths
  }), {
    onSuccess: async (data) => {
      selectedMap.value = {};
      await fetchImages(false);
      if (images.value.length === 0 && (filters.offset || 0) > 0) {
        filters.offset = Math.max(0, (filters.offset || 0) - (filters.limit || 0));
        pageInput.value = Math.floor((filters.offset || 0) / (filters.limit || 1)) + 1;
        await fetchImages(false);
      }
      toast.success(`成功删除 ${data.deleted_count || 0} 张图片`);
    },
    errorMsg: '删除失败',
    finally: () => { deleting.value = false; },
  });
};

const runAutoAnnotate = async () => {
  if (autoAnnotating.value) return;
  if (!assertCapabilityGuard(autoAnnotateGuard.value, toast.warn)) return;
  await asyncAction.run(AUTO_ANNOTATE_ACTION_KEY, async () => {
    const imagePaths = await listFilteredImagePaths();
    if (imagePaths.length === 0) {
      toast.warn('当前筛选条件下没有可标注图片');
      return;
    }
    showAutoAnnotateModal.value = false;
    await apiCall(api.autoAnnotate({
      project_path: store.currentProject.path,
      dataset_name: store.selectedDataset.name,
      split: filters.split,
      image_paths: imagePaths,
      model_path: selectedModelPath.value,
      conf: 0.25,
      iou_thresh: 0.7
    }), {
      errorMsg: '自动标注启动失败',
      onSuccess: (data) => {
        const taskId = String(data?.task_id || '').trim();
        if (!taskId) {
          autoAnnotating.value = false;
          autoAnnotateTaskId.value = '';
          toast.error('自动标注启动成功，但未返回 task_id');
          return;
        }
        autoAnnotateTaskId.value = taskId;
        autoAnnotating.value = true;
        autoAnnotateStatus.value = { progress: 0, message: `初始化(${imagePaths.length}张)...`, added: 0, pending: 0 };
        pollAutoAnnotateStatus();
      }
    });
  });
};

const pollAutoAnnotateStatus = () => {
  const taskId = String(autoAnnotateTaskId.value || '').trim();
  if (!taskId) {
    autoAnnotating.value = false;
    toast.error('缺少 task_id，无法查询自动标注状态');
    return;
  }
  stopAutoAnnotatePolling();
  autoAnnotateTimer = setInterval(async () => {
    try {
      const res = await api.getAutoAnnotateStatus({ task_id: taskId });
      const s = res || {};
      autoAnnotateStatus.value = s;
      if (!s.is_running) {
        stopAutoAnnotatePolling();
        autoAnnotating.value = false;
        autoAnnotateTaskId.value = '';
        setTimeout(() => {
          if (s.error) {
            toast.error(s.error || '自动标注失败');
          } else {
            toast.success(`自动标注完成！新增标注: ${s.added || 0}，新增待复核: ${s.pending || 0}`);
            fetchImages(true);
          }
        }, 300);
      }
    } catch (e) {
      stopAutoAnnotatePolling();
      autoAnnotating.value = false;
      autoAnnotateTaskId.value = '';
      toast.error(e?.message || '自动标注状态查询失败');
      console.error(e);
    }
  }, 1000);
};

watch(() => store.selectedDataset?.path || '', () => {
  if (store.selectedDataset?.path) {
    fetchImages(true);
    fetchDatasetInfo();
    selectionMode.value = false;
    selectedMap.value = {};
    selectedClassIds.value = [];
  }
}, { immediate: true });

watch(() => filters.split, () => applyFilters());

const handleGlobalKeydown = (e) => {
  if (e.defaultPrevented) return;
  if (e.ctrlKey || e.metaKey || e.altKey) return;
  if (!store.selectedDataset) return;
  if (currentImage.value || showAutoAnnotateModal.value || showCreateSubsetModal.value || showAugmentSubsetModal.value) return;

  const el = e.target;
  const tag = el?.tagName?.toLowerCase?.();
  if (tag === 'input' || tag === 'textarea' || tag === 'select' || el?.isContentEditable) return;

  if (e.key === 'ArrowLeft') {
    if (currentPage.value > 1) {
      e.preventDefault();
      goPrevPage();
    }
  } else if (e.key === 'ArrowRight') {
    if (currentPage.value < totalPages.value) {
      e.preventDefault();
      goNextPage();
    }
  }
};

onMounted(() => {
  window.addEventListener('keydown', handleGlobalKeydown);
  document.addEventListener('click', onDocClick);
});

onUnmounted(() => {
  stopAutoAnnotatePolling();
  if (activeImageRequestController) {
    activeImageRequestController.abort();
    activeImageRequestController = null;
  }
  window.removeEventListener('keydown', handleGlobalKeydown);
  document.removeEventListener('click', onDocClick);
});

const onDocClick = (e) => {
  if (!showAdvancedMenu.value) return;
  if (advancedMenuRef.value && !advancedMenuRef.value.contains(e.target)) {
    showAdvancedMenu.value = false;
  }
};
</script>
