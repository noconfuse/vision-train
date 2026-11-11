<template>
  <div class="bg-white flex flex-col h-full min-h-0 p-4">
    <!-- A: 页头 —— 数据集名 + 全量指标 + 数据集级动作 -->
    <div class="mb-3 flex items-center justify-between gap-3">
      <div class="flex min-w-0 items-baseline gap-3">
        <h2 class="shrink-0 text-base font-semibold text-slate-800">{{ store.selectedDataset?.name }}</h2>
        <div v-if="datasetInfo" class="truncate text-xs text-slate-500">
          <span class="font-mono text-slate-700">{{ datasetInfo.image_count }}</span> 张 ·
          已标注 <span class="font-mono text-slate-700">{{ annotatedPercent }}</span> ·
          {{ datasetMetricLabel }}
          <span class="font-mono text-slate-700">{{ datasetMetricValue }}</span>
        </div>
      </div>
      <div class="flex shrink-0 items-center gap-2">
        <button
          v-if="uploadImagesGuard.visible"
          class="vt-btn-solid-primary vt-btn-size-md"
          :disabled="!uploadImagesGuard.enabled"
          @click="openUploadImagesModal"
        >
          <AppIcon name="upload" class="h-4 w-4" />
          上传图片
        </button>
        <UiTooltip v-if="hasDatasetOperation(DATASET_OPERATION.AUTO_ANNOTATE)" side="bottom" content-class="max-w-[16rem]">
          <template #trigger>
            <button
              class="vt-btn-secondary vt-btn-size-md"
              @click="showAutoAnnotateModal = true"
            >
              <AppIcon name="sparkles" class="h-4 w-4" />
              自动标注
            </button>
          </template>
          对<strong class="text-white">当前筛选条件</strong>下的图片用选定模型预标注，结果保存为「待复核」，可逐张确认或修正。
        </UiTooltip>
        <div ref="moreMenuRef" class="relative">
          <button class="vt-icon-btn" aria-label="更多操作" @click="showMoreMenu = !showMoreMenu">
            <AppIcon name="moreHorizontal" class="h-4 w-4" />
          </button>
          <div
            v-if="showMoreMenu"
            class="absolute right-0 top-full z-30 mt-1 w-40 border border-gray-200 bg-white py-1 shadow-sm"
          >
            <button class="vt-menu-item" @click="onAdvanced(toggleSelectionMode)">
              {{ selectionMode ? '退出选择模式' : '选择模式' }}
            </button>
            <button
              v-if="canAddClass || canDeleteClass || canReorderLabels"
              class="vt-menu-item"
              @click="onAdvanced(openClassManager)"
            >
              类别管理
            </button>
            <button v-if="canReorderLabels" class="vt-menu-item" @click="onAdvanced(openReorderLabels)">
              调整类别顺序
            </button>
            <div v-if="hasDatasetOperations || augmentDatasetGuard.visible || hasDatasetOperation(DATASET_OPERATION.AUTO_ANNOTATE)" class="my-1 border-t border-gray-100"></div>
            <button
              v-if="hasDatasetOperation(DATASET_OPERATION.DEDUPLICATE_IMAGES)"
              class="vt-menu-item"
              :disabled="deduplicatingImages"
              @click="onAdvanced(deduplicateImages)"
            >
              {{ deduplicatingImages ? '去重处理中...' : '图片去重（MD5）' }}
            </button>
            <button
              v-if="hasDatasetOperation(DATASET_OPERATION.MERGE_DATASETS)"
              class="vt-menu-item"
              :disabled="mergingDatasets || otherDatasetNames.length === 0"
              @click="onAdvanced(openMergeDatasets)"
            >
              {{ mergingDatasets ? '合并处理中...' : '合并数据集' }}
            </button>
            <button
              v-if="augmentDatasetGuard.visible"
              class="vt-menu-item"
              :disabled="isActionPending(AUGMENT_PREVIEW_ACTION_KEY) || isActionPending(AUGMENT_SUBMIT_ACTION_KEY)"
              @click="onAdvanced(openAugmentSubsetModal)"
            >
              弱类补偿采样
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- B: 工具条 —— 筛选与分页常驻；选择模式在上方追加一条选择态操作条，不顶掉分页 -->
    <div class="mb-3 rounded-lg border border-gray-200 bg-gray-50 px-2.5 py-1.5">
      <div v-if="selectionMode" class="mb-1.5 flex flex-wrap items-center justify-between gap-2 border-b border-gray-200 pb-1.5">
        <div class="text-xs">
          已选 <span class="font-mono font-semibold">{{ selectedCount }}</span> 张
          <span class="text-gray-500">/ 当前筛选 {{ total }} 张</span>
        </div>
        <div class="flex flex-wrap items-center gap-2">
          <button class="vt-btn-secondary vt-btn-size-sm" :disabled="images.length === 0" @click="selectAllCurrentPage">全选本页</button>
          <button
            class="vt-btn-secondary vt-btn-size-sm"
            :disabled="selectingAll || total === 0"
            title="按当前 split / 搜索 / 类别 / 标注状态筛选，跨分页全部选中"
            @click="selectAllFiltered"
          >
            {{ selectingAll ? '正在收集...' : `全选筛选结果（${total} 张）` }}
          </button>
          <button class="vt-btn-link text-xs" :disabled="selectedCount === 0" @click="clearSelection">清空选择</button>
          <button
            v-if="createSubsetGuard.visible"
            class="vt-btn-secondary vt-btn-size-sm"
            :disabled="selectedCount === 0 || !createSubsetGuard.enabled"
            @click="openCreateSubset"
          >
            生成子集
          </button>
          <button
            class="vt-btn-solid-danger vt-btn-size-sm"
            :disabled="selectedCount === 0 || deleting"
            @click="batchDelete"
          >
            {{ deleting ? '删除中...' : '删除选中' }}
          </button>
          <button class="vt-btn-link text-xs" @click="toggleSelectionMode">退出选择模式</button>
        </div>
      </div>

      <!-- 审查批量条：审查的就是当前筛出来的这一批图，所以「整批收下」和「整批作废」放在这里，不藏进菜单 -->
      <div v-if="reviewMode" class="mb-1.5 flex flex-wrap items-center justify-between gap-2 border-b border-gray-200 pb-1.5">
        <div class="text-xs">
          审查 {{ filters.has_auto_label ? '待复核' : '当前筛选' }}
          <span class="font-mono font-semibold">{{ foldSummary }}</span>
          <span v-if="!filters.has_auto_label" class="text-gray-500">· 其中待复核 {{ pendingTotal }} 张</span>
          <span class="text-gray-500">· {{ pendingBatchScope }}</span>
        </div>
        <div class="flex flex-wrap items-center gap-2">
          <span class="text-xs text-gray-400" title="缩略图上的框和标注弹窗里同一套：颜色是类别，有底色的是还没审的候选，只有描边的是已标注">
            底色待审 / 描边已标注
          </span>
          <button
            class="vt-btn-secondary vt-btn-size-sm"
            :disabled="clearingPending || pendingBatchBusy || pendingTotal === 0"
            title="删掉这一批还没审的候选框，人工标签不动；同样的模型和置信度再跑一轮就会重新生成"
            @click="clearPendingCandidates"
          >
            {{ clearingPending ? '清空中...' : '清空这批候选' }}
          </button>
          <button
            class="vt-btn-solid-primary vt-btn-size-sm"
            :disabled="committingPending || pendingBatchBusy || pendingTotal === 0"
            title="把当前筛选里还有候选的图逐张收下写进人工标签，就是逐张点保存那一下的批量版；没有候选的图不碰"
            @click="commitPendingCandidates"
          >
            {{ committingPending ? '写入中...' : pendingBatchBusy ? '正在数有多少张...' : `批量写入 ${pendingTotal} 张` }}
          </button>
        </div>
      </div>

      <div class="flex flex-wrap items-center gap-x-3 gap-y-1.5">
        <div class="flex shrink-0 items-center">
          <span
            v-if="isSearchMode"
            class="rounded bg-blue-50 px-2 py-1 text-xs font-medium text-[var(--vt-color-primary)]"
            title="搜索不限 split，train / val / test 一起匹配"
          >跨 train / val / test</span>
          <template v-else>
            <button
              v-for="s in SPLIT_OPTIONS"
              :key="s"
              class="vt-segmented-tab vt-segmented-tab--compact"
              :class="{ 'vt-segmented-tab--active': filters.split === s }"
              @click="filters.split = s"
            >
              {{ s }}
            </button>
          </template>
        </div>

        <span class="h-4 w-px shrink-0 bg-gray-200"></span>

        <div class="relative flex shrink-0 items-center">
          <AppIcon name="search" class="pointer-events-none absolute left-2 h-3.5 w-3.5 text-gray-400" />
          <input
            :value="filters.keyword"
            type="text"
            placeholder="搜图片名"
            class="vt-input vt-control-sm vt-input--with-both w-40"
            title="按文件名模糊匹配，train / val / test 一起找"
            @input="onKeywordInput($event.target.value)"
          />
          <button
            v-if="filters.keyword"
            class="absolute right-1.5 text-gray-400 hover:text-gray-600"
            aria-label="清空搜索"
            @click="clearKeyword"
          >
            <AppIcon name="close" class="h-3.5 w-3.5" />
          </button>
        </div>

        <div class="flex shrink-0 items-center">
          <button
            class="vt-segmented-tab vt-segmented-tab--compact"
            :class="{ 'vt-segmented-tab--active': filters.unannotated }"
            title="只看还没有人工标签的图"
            @click="filters.unannotated = !filters.unannotated"
          >
            未标注
          </button>
          <button
            class="vt-segmented-tab vt-segmented-tab--compact"
            :class="{ 'vt-segmented-tab--active': filters.has_auto_label }"
            title="只看有待确认候选框的图；不管谁在审查，这个开关只决定列表里留下哪些图"
            @click="togglePendingFilter"
          >
            待复核
          </button>
          <button
            v-if="isDetectBoxDataset"
            class="vt-segmented-tab vt-segmented-tab--compact"
            :class="{ 'vt-segmented-tab--active': filters.overlap_dup }"
            title="只看有同类重复框的图：两个同类框重叠七成以上，或一个九成以上落在另一个里。是不是真重复要人看，进标注页自己删。"
            @click="filters.overlap_dup = !filters.overlap_dup"
          >
            同类重复
          </button>
        </div>

        <div v-if="datasetInfo" class="flex min-w-0 flex-1 flex-wrap items-center gap-1.5">
          <span class="text-xs text-gray-400">{{ reviewMode ? '高亮' : '类别' }}</span>
          <span
            v-for="s in datasetInfo.class_stats || []"
            :key="s.id"
            class="vt-chip"
            :class="{ 'vt-chip--selected': selectedClassIds.includes(s.id) }"
            :title="reviewMode
              ? `只看这一类在缩略图上框的颜色（已标注的和候选都算）；不点就全画`
              : `${s.name}：${s.count} 个目标 · ${s.percentage}%`"
            @click="toggleClass(s.id)"
          >
            <span class="h-2 w-2 shrink-0 rounded-full" :style="{ background: getClassColor(s.id) }"></span>
            <span class="font-medium">{{ s.name }}</span>
          </span>
          <span v-if="!(datasetInfo.class_stats && datasetInfo.class_stats.length)" class="text-xs text-gray-400">
            暂无类别
          </span>
          <!-- 空类别表时先在这里给一个入口，不然只能去 ⋯ 菜单里翻 -->
          <button
            v-if="!(datasetInfo.class_stats && datasetInfo.class_stats.length) && canAddClass"
            class="vt-btn-link text-xs"
            @click="openClassManager"
          >
            类别管理
          </button>
          <button v-if="selectedClassIds.length > 0" class="vt-btn-link text-xs" @click="clearClasses">
            清空已选 {{ selectedClassIds.length }}
          </button>
        </div>

        <div class="ml-auto flex shrink-0 items-center gap-2">
          <!-- 探测在后台跑，弹窗关掉后进度不能消失：这里留一个能点回去的读数 -->
          <button
            v-if="probe.running"
            class="vt-tag vt-tag-info"
            title="同类探测还在跑，点开看进度"
            @click="probePanel.open = true"
          >
            同类探测 {{ probe.progress }}%
          </button>
          <!-- 审查是看这批图的方式，不是筛图的条件，所以不放筛选段控件，跟「显示设置」组成右边的图标组 -->
          <div class="flex shrink-0 items-center gap-1">
            <button
              v-if="isDetectBoxDataset"
              class="vt-icon-btn vt-icon-btn--sm"
              :class="{ 'vt-icon-btn--active': reviewMode }"
              :aria-label="reviewMode ? '退出审查' : '进入审查'"
              :title="reviewMode
                ? '退出审查：缩略图不再画框，类别点标回到「按类别筛图」。列表里有哪些图不变。'
                : '进入审查：把当前筛出来的这一批图整个拉进审查，缩略图上已标注框画描边、候选框画底色+虚线，类别点标改成点亮这一类的框。列表里有哪些图不变。'"
              @click="toggleReview"
            >
              <AppIcon name="review" class="h-4 w-4" />
            </button>
            <div ref="displayMenuRef" class="relative shrink-0">
              <button
                class="vt-icon-btn vt-icon-btn--sm"
                :class="{ 'vt-icon-btn--active': displayMenuDirty }"
                aria-label="显示设置"
                title="显示设置：一屏排几列、折叠相似帧、聚焦列表"
                @click="showDisplayMenu = !showDisplayMenu"
              >
                <AppIcon name="settings" class="h-4 w-4" />
              </button>
              <div
                v-if="showDisplayMenu"
                class="absolute right-0 top-full z-30 mt-1 w-52 border border-gray-200 bg-white py-1 shadow-sm"
              >
                <div class="px-3 pb-1 pt-0.5 text-[10px] text-gray-400">单张图占多宽</div>
                <button
                  v-for="opt in GRID_SHARE_OPTIONS"
                  :key="opt.key"
                  class="vt-menu-item flex items-center justify-between gap-2"
                  :class="{ 'font-semibold text-[var(--vt-color-primary)]': gridShareKey === opt.key }"
                  :title="opt.hint"
                  @click="chooseGridShare(opt.key)"
                >
                  {{ opt.label }}
                  <AppIcon v-if="gridShareKey === opt.key" name="check" class="h-3.5 w-3.5 shrink-0" />
                </button>
                <div class="my-1 border-t border-gray-100"></div>
                <button
                  v-if="isDetectBoxDataset"
                  class="vt-menu-item flex items-center justify-between gap-2"
                  :class="{ 'font-semibold text-[var(--vt-color-primary)]': filters.fold_dup }"
                  title="把差不多一样的连拍帧折成一格，组数变少、翻页变少；每张仍要各开弹窗各判各的"
                  @click="filters.fold_dup = !filters.fold_dup"
                >
                  折叠相似帧
                  <AppIcon v-if="filters.fold_dup" name="check" class="h-3.5 w-3.5 shrink-0" />
                </button>
                <button
                  class="vt-menu-item flex items-center justify-between gap-2"
                  :class="{ 'font-semibold text-[var(--vt-color-primary)]': store.listFocus }"
                  title="收起侧边栏和顶栏，把面积让给图片列表；按 Esc 退出"
                  @click="store.setListFocus(!store.listFocus)"
                >
                  聚焦列表
                  <AppIcon v-if="store.listFocus" name="check" class="h-3.5 w-3.5 shrink-0" />
                </button>
              </div>
            </div>
          </div>
          <template v-if="cursor.path">
            <UiTooltip side="bottom" content-class="max-w-[16rem]">
              <template #trigger>
                <button class="vt-icon-btn vt-icon-btn--sm" :disabled="loading" aria-label="定位" @click="locateAndJumpCursor">
                  <AppIcon name="target" class="h-4 w-4" />
                </button>
              </template>
              跳到上次那张所在页并滚动到位
            </UiTooltip>
          </template>
          <span
            class="font-mono text-xs text-gray-500"
            :title="foldActive ? '折叠中：组数是列表上的格子数，张数是它们背后真实的图数' : ''"
          >{{ foldSummary }}</span>
          <button class="vt-icon-btn vt-icon-btn--sm" :disabled="loading || currentPage <= 1" @click="goPrevPage">
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
          <button class="vt-icon-btn vt-icon-btn--sm" :disabled="loading || currentPage >= totalPages" @click="goNextPage">
            <AppIcon name="next" class="h-3.5 w-3.5" />
          </button>
        </div>
      </div>
    </div>

    <!-- Image Grid -->
    <div ref="gridScrollRef" class="flex-1 overflow-y-auto min-h-0 bg-gray-50 rounded-lg p-4 border border-gray-100" @scroll.passive="closeImageMenu">
        <div v-if="loading && images.length === 0" class="flex justify-center items-center h-full">
        <div class="h-12 w-12 animate-spin rounded-full border-2 border-[var(--vt-color-primary-border)] border-t-[var(--vt-color-primary)]"></div>
      </div>

      <div v-else-if="images.length === 0" class="flex flex-col items-center justify-center h-full text-gray-400">
        <AppIcon :name="isSearchMode ? 'search' : 'camera'" class="mb-2 h-9 w-9" />
        <p v-if="filters.overlap_dup">这个范围内没有同类重复框。</p>
        <p v-else>{{ isSearchMode ? '没有匹配的图片' : '暂无图片' }}</p>
      </div>

      <div v-else :class="imageGridClass" :style="imageGridStyle">
        <div
          v-for="img in visibleImages"
          :key="img.path"
          :data-path="img.path"
          class="group relative aspect-square overflow-hidden rounded-lg bg-gray-200 transition-all cursor-pointer hover:ring-2 hover:ring-[var(--vt-color-primary)]"
          :class="{ 'ring-2 ring-[var(--vt-color-primary)]': img.path === cursor?.path }"
          @click="onImageClick(img)"
          @contextmenu.prevent="openImageMenu(img, $event)"
        >
          <img
            :src="img.url"
            class="h-full w-full"
            :class="reviewMode ? 'object-contain' : 'object-cover'"
            loading="lazy"
            @load="onImageLoad(img, $event)"
          />
          <!-- 走查模式：这张图的整体按类别颜色画在缩略图上——描边是已标好的，底色+虚线是还没审的候选；
               批量看的是全图，只画候选等于让人拿半张图判断。点图进标注页判定。
               走查时图必须整个看见（裁掉一块就等于少看一个目标），所以是 object-contain，上下或左右留黑边；
               viewBox 用图片自己的宽高比配 meet 缩放，跟这块实际画面重合，框就不会偏。
               格子小，虚线在缩略图上根本数得清几段，所以候选另加一层底色：远看「哪块还没定」是看出来的，不是盯出来的。 -->
          <svg
            v-if="reviewMode && highlightBoxes(img).length"
            class="pointer-events-none absolute inset-0 h-full w-full"
            :viewBox="overlayViewBox(img)"
            preserveAspectRatio="xMidYMid meet"
          >
            <rect
              v-for="(b, i) in highlightBoxes(img)"
              :key="i"
              :x="b.x"
              :y="b.y"
              :width="b.w"
              :height="b.h"
              :fill="b.pending ? getClassColor(b.class) : 'none'"
              :fill-opacity="b.pending ? 0.3 : 0"
              :stroke="getClassColor(b.class)"
              :stroke-width="b.pending ? 2 : 1.5"
              :stroke-dasharray="b.pending ? '4 3' : '0'"
              stroke-opacity="0.95"
              vector-effect="non-scaling-stroke"
            />
          </svg>

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

          <span
            v-if="isSearchMode && img.split"
            class="absolute bottom-2 left-2 rounded bg-black/60 px-1.5 py-0.5 text-[10px] font-mono text-white"
            title="这张图所在的 split"
          >{{ img.split }}</span>

          <!-- 右下角这条竖排：同类重复的框数、折叠出来的组大小，叠着放免得互相盖住 -->
          <div class="absolute bottom-1.5 right-1.5 flex flex-col items-end gap-1">
            <span
              v-if="img.overlap_boxes"
              class="rounded bg-red-500/90 px-1.5 py-0.5 text-[10px] font-semibold text-white shadow-sm"
              :title="`${img.overlap_boxes} 个框跟同类的另一个框重叠七成以上，或九成以上落在它里面`"
            >{{ img.overlap_boxes }} 个重复</span>

            <!-- 折叠相似：一张代表顶上挂着这一组的张数，点开才摊出其余的；点图本身还是进这张图的标注弹窗 -->
            <button
              v-if="foldActive && groupSize(img) > 1"
              class="rounded px-1.5 py-0.5 text-[10px] font-semibold text-white shadow-sm"
              :class="expandedGroups.has(img.path) ? 'bg-[var(--vt-color-primary)]' : 'bg-black/60'"
              :title="expandedGroups.has(img.path)
                ? '收起这一组'
                : `这一组共 ${groupSize(img)} 张差不多一样的图，点开摊出其余 ${groupSize(img) - 1} 张；每张进各自弹窗各判各的`"
              @click.stop="toggleGroup(img.path)"
            >×{{ groupSize(img) }}</button>
          </div>

          <div v-if="selectionMode" class="absolute top-2 left-2">
            <div
              class="vt-selection-indicator h-5 w-5 rounded shadow-sm"
              :class="isSelected(img.path) ? 'vt-selection-indicator--selected' : ''"
            >
              ✓
            </div>
          </div>
          <span
            v-else-if="img.path === cursor?.path"
            class="absolute top-2 left-2 rounded bg-[var(--vt-color-primary)] px-1.5 py-0.5 text-[10px] font-semibold text-white shadow-sm"
          >上次</span>
        </div>
      </div>
    </div>
    
    <!-- 单张图片的右键菜单：移动与删除都只在点击后执行 -->
    <div
      v-if="imageMenu.open"
      ref="imageMenuRef"
      class="fixed z-40 w-44 border border-gray-200 bg-white py-1 shadow-lg"
      :style="{ left: `${imageMenu.x}px`, top: `${imageMenu.y}px` }"
    >
      <div class="truncate px-3 pb-1 pt-0.5 font-mono text-[10px] text-gray-400" :title="imageMenu.image?.name">
        {{ imageMenu.image?.name }}
      </div>
      <div class="mb-1 px-3 text-[10px] text-gray-400">
        移动到<span v-if="imageMenu.image?.split">（当前 {{ imageMenu.image.split }}）</span>
      </div>
      <button
        v-for="s in moveTargetSplits"
        :key="s"
        class="vt-menu-item"
        :disabled="isImageMutating"
        @click="moveImageTo(s)"
      >
        {{ s }}
      </button>
      <div class="my-1 border-t border-gray-100"></div>
      <button
        class="vt-menu-item vt-menu-item--danger"
        :disabled="isImageMutating"
        @click="deleteSingleImage"
      >
        删除
      </button>
    </div>

    <!-- Footer Actions：底栏左侧只讲圆点颜色，右侧是页面主行动。聚焦时这一条整块让给列表，退出聚焦就回来。 -->
    <div v-if="!store.listFocus" class="mt-4 pt-4 border-t border-gray-100 flex items-center justify-between gap-3">
      <div class="flex items-center gap-3 text-xs text-gray-500">
        <span class="flex items-center gap-1.5">
          <i class="vt-status-dot vt-status-dot--warn"></i>待复核
        </span>
        <span class="flex items-center gap-1.5">
          <i class="vt-status-dot vt-status-dot--success"></i>已标注
        </span>
        <span class="flex items-center gap-1.5">
          <i class="vt-status-dot bg-white ring-1 ring-gray-300 ring-inset"></i>未标注
        </span>
      </div>
       <button
         @click="goToTrain"
         :disabled="!trainGuard.enabled"
         :title="trainGuard.reason || ''"
         class="vt-btn-solid-primary vt-btn-size-lg"
       >
         <AppIcon name="train" class="h-4 w-4" />
         <span>{{ trainGuard.enabled ? '去训练' : '暂不可训练' }}</span>
         <AppIcon name="next" class="h-4 w-4" />
       </button>
    </div>
    
    <!-- Auto Annotate Progress Modal -->
    <ModalShell
      v-if="autoAnnotating"
      title="自动标注中..."
      size="md"
      body-class="p-5 text-center"
      :dismissible="false"
      close-title="标注进行中，跑完自动关闭"
    >
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
            <div class="text-gray-500 mb-1">待审候选</div>
            <div class="font-mono font-bold text-lg text-blue-600">{{ autoAnnotateStatus.added }}</div>
          </div>
          <div class="bg-gray-50 p-3 rounded-lg">
            <div class="text-gray-500 mb-1">待复核图片</div>
            <div class="font-mono font-bold text-lg text-orange-500">{{ autoAnnotateStatus.pending }}</div>
          </div>
        </div>
    </ModalShell>

    <!-- Auto Annotate Modal -->
    <ModalShell
      v-if="showAutoAnnotateModal"
      title="自动标注配置"
      size="md"
      body-class="p-5"
      :dismissible="!isActionPending(AUTO_ANNOTATE_ACTION_KEY)"
      @close="showAutoAnnotateModal = false"
    >
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
             <option v-if="trainedModelOptions.length === 0" disabled>没有未归档的训练产物，去任务中心恢复对应训练流程</option>
             <option v-for="opt in trainedModelOptions" :key="opt.key" :value="opt.value">{{ opt.label }}</option>
          </select>
        </div>

        <div v-if="isDetectBoxDataset" class="mb-4">
          <label class="vt-field-label">探测类别</label>
          <select v-model.number="autoProbeClassId" class="vt-select">
            <option :value="-1">全部类别</option>
            <option v-for="(name, idx) in classList" :key="idx" :value="idx">{{ name }}</option>
          </select>
          <p class="mt-1 text-xs leading-5 text-gray-500">
            {{ autoProbeClassId === -1 ? '在全部类别上找漏' : `只在 ${classList[autoProbeClassId] ?? '所选类别'} 这一类上找漏` }}；已经标好的同类框会跳过。
          </p>
        </div>
        
        <div class="mb-4">
          <label class="vt-field-label">置信度下限</label>
          <input v-model="autoConf" type="number" min="0" max="1" step="0.05" class="vt-input" placeholder="如 0.25" />
          <p class="mt-1 text-xs leading-5 text-gray-500">
            低于这个值的框不成为候选；跑完只进待复核，不写标签文件。
          </p>
          <p v-if="autoConfError" class="mt-2 text-xs text-red-500">{{ autoConfError }}</p>
        </div>

      <template #footer>
          <button @click="showAutoAnnotateModal = false" class="vt-btn-secondary vt-btn-size-md" :disabled="isActionPending(AUTO_ANNOTATE_ACTION_KEY)">取消</button>
          <AsyncButton
            @click="runAutoAnnotate"
            class="vt-btn-solid-primary vt-btn-size-md"
            :disabled="!selectedModelPath || autoAnnotating || !!autoConfError"
            :pending="isActionPending(AUTO_ANNOTATE_ACTION_KEY)"
            loading-text="启动中..."
          >
            开始标注
          </AsyncButton>
      </template>
    </ModalShell>

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
      @probe="openProbeModal"
    />
    <SimilarProbeModal
      v-if="probePanel.open && probePanel.sample"
      :sample="probePanel.sample"
      :dataset-name="store.selectedDataset?.name || ''"
      :split="filters.split"
      :probe="probe"
      @close="closeProbeModal"
      @start="runProbe"
      @review="goReviewPending"
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

    <ModalShell
      v-if="showCreateSubsetModal"
      title="生成独立数据集"
      size="md"
      body-class="p-5"
      :dismissible="!isActionPending(CREATE_SUBSET_ACTION_KEY)"
      @close="closeCreateSubset"
    >
        <div class="mb-4 text-sm text-gray-600">已选择 <span class="font-mono">{{ selectedCount }}</span> 张图片</div>
        <div class="mb-6">
          <label class="block text-sm font-medium text-gray-700 mb-2">新数据集名称</label>
          <input v-model.trim="subsetName" class="vt-input" :disabled="isActionPending(CREATE_SUBSET_ACTION_KEY)" placeholder="例如：datasets_04_subset" />
        </div>
      <template #footer>
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
      </template>
    </ModalShell>

    <ModalShell
      v-if="showAugmentSubsetModal"
      title="弱类补偿采样"
      size="xl"
      body-class="p-5"
      :dismissible="!isAugmentPending()"
      @close="closeAugmentSubsetModal"
    >
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
      <template #footer>
          <button
            class="vt-btn-secondary vt-btn-size-md"
            :disabled="isAugmentPending()"
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
      </template>
    </ModalShell>

    <ModalShell
      v-if="showMergeDatasetsModal"
      title="合并两个数据集"
      size="lg"
      body-class="p-5"
      @close="closeMergeDatasets"
    >
        <div class="mb-4 text-sm text-gray-600">仅支持类别完全一致的数据集合并；将合并 train/val/test 的 images 与 labels。</div>

        <div class="grid grid-cols-1 gap-4">
          <div class="text-sm text-gray-700">
            当前数据集：<span class="font-mono">{{ store.selectedDataset?.name }}</span>
          </div>

          <div>
            <label class="block text-sm font-medium text-gray-700 mb-2">选择另一个数据集</label>
            <select v-model="mergeOtherDataset" class="vt-select">
              <option v-for="n in otherDatasetNames" :key="n" :value="n">{{ n }}</option>
            </select>
          </div>

          <div>
            <label class="block text-sm font-medium text-gray-700 mb-2">新数据集名称</label>
            <input v-model.trim="mergeNewDatasetName" class="vt-input" placeholder="例如：datasets_merge_01" />
          </div>
        </div>

      <template #footer>
          <button class="vt-btn-secondary vt-btn-size-md" :disabled="mergingDatasets" @click="closeMergeDatasets">取消</button>
          <button class="vt-btn-solid-primary vt-btn-size-md" :disabled="mergingDatasets || !mergeOtherDataset || !mergeNewDatasetName" @click="runMergeDatasets">
            {{ mergingDatasets ? '合并中...' : '开始合并' }}
          </button>
      </template>
    </ModalShell>

    <!-- 类别管理：增删收在一处，列表页的类别 chip 只负责筛选 -->
    <ModalShell
      v-if="showClassManagerModal"
      title="类别管理"
      size="md"
      body-class="p-5"
      @close="showClassManagerModal = false"
    >
        <div v-if="canAddClass" class="mb-3 flex items-center gap-2">
          <input
            v-model="newClassName"
            type="text"
            class="vt-input flex-1"
            placeholder="新类别名，回车添加"
            :disabled="addingClass"
            @keydown.enter.prevent="commitAddClass"
          />
          <button
            class="vt-btn-secondary vt-btn-size-sm shrink-0"
            :disabled="addingClass || !String(newClassName || '').trim()"
            @click="commitAddClass"
          >
            添加
          </button>
        </div>
        <div v-if="canAddClass && otherDatasetNames.length" class="mb-3 flex items-center gap-2">
          <select v-model="classSourceName" class="vt-select flex-1" :disabled="copyingClasses">
            <option value="">从其他数据集复用类别</option>
            <option v-for="n in otherDatasetNames" :key="n" :value="n">{{ n }}</option>
          </select>
          <button
            class="vt-btn-secondary vt-btn-size-sm shrink-0"
            :disabled="copyingClasses || !classSourceName"
            @click="commitCopyClasses"
          >
            {{ copyingClasses ? '复用中...' : '复用' }}
          </button>
        </div>
        <div class="max-h-80 overflow-y-auto border border-gray-200">
          <div
            v-for="s in datasetInfo?.class_stats || []"
            :key="s.id"
            class="flex items-center justify-between gap-3 border-b border-gray-100 px-3 py-2 text-sm last:border-b-0"
          >
            <span class="truncate text-slate-800">{{ s.name }}</span>
            <span class="shrink-0 font-mono text-xs text-gray-400">{{ s.count }} · {{ s.percentage }}%</span>
            <button
              v-if="canDeleteClass"
              class="vt-icon-btn vt-icon-btn--sm vt-icon-btn--danger shrink-0"
              :disabled="deletingLabelId !== null"
              :aria-label="`删除类别 ${s.name}`"
              @click="onDeleteClassChip(s)"
            >
              <AppIcon name="delete" class="h-3.5 w-3.5" />
            </button>
          </div>
          <div v-if="!(datasetInfo?.class_stats || []).length" class="px-3 py-6 text-center text-xs text-gray-400">
            暂无类别
          </div>
        </div>
    </ModalShell>

    <ModalShell
      v-if="showReorderLabelsModal"
      title="调整类别顺序"
      size="lg"
      body-class="p-5"
      :dismissible="!reorderingLabels"
      @close="closeReorderLabels"
    >
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

      <template #footer>
          <button class="vt-btn-secondary vt-btn-size-md" :disabled="reorderingLabels" @click="closeReorderLabels">取消</button>
          <button class="vt-btn-solid-primary vt-btn-size-md" :disabled="reorderingLabels || reorderItems.length === 0" @click="applyReorderLabels">
            {{ reorderingLabels ? '处理中...' : '应用' }}
          </button>
      </template>
    </ModalShell>


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
import { useGridShare, GRID_SHARE_OPTIONS } from '../composables/useGridShare';
import {
  DATASET_ANNOTATION_MODE,
  DATASET_OPERATION,
} from '../utils/datasetCapabilities';
import { assertCapabilityGuard } from '../utils/capabilityGuards';
import { CATEGORY_NAME_PATTERN, validateCategoryName } from '../utils';
import { resolveTrainingDatasetGuard } from '../utils/trainingActionGuards';
import { getClassColor } from '../utils/classColors';
import ClassificationAnnotator from './ClassificationAnnotator.vue';
import ImageAnnotator from './ImageAnnotator.vue';
import PoseAnnotator from './PoseAnnotator.vue';
import SegmentAnnotator from './SegmentAnnotator.vue';
import SimilarProbeModal from './SimilarProbeModal.vue';
import UploadDatasetImagesModal from './UploadDatasetImagesModal.vue';
import AppIcon from './ui/AppIcon.vue';
import AsyncButton from './ui/AsyncButton.vue';
import ModalShell from './ui/ModalShell.vue';
import UiTooltip from './ui/Tooltip.vue';

const store = useMainStore();
const toast = useToast();
const apiCall = useApiCall();
const asyncAction = useAsyncAction();
const router = useRouter();
const { confirm: showConfirm } = useConfirm();
const { allDatasets } = useDatasets();
const images = ref([]);
const loading = ref(false);
const total = ref(0);
// 折叠开着时 total 数的是组，这里另存折叠前的张数，列表上两个数各说各的
const rawTotal = ref(0);
// 筛选里还有候选文件的张数：批量写入/清空只作用于这些图，为 0 时两个按钮都该歇着
const pendingTotal = ref(0);
const classList = ref([]);
const datasetInfo = ref(null);
const currentImage = ref(null);
const showAutoAnnotateModal = ref(false);
const autoAnnotateType = ref('pretrained');
// 界面里这一个值就是本轮实际用的置信度下限，不再在别处藏默认值
const autoConf = ref('0.25');
// -1 = 全部类别；选了某个类别就只在这一类上找漏标
const autoProbeClassId = ref(-1);
const selectedModelPath = ref('');
const selectionMode = ref(false);
const selectedClassIds = ref([]);
const selectedMap = ref({});
const selectingAll = ref(false);
const showCreateSubsetModal = ref(false);
const subsetName = ref('');
const deleting = ref(false);
const showReorderLabelsModal = ref(false);
const reorderItems = ref([]);
const reorderingLabels = ref(false);
const deletingLabelId = ref(null);
const showClassManagerModal = ref(false);
const newClassName = ref('');
const addingClass = ref(false);
const classSourceName = ref('');
const copyingClasses = ref(false);
const deduplicatingImages = ref(false);
// 待复核批量条：清空只删候选，写入要把跨分页名单收齐才敢报张数，所以名单收集单独有个态
const clearingPending = ref(false);
const committingPending = ref(false);
const collectingPendingNames = ref(false);
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
// 画幅=一屏排几列（显示设置里三档）；聚焦=把侧边栏和顶栏让给列表（走查态自动开）
const { shareKey: gridShareKey, columns: gridColumns, setShare: setGridShare } = useGridShare();
let activeImageRequestController = null;
const { gridClass: imageGridClass, gridStyle: imageGridStyle } = useAutoFillGrid(gridColumns, {
  gapPx: 12,
});
const SPLIT_OPTIONS = ['train', 'val', 'test'];
const showMoreMenu = ref(false);
const moreMenuRef = ref(null);
const showDisplayMenu = ref(false);
const displayMenuRef = ref(null);
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
// 预估 → 确认 → 生成 三步共一把锁：这期间弹窗不能被点遮罩/Esc/叉号关掉，
// 否则「生成中」和失败报错都没有落脚的地方，看起来就像点了没反应。
const augmentConfirming = ref(false);
const isAugmentPending = () =>
  isActionPending(AUGMENT_PREVIEW_ACTION_KEY)
  || isActionPending(AUGMENT_SUBMIT_ACTION_KEY)
  || augmentConfirming.value;
const onAdvanced = (fn) => {
  showMoreMenu.value = false;
  fn && fn();
};

const openCreatedDataset = async (datasetName) => {
  const nextName = String(datasetName || '').trim();
  const nextDataset = nextName
    ? (store.currentProject?.datasets || []).find((d) => d.name === nextName) || null
    : null;
  if (!nextDataset) return null;
  store.selectDataset(nextDataset);
  await router.push({
    name: 'dataset-detail',
    params: {
      project: encodeURIComponent(store.currentProject?.name || ''),
      name: encodeURIComponent(nextDataset.name),
    },
    query: {
      dataset_id: nextDataset.dataset_id,
    },
  });
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
  overlap_dup: false,
  fold_dup: false,
  keyword: '',
  offset: 0,
  limit: 60
});

// 有关键词就跨 train/val/test 一起找（此时 split tab 不适用），清空后回到单 split 浏览。
const isSearchMode = computed(() => !!String(filters.keyword || '').trim());
const activeSplitQuery = computed(() => (isSearchMode.value ? 'all' : filters.split));

// 占比只改每格多宽，图还是那批图，收掉菜单就行；折叠和聚焦会在菜单上留个记号，不用点开也看得出列表被改过。
const chooseGridShare = (key) => {
  setGridShare(key);
  showDisplayMenu.value = false;
};
const displayMenuDirty = computed(() => filters.fold_dup || store.listFocus);

// 审查态和「待复核」筛选是两件事：筛选决定列表里留下哪些图，审查决定这些图上画不画框、
// 批量条管不管这一批。所以审查是工具栏上一个独立开关，点它把当前筛出来的全量拉进来。
// 只有检测任务画得出框，分割/姿态/分类的标签行不是框，审查对它没有意义。
const reviewOn = ref(false);
const reviewMode = computed(() => reviewOn.value && isDetectBoxDataset.value);

// 批量条上的作用范围：数据集 + split 是两个动作共用的，类别只有「清空」按它删行，所以只在清空的确认里出现。
const pendingBatchScope = computed(() => {
  const splitText = isSearchMode.value ? 'train/val/test 全部' : filters.split;
  return `${store.selectedDataset?.name || '当前数据集'} · ${splitText}`;
});
const pendingClearScope = computed(() => {
  if (selectedClassIds.value.length === 0) return '全部类别';
  const stats = datasetInfo.value?.class_stats || [];
  const names = selectedClassIds.value.map((id) => stats.find((s) => s.id === id)?.name || `#${id}`);
  return names.join('、');
});
const pendingBatchBusy = computed(() => collectingPendingNames.value);

// 待复核这个开关只决定列表里留下哪些图；看不看框由右边那个审查图标决定，两件事不绑在一起。
const togglePendingFilter = async () => {
  filters.has_auto_label = !filters.has_auto_label;
  await applyFilters();
};

// 审查不改筛选：手上筛出来的是哪一批，就审哪一批。
const toggleReview = async () => {
  reviewOn.value = !reviewOn.value;
  await applyFilters();
};

// 走查时图必须整个看见（裁掉一块就等于少看一个目标），所以缩略图用 object-contain，多出来的一方留黑边；
// 记下宽高比是为了把框对回图上那块实际画面。
const imageAspect = reactive({});
const onImageLoad = (img, event) => {
  const ratio = Number(event?.target?.naturalWidth) / Number(event?.target?.naturalHeight);
  imageAspect[img.path] = Number.isFinite(ratio) && ratio > 0 ? ratio : 1;
};

// viewBox 用图片自己的宽高比配 meet 缩放，正好盖住 contain 后那块实际画面：
// 横竖在 viewBox 里是同一个刻度，而宽图的 1 单位宽 = 1/r 单位高，所以框的横向坐标要乘上宽高比。
const overlayViewBox = (img) => `0 0 ${imageAspect[img.path] || 1} 1`;

// 走查时批看的是这张图的整体：已经标好的框和还没审的候选都得在缩略图上，
// 只画候选等于让人对着半张图判断。两类共用类别颜色：只有描边=已标注，底色+虚线=候选——
// 格子小的时候没人数不清虚线有几段，区分得靠底色看出来，不是盯出来。
const highlightBoxes = (img) => {
  const aspect = imageAspect[img.path] || 1;
  const only = selectedClassIds.value;
  const merged = [
    ...(img.label_boxes || []).map((b) => ({ ...b, pending: false })),
    ...(img.pending_boxes || []).map((b) => ({ ...b, pending: true })),
  ];
  return merged
    .filter((b) => only.length === 0 || only.includes(b.class))
    .map((b) => ({
      x: b.x1 * aspect,
      y: b.y1,
      w: Math.max(0, b.x2 - b.x1) * aspect,
      h: Math.max(0, b.y2 - b.y1),
      class: b.class,
      pending: b.pending,
    }));
};

// 折叠相似帧：连拍镜头在列表里一张挨一张，看两张就认得出来了，跟看不看候选框无关，
// 所以任何筛选状态下都能折。只折显示——组员各开各的标注弹窗，判定不跨帧复制。
const foldActive = computed(() => filters.fold_dup);
const expandedGroups = ref(new Set());
const toggleGroup = (path) => {
  const next = new Set(expandedGroups.value);
  if (next.has(path)) next.delete(path);
  else next.add(path);
  expandedGroups.value = next;
};
const visibleImages = computed(() => {
  if (!foldActive.value) return images.value;
  const out = [];
  for (const item of images.value) {
    out.push(item);
    if (expandedGroups.value.has(item.path)) out.push(...(item.dup_members || []));
  }
  return out;
});
// 列表上「×N 相似」那个角标：N 是这一组里的张数，包含代表自己
const groupSize = (img) => Number(img?.dup_group_size || 1);
const foldSummary = computed(() => {
  if (!foldActive.value || !rawTotal.value) return `${total.value} 张`;
  return `${total.value} 组 / ${rawTotal.value} 张`;
});

// 「当前筛选条件」的唯一出处：列表、定位、批量标注都从这里取，避免各处各写一份。
// 框几何只给缩略图用，批量取全量名单时不要它，否则一页 500 张白读 1000 个文件。
// fold 同理：批量名单要的是每一张图，折叠后只剩代表，会漏掉被折走的那些。
const listQuery = ({ reviewBoxes = true, fold = true } = {}) => ({
  project_path: store.currentProject?.path,
  dataset_name: store.selectedDataset?.name,
  split: activeSplitQuery.value,
  keyword: isSearchMode.value ? String(filters.keyword).trim() : undefined,
  classes: selectedClassIds.value.length > 0 && !reviewMode.value ? selectedClassIds.value.join(',') : undefined,
  mode: filters.mode,
  unannotated: filters.unannotated,
  has_auto_label: filters.has_auto_label,
  overlap_dup: filters.overlap_dup || undefined,
  review_boxes: (reviewMode.value && reviewBoxes) || undefined,
  fold_dup: (foldActive.value && fold) || undefined,
});

// 「上次打开的图片」游标：后端按 数据集::split 存储（.dataset-store 下，非 DVC 内容），
// 进入数据集或切 split 时自动跳到上次那张所在页并滚动到位；打开标注器/上下张切换即更新。
const gridScrollRef = ref(null);
const cursor = ref({ path: '' });
const cursorProjectPath = computed(() => store.currentProject?.path || '');
const cursorDatasetName = computed(() => store.selectedDataset?.name || '');
const readCursor = async () => {
  if (!cursorProjectPath.value || !cursorDatasetName.value) {
    cursor.value = { path: '' };
    return;
  }
  try {
    const res = await api.getDatasetCursor({
      project_path: cursorProjectPath.value,
      dataset_name: cursorDatasetName.value,
      split: filters.split,
    });
    cursor.value = { path: res?.path || '' };
  } catch (e) {
    cursor.value = { path: '' };
  }
};
const scrollToPath = (path) => {
  if (!path || !gridScrollRef.value) return;
  const tiles = gridScrollRef.value.querySelectorAll('[data-path]');
  for (const t of tiles) {
    if (t.getAttribute('data-path') === path) {
      t.scrollIntoView({ block: 'center' });
      break;
    }
  }
};
// 定位到上次那张：在当页就直接滚动，否则用 image_index 求所在页再翻过去
const locateAndJumpCursor = async () => {
  if (!cursorProjectPath.value || !cursorDatasetName.value) return;
  await readCursor();
  const target = cursor.value.path;
  if (!target) return;
  if (visibleImages.value.some((i) => i.path === target)) {
    await nextTick();
    scrollToPath(target);
    return;
  }
  try {
    const info = await api.locateDatasetImage({
      ...listQuery(),
      image_path: target,
    });
    if (info && info.index >= 0) {
      const targetPage = Math.floor(info.index / filters.limit) + 1;
      if (targetPage !== currentPage.value) {
        pageInput.value = targetPage;
        filters.offset = (targetPage - 1) * filters.limit;
        await fetchImages(false);
      }
      await nextTick();
      scrollToPath(target);
    }
  } catch (e) { /* 定位失败只失去跳转，不影响浏览 */ }
};

// 打开或翻到某张即写游标（关闭时 currentImage 变 null，跳过，不清除）
watch(currentImage, (img) => {
  if (!img || !cursorProjectPath.value || !cursorDatasetName.value) return;
  cursor.value = { path: img.path };
  api.setDatasetCursor({
    project_path: cursorProjectPath.value,
    dataset_name: cursorDatasetName.value,
    // 搜索结果里可能是别的 split 的图，游标要落在这张图自己的 split 上
    split: img.split || filters.split,
    image_path: img.path,
    image_name: img.name,
  }).catch(() => { /* 写失败静默，仅失去记忆 */ });
});

const openAnnotator = (img) => {
  if (!assertCapabilityGuard(manualAnnotationGuard.value, toast.warn)) return;
  currentImage.value = img;
};

const selectedCount = computed(() => Object.keys(selectedMap.value).length);
// 能力判定只看 store 里的数据集摘要（版本状态轮询会持续刷新它）；
// datasetInfo 只负责图片数、类别分布这些本页面的实时统计。
const { annotationMode, hasDatasetOperation, getDatasetOperationGuard } = useDatasetCapabilities(computed(() => store.selectedDataset));
const uploadImagesGuard = computed(() => getDatasetOperationGuard(DATASET_OPERATION.UPLOAD_IMAGES));
const manualAnnotationGuard = computed(() => getDatasetOperationGuard(DATASET_OPERATION.MANUAL_ANNOTATION));
const trainGuard = computed(() => resolveTrainingDatasetGuard(store.selectedDataset));
const createSubsetGuard = computed(() => getDatasetOperationGuard(DATASET_OPERATION.CREATE_SUBSET));
const autoAnnotateGuard = computed(() => getDatasetOperationGuard(DATASET_OPERATION.AUTO_ANNOTATE, {
  visibleWhenUnsupported: true,
}));
const autoConfError = computed(() => {
  const value = Number(autoConf.value);
  if (autoConf.value === '' || !Number.isFinite(value)) return '置信度下限要填一个数';
  if (value < 0 || value > 1) return '置信度下限在 0 到 1 之间';
  return '';
});
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
const isDetectBoxDataset = computed(() => annotationMode.value === DATASET_ANNOTATION_MODE.DETECT_BOXES);
const hasDatasetOperations = computed(() => hasDatasetOperation(DATASET_OPERATION.DEDUPLICATE_IMAGES) || hasDatasetOperation(DATASET_OPERATION.MERGE_DATASETS));
const canAddClass = computed(() => hasDatasetOperation(DATASET_OPERATION.ADD_LABEL));
const canDeleteClass = computed(() => hasDatasetOperation(DATASET_OPERATION.DELETE_LABEL));
const annotatedPercent = computed(() => `${Math.round(Number(datasetInfo.value?.annotation_rate || 0) * 1000) / 10}%`);
const totalPages = computed(() => Math.max(1, Math.ceil((total.value || 0) / (filters.limit || 1))));
const currentPage = computed(() => Math.min(totalPages.value, Math.floor((filters.offset || 0) / (filters.limit || 1)) + 1));
// 同项目里的其他数据集：合并、复用类别都用它，一处定义
const otherDatasetNames = computed(() => {
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
      const weight = String(model?.name || '').endsWith('last.pt') ? 'last.pt' : 'best.pt';
      const map50 = model?.metrics?.map50;
      const score = map50 === null || map50 === undefined ? '' : ` · 末轮 mAP50 ${Number(map50).toFixed(3)}`;
      return {
        key: `${runId}:${model.path}`,
        value: model.path,
        label: `[${dataset}] ${runId} · ${weight}${score}`,
      };
    });
});

const ensureAutoAnnotateModelsLoaded = async (type) => {
  await store.fetchModels(store.selectedDataset?.vision_task_type, 'auto_annotate');
  if (type === 'pretrained' && pretrainedModelOptions.value.length > 0) {
    selectedModelPath.value = pretrainedModelOptions.value[0].path;
    return;
  }
  if (type === 'trained' && trainedModelOptions.value.length > 0) {
    selectedModelPath.value = trainedModelOptions.value[0].value;
    return;
  }
  selectedModelPath.value = '';
};

watch(() => showAutoAnnotateModal.value, (val) => {
  if (val) {
    ensureAutoAnnotateModelsLoaded(autoAnnotateType.value).catch(() => {});
  }
});

// 切换模型来源要重新落定选中项：否则下拉框显示的是训练权重，实际发出去的还是上一个路径
watch(autoAnnotateType, (type) => {
  ensureAutoAnnotateModelsLoaded(type).catch(() => {});
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
  // 「本页」= 屏面上看得见的格子：折叠起来的组员没展开就不算被选中
  visibleImages.value.forEach(img => {
    // 值存这张图所在的 split：搜索是跨 split 的，删除时要按 split 分组下发
    next[img.path] = img.split || filters.split;
  });
  selectedMap.value = next;
};

const clearSelection = () => {
  selectedMap.value = {};
};

const selectAllFiltered = async () => {
  if (selectingAll.value) return;
  selectingAll.value = true;
  try {
    const items = await listFilteredItems();
    if (items.length === 0) {
      toast.warn('当前筛选条件下没有图片');
      return;
    }
    const next = { ...selectedMap.value };
    items.forEach(item => {
      next[item.path] = item.split;
    });
    selectedMap.value = next;
    toast.success(`已选中当前筛选结果 ${items.length} 张`);
  } catch (err) {
    toast.error(err?.message || '收集筛选结果失败');
  } finally {
    selectingAll.value = false;
  }
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
    selectedMap.value = { ...selectedMap.value, [img.path]: img.split || filters.split };
  }
};

const navImage = (dir) => {
  if (!currentImage.value) return;
  // 用屏面上这份顺序：折叠展开后的组员也在序列里，判完一组可以连着往下走
  const idx = visibleImages.value.findIndex(i => i.path === currentImage.value.path);
  if (idx === -1) return;

  const newIdx = idx + dir;
  if (newIdx >= 0 && newIdx < visibleImages.value.length) {
    currentImage.value = visibleImages.value[newIdx];
  } else if (newIdx >= visibleImages.value.length) {
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
  // 保存只回传「这张图审过了」这几个开关，框的几何不在里面；缩略图上画的是磁盘上的
  // 标签文件和候选文件，所以审完一张必须按当前页重读一次，不然框还是保存前的那套。
  if (filters.unannotated || filters.has_auto_label || reviewMode.value) {
    fetchImages(false);
  }
};

// 找同类：样本框来自标注弹窗，进度和结果归这里管——关掉弹窗任务照样跑完，工具条上有读数
const probePanel = reactive({ open: false, sample: null });
const probe = reactive({ running: false, done: false, thresh: 0.45, progress: 0, message: '', added: 0, pending: 0, error: '' });
let probeTimer = null;

const stopProbePolling = () => {
  if (probeTimer) {
    clearInterval(probeTimer);
    probeTimer = null;
  }
};

// 上一轮的读数不能跟着下一轮：进度、命中数、错误全部收干净
const resetProbe = () => {
  stopProbePolling();
  Object.assign(probe, { running: false, done: false, progress: 0, message: '', added: 0, pending: 0, error: '' });
  probePanel.sample = null;
  probePanel.open = false;
};

const openProbeModal = (sample) => {
  // 扫的是整个 split，不是这一张图，所以把标注弹窗让出来
  currentImage.value = null;
  resetProbe();
  probePanel.sample = sample;
  probePanel.open = true;
};

const closeProbeModal = () => {
  probePanel.open = false;
};

const pollProbe = (taskId) => {
  stopProbePolling();
  probeTimer = setInterval(async () => {
    let status = null;
    try {
      status = await api.getSimilarProbeStatus({ task_id: taskId });
    } catch (e) {
      stopProbePolling();
      probe.running = false;
      probe.error = e.message || '探测状态查询失败';
      return;
    }
    if (!status) return;
    probe.progress = status.progress || 0;
    probe.message = status.message || '';
    if (status.is_running) return;
    stopProbePolling();
    probe.running = false;
    probe.added = status.added || 0;
    probe.pending = status.pending || 0;
    probe.done = true;
    if (status.error) probe.error = status.error;
    // 命中落在别的图上，这一页的「待复核」角标和候选框得跟着重取
    else await fetchImages(false);
  }, 1000);
};

const runProbe = async (thresh) => {
  if (probe.running || !probePanel.sample) return;
  probe.thresh = thresh;
  probe.error = '';
  probe.done = false;
  probe.running = true;
  probe.progress = 0;
  probe.message = '启动中...';
  try {
    const res = await api.startSimilarProbe({
      project_path: store.currentProject.path,
      dataset_name: store.selectedDataset.name,
      split: filters.split,
      ...probePanel.sample,
      score_thresh: thresh,
    });
    pollProbe(res.task_id);
  } catch (e) {
    probe.running = false;
    probe.error = e.message || '启动探测失败';
  }
};

// 候选已经落盘，去复核就是把它筛出来；筛「待复核」本来就带进审查，这里不再重复一次
const goReviewPending = async () => {
  probePanel.open = false;
  if (!filters.has_auto_label) await togglePendingFilter();
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
    const res = await api.getDatasetImages(
      { ...listQuery(), offset: filters.offset, limit: filters.limit },
      { signal: controller.signal }
    );
    images.value = res.items;
    total.value = res.total;
    rawTotal.value = Number(res.raw_total || 0);
    pendingTotal.value = Number(res.pending_total || 0);
    expandedGroups.value = new Set();
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

const listFilteredItems = async () => {
  const pageSize = 500;
  let offset = 0;
  const byPath = new Map();

  while (true) {
    const res = await api.getDatasetImages({ ...listQuery({ reviewBoxes: false, fold: false }), offset, limit: pageSize });
    const pageItems = Array.isArray(res.items) ? res.items : [];
    pageItems.forEach(it => {
      if (it?.path) {
        byPath.set(it.path, { path: it.path, split: it.split || filters.split, has_auto_label: !!it.has_auto_label });
      }
    });
    const totalCount = Number(res.total || 0);
    offset += pageItems.length;
    if (pageItems.length === 0 || offset >= totalCount) {
      break;
    }
  }

  return Array.from(byPath.values());
};

// 批量写入和清空都只碰「筛选里还有候选的图」：名单在这里收口，按钮上的张数跟它同源
const listPendingNames = async () => {
  const items = await listFilteredItems();
  return items.filter(it => it.has_auto_label).map(({ path, split }) => ({ path, split }));
};

const applyFilters = () => {
  selectedMap.value = {};
  filters.offset = 0;
  pageInput.value = 1;
  return fetchImages(true);
};

// ===== 模糊搜索：停下打字 300ms 才发一次请求 =====
const SEARCH_DEBOUNCE_MS = 300;
let searchDebounceTimer = null;

const cancelKeywordSearch = () => {
  if (searchDebounceTimer) {
    clearTimeout(searchDebounceTimer);
    searchDebounceTimer = null;
  }
};

const scheduleKeywordSearch = () => {
  cancelKeywordSearch();
  searchDebounceTimer = setTimeout(() => {
    searchDebounceTimer = null;
    applyFilters();
  }, SEARCH_DEBOUNCE_MS);
};

const onKeywordInput = (value) => {
  filters.keyword = String(value || '');
  scheduleKeywordSearch();
};

const clearKeyword = () => {
  if (!filters.keyword) return;
  filters.keyword = '';
  scheduleKeywordSearch();
};

// ===== 右键单张图片：移动到其他 split / 删除 =====
const MOVE_IMAGE_ACTION_KEY = 'dataset-preview:move-image';
const DELETE_IMAGE_ACTION_KEY = 'dataset-preview:delete-image';
const imageMenu = ref({ open: false, x: 0, y: 0, image: null });
const imageMenuRef = ref(null);
const isImageMutating = computed(
  () => isActionPending(MOVE_IMAGE_ACTION_KEY) || isActionPending(DELETE_IMAGE_ACTION_KEY)
);
// 搜索结果里的图可能来自别的 split，动手时要以这张图自己的 split 为准
const splitOfImage = (img) => img?.split || filters.split;
const moveTargetSplits = computed(() => {
  const source = splitOfImage(imageMenu.value.image);
  return SPLIT_OPTIONS.filter((s) => s !== source);
});

const openImageMenu = async (img, e) => {
  if (selectionMode.value) return;
  imageMenu.value = { open: true, x: e.clientX, y: e.clientY, image: img };
  await nextTick();
  const el = imageMenuRef.value;
  if (!el) return;
  imageMenu.value.x = Math.max(8, Math.min(e.clientX, window.innerWidth - el.offsetWidth - 8));
  imageMenu.value.y = Math.max(8, Math.min(e.clientY, window.innerHeight - el.offsetHeight - 8));
};

const closeImageMenu = () => {
  if (imageMenu.value.open) imageMenu.value = { open: false, x: 0, y: 0, image: null };
};

const unselectImage = (path) => {
  if (!selectedMap.value[path]) return;
  const next = { ...selectedMap.value };
  delete next[path];
  selectedMap.value = next;
};

const moveImageTo = async (targetSplit) => {
  const img = imageMenu.value.image;
  closeImageMenu();
  if (!img) return;
  const sourceSplit = splitOfImage(img);
  if (!await showConfirm({
    title: '移动图片',
    message: `把 ${img.name} 从 ${sourceSplit} 移到 ${targetSplit}？`,
    detail: `${store.selectedDataset?.name} · 图片连同它的人工标签、待复核的自动标注一起移动`,
    confirmText: '移动',
  })) return;
  await asyncAction.run(MOVE_IMAGE_ACTION_KEY, async () => {
    await apiCall(api.moveDatasetImage({
      project_path: store.currentProject.path,
      dataset_name: store.selectedDataset.name,
      split: sourceSplit,
      target_split: targetSplit,
      image_path: img.path,
    }), {
      errorMsg: '移动失败',
      onSuccess: async () => {
        unselectImage(img.path);
        await refreshAfterImageMutation();
        toast.success(`已移动到 ${targetSplit}`);
      },
    });
  });
};

const deleteSingleImage = async () => {
  const img = imageMenu.value.image;
  closeImageMenu();
  if (!img) return;
  const sourceSplit = splitOfImage(img);
  if (!await showConfirm({
    title: '删除图片',
    message: `删除 ${img.name}？`,
    detail: `${store.selectedDataset?.name} · ${sourceSplit} · 图片和它的标签文件一起删除，不可恢复`,
    danger: true,
    confirmText: '删除',
  })) return;
  await asyncAction.run(DELETE_IMAGE_ACTION_KEY, async () => {
    await apiCall(api.deleteDatasetImage({
      project_path: store.currentProject.path,
      dataset_name: store.selectedDataset.name,
      split: sourceSplit,
      image_path: img.path,
    }), {
      errorMsg: '删除失败',
      onSuccess: async (data) => {
        unselectImage(img.path);
        await refreshAfterImageMutation();
        if (data?.deleted?.image) toast.success('已删除');
        else toast.warn('磁盘上没有找到这张图片，列表已重新读取');
      },
    });
  });
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
    await store.fetchProjects({ silent: true });
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
  if (!assertCapabilityGuard(trainGuard.value, toast.warn)) return;
  router.push({
    name: 'dataset-train',
    params: {
      project: encodeURIComponent(store.currentProject?.name || ''),
      name: encodeURIComponent(store.selectedDataset.name),
    },
    query: {
      dataset_id: store.selectedDataset.dataset_id,
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
  augmentConfirming.value = true;
  let confirmed = false;
  try {
    confirmed = await showConfirm({
      message: `源数据集：${store.selectedDataset.name}\n新建数据集：${augmentConfig.newDatasetName}\n目标类设置:\n${targetClassText}\n非目标图片保留比例: ${nonTargetKeepRatio}\n评估集策略: ${evalMode}`,
      title: '生成增强子集',
      confirmText: '生成',
    });
  } finally {
    augmentConfirming.value = false;
  }
  if (!confirmed) return;

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

const openClassManager = () => {
  showClassManagerModal.value = true;
  newClassName.value = '';
  classSourceName.value = '';
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
};

// 复用另一个数据集的类别表：先读源类别与本地比对，确认后一次写入
const commitCopyClasses = async () => {
  const source = String(classSourceName.value || '').trim();
  if (!source || copyingClasses.value) return;
  if (!store.currentProject?.path || !store.selectedDataset?.name) return;

  copyingClasses.value = true;
  const sourceInfo = await apiCall(api.getDatasetInfo({
    project_path: store.currentProject.path,
    dataset_name: source,
  }), { errorMsg: `读取数据集「${source}」失败` });
  copyingClasses.value = false;
  if (!sourceInfo) return;

  const sourceNames = normalizeNames(sourceInfo?.names);
  if (!sourceNames.length) {
    toast.warn(`数据集「${source}」还没有类别`);
    return;
  }
  // 与后端同一条规则：不合规的名字跳过并说清楚，不让整批复用卡死
  const invalidNames = sourceNames.filter(n => !CATEGORY_NAME_PATTERN.test(n));
  const legalNames = sourceNames.filter(n => CATEGORY_NAME_PATTERN.test(n));
  const existing = new Set(normalizeNames(classList.value));
  const toAdd = legalNames.filter(n => !existing.has(n));
  const skipped = legalNames.filter(n => existing.has(n));
  if (!toAdd.length) {
    toast.warn(
      invalidNames.length
        ? `「${source}」能复用的类别当前数据集都已经有了`
        : `「${source}」的类别当前数据集都已经有了`
    );
    return;
  }

  const detail = [
    `来源：${source}`,
    `目标：${store.selectedDataset.name}`,
    `新增 ${toAdd.length} 个：${briefClassNames(toAdd)}`,
  ];
  if (skipped.length) detail.push(`已有同名，跳过 ${skipped.length} 个：${briefClassNames(skipped)}`);
  if (invalidNames.length) {
    detail.push(`类别名不合规则，跳过 ${invalidNames.length} 个（只能包含字母 / 数字 / _ / -）：${briefClassNames(invalidNames)}`);
  }
  detail.push('已有类别不变，新增的接在后面。');
  if (!await showConfirm({
    title: '复用类别',
    message: detail.join('\n'),
    confirmText: '复用',
  })) return;

  copyingClasses.value = true;
  await apiCall(api.copyDatasetLabels({
    project_path: store.currentProject.path,
    dataset_name: store.selectedDataset.name,
    source_dataset_name: source,
  }), {
    errorMsg: '复用类别失败',
    onSuccess: async (data) => {
      classSourceName.value = '';
      await fetchDatasetInfo();
      const added = data?.added_labels?.length || 0;
      const invalid = data?.invalid_labels?.length || 0;
      toast.success(invalid ? `已复用 ${added} 个类别，${invalid} 个名称不合规则已跳过` : `已复用 ${added} 个类别`);
    },
    finally: () => { copyingClasses.value = false; },
  });
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

const markCurrentImageReviewed = () => {
  if (!currentImage.value) return;
  currentImage.value = { ...currentImage.value, pending: false, has_auto_label: false };
};

const clearPendingCandidates = async () => {
  if (!store.currentProject?.path || !store.selectedDataset?.name || clearingPending.value) return;
  collectingPendingNames.value = true;
  let items = [];
  try {
    items = await listPendingNames();
  } finally {
    collectingPendingNames.value = false;
  }
  if (items.length === 0) {
    toast.warn('当前筛选里没有待复核候选');
    return;
  }
  if (!await showConfirm({
    message: `将删掉当前筛选里 ${items.length} 张图上的候选框：${pendingBatchScope.value} · ${pendingClearScope.value}。\n`
      + '人工标签不动；再跑一轮自动标注会重新生成。',
    title: '清空这批候选',
    danger: true,
    confirmText: `清空 ${items.length} 张`,
  })) return;
  clearingPending.value = true;
  await apiCall(api.clearPendingAnnotations({
    project_path: store.currentProject.path,
    dataset_name: store.selectedDataset.name,
    images: items,
    classes: selectedClassIds.value.length ? selectedClassIds.value : null,
  }), {
    errorMsg: '清空失败',
    onSuccess: async (data) => {
      markCurrentImageReviewed();
      await fetchDatasetInfo();
      applyFilters();
      const kept = Number(data.kept_items || 0);
      toast.success(`已清掉 ${data.cleared_images || 0} 张图上的 ${data.dropped_items || 0} 个候选框`
        + (kept ? `，别的类别还留着 ${kept} 个` : '')
        + '；人工标签未改动');
    },
    finally: () => { clearingPending.value = false; },
  });
};

const commitPendingCandidates = async () => {
  if (!store.currentProject?.path || !store.selectedDataset?.name || committingPending.value) return;
  collectingPendingNames.value = true;
  let items = [];
  try {
    items = await listPendingNames();
  } finally {
    collectingPendingNames.value = false;
  }
  if (items.length === 0) {
    toast.warn('当前筛选里没有待复核候选');
    return;
  }
  if (!await showConfirm({
    message: `将把当前筛选里 ${items.length} 张图上的候选写进人工标签：${pendingBatchScope.value}。\n`
      + '已有标签不动，候选接在后面；写完这些图就不再是待复核。',
    title: '批量写入',
    confirmText: `写入 ${items.length} 张`,
  })) return;
  committingPending.value = true;
  await apiCall(api.commitPendingAnnotations({
    project_path: store.currentProject.path,
    dataset_name: store.selectedDataset.name,
    images: items,
  }), {
    errorMsg: '批量写入失败',
    onSuccess: async (data) => {
      markCurrentImageReviewed();
      await fetchDatasetInfo();
      applyFilters();
      const skipped = Number(data.skipped_images || 0);
      toast.success(`已写入 ${data.committed_images || 0} 张、${data.written_items || 0} 个框`
        + (skipped ? `；另有 ${skipped} 张名单里没有候选，已跳过` : ''));
    },
    finally: () => { committingPending.value = false; },
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

// 确认框里的类别清单只列前 12 个：几十个名字堆在弹窗里没人会看完
const briefClassNames = (names, max = 12) => (
  names.length > max ? `${names.slice(0, max).join('、')}…` : names.join('、')
);

const openMergeDatasets = () => {
  if (!mergeDatasetsGuard.value.enabled) return;
  const cand = otherDatasetNames.value;
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

// 移动或删除改的是磁盘上的文件：列表和页头计数都要重算，
// 当前页被删空时退回上一页，别停在一张空白页上。
const refreshAfterImageMutation = async () => {
  await fetchImages(false);
  if (images.value.length === 0 && (filters.offset || 0) > 0) {
    filters.offset = Math.max(0, (filters.offset || 0) - (filters.limit || 0));
    pageInput.value = Math.floor((filters.offset || 0) / (filters.limit || 1)) + 1;
    await fetchImages(false);
  }
  fetchDatasetInfo();
};

const batchDelete = async () => {
  if (deleting.value) return;
  const entries = Object.entries(selectedMap.value);
  if (entries.length === 0) return;
  // 搜索结果里的图可能分属不同 split，删除要按各自所在 split 分组下发
  const bySplit = {};
  entries.forEach(([path, split]) => {
    const key = split || filters.split;
    (bySplit[key] = bySplit[key] || []).push(path);
  });
  const groups = Object.entries(bySplit);
  if (!await showConfirm({
    message: `确定要删除选中的 ${entries.length} 张图片及其标注文件吗？`,
    detail: `${store.selectedDataset?.name} · ${groups.map(([split, paths]) => `${split} ${paths.length} 张`).join('、')}`,
    title: '删除图片',
    danger: true,
    confirmText: '删除',
  })) return;
  deleting.value = true;
  try {
    const results = await Promise.all(groups.map(([split, image_paths]) => api.batchDeleteDatasetImages({
      project_path: store.currentProject.path,
      dataset_name: store.selectedDataset.name,
      split,
      image_paths,
    })));
    const failed = results.flatMap(r => (r?.results || []).filter(item => !item.success));
    const deletedCount = results.reduce((sum, r) => sum + Number(r?.deleted_count || 0), 0);
    selectedMap.value = {};
    await refreshAfterImageMutation();
    if (failed.length) toast.warn(`已删除 ${deletedCount} 张，${failed.length} 张失败：${failed[0].error}`);
    else toast.success(`成功删除 ${deletedCount} 张图片`);
  } catch (e) {
    toast.error(e?.message || '删除失败');
  } finally {
    deleting.value = false;
  }
};

const runAutoAnnotate = async () => {
  if (autoAnnotating.value) return;
  if (!assertCapabilityGuard(autoAnnotateGuard.value, toast.warn)) return;
  await asyncAction.run(AUTO_ANNOTATE_ACTION_KEY, async () => {
    const imagePaths = (await listFilteredItems()).map(item => item.path);
    if (imagePaths.length === 0) {
      toast.warn('当前筛选条件下没有可标注图片');
      return;
    }
    const probeClassId = Number(autoProbeClassId.value);
    const classes = probeClassId >= 0 ? [probeClassId] : undefined;
    showAutoAnnotateModal.value = false;
    await apiCall(api.autoAnnotate({
      project_path: store.currentProject.path,
      dataset_name: store.selectedDataset.name,
      split: filters.split,
      image_paths: imagePaths,
      model_path: selectedModelPath.value,
      conf: Number(autoConf.value),
      classes,
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
            if (s.failed_images) {
              toast.error(`自动标注有 ${s.failed_images} 张写入失败：${(s.errors || []).join('；')}`);
            } else {
              toast.success(`自动标注完成！候选 ${s.added || 0} 条，${s.pending || 0} 张图待复核`);
            }
            fetchDatasetInfo();
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

watch(() => store.selectedDataset?.dataset_id || '', async () => {
  if (store.selectedDataset?.dataset_id) {
    selectionMode.value = false;
    selectedMap.value = {};
    selectedClassIds.value = [];
    reviewOn.value = false;
    filters.has_auto_label = false;
    cursor.value = { path: '' };
    // 探测属于上一个数据集：读数收掉，服务端那一轮还会把候选落到它自己的图上
    resetProbe();
    // 关键词属于上一个数据集：直接清掉，别把它的 300ms 延后请求带过来
    cancelKeywordSearch();
    filters.keyword = '';
    closeImageMenu();
    fetchDatasetInfo();
    await fetchImages(true);
    await locateAndJumpCursor();
  }
}, { immediate: true });

watch(() => filters.split, async () => {
  await applyFilters();
  await locateAndJumpCursor();
});

// 未标注 / 同类重复 / 折叠相似 一改就出结果，不再需要「应用筛选」；fetchImages 会丢弃上一次请求
// 待复核和审查各有一条 toggle，它们自己调 applyFilters，别在这儿再触发一次
watch([() => filters.unannotated, () => filters.overlap_dup, () => filters.fold_dup], () => {
  applyFilters();
});

// 审查要占面积：进审查把侧边栏和顶栏收起，退出原样还回去。
// 手动那一档在「显示设置」里，随时能单独开合。
watch(reviewMode, (on) => store.setListFocus(on));

// 走查模式里类别只负责点亮缩略图上的候选框，不重新取图；其余时候还是按类别筛图
watch(selectedClassIds, () => {
  if (!reviewMode.value) applyFilters();
});

const handleGlobalKeydown = (e) => {
  if (e.key === 'Escape') {
    closeImageMenu();
    showDisplayMenu.value = false;
    showMoreMenu.value = false;
    // 聚焦把侧边栏和顶栏都收了，留一条不用翻按钮的退路；标注弹窗开着时它自己会接住这个键
    if (!currentImage.value && !showAutoAnnotateModal.value && !showCreateSubsetModal.value && !showAugmentSubsetModal.value) {
      store.setListFocus(false);
    }
  }
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
  // 离开数据集就把收起来的侧边栏和顶栏放回去，别把聚焦带到别的页面
  store.setListFocus(false);
  stopAutoAnnotatePolling();
  stopProbePolling();
  cancelKeywordSearch();
  if (activeImageRequestController) {
    activeImageRequestController.abort();
    activeImageRequestController = null;
  }
  window.removeEventListener('keydown', handleGlobalKeydown);
  document.removeEventListener('click', onDocClick);
});

const onDocClick = (e) => {
  if (showMoreMenu.value && moreMenuRef.value && !moreMenuRef.value.contains(e.target)) {
    showMoreMenu.value = false;
  }
  if (showDisplayMenu.value && displayMenuRef.value && !displayMenuRef.value.contains(e.target)) {
    showDisplayMenu.value = false;
  }
  if (imageMenu.value.open && imageMenuRef.value && !imageMenuRef.value.contains(e.target)) {
    closeImageMenu();
  }
};
</script>
