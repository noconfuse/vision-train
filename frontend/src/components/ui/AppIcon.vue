<template>
  <component :is="iconComponent" :class="iconClass" :stroke-width="strokeWidth" />
</template>

<script setup>
import {
  Archive,
  ArrowDownToLine,
  ArrowLeft,
  ArrowRight,
  CircleAlert,
  ChartColumn,
  Check,
  ChevronDown,
  ChevronRight,
  ClipboardList,
  CircleHelp,
  CircleX,
  Download,
  Eye,
  EyeOff,
  FolderPlus,
  FolderTree,
  Lock,
  LogOut,
  Maximize2,
  Minimize2,
  MoreHorizontal,
  Pencil,
  Play,
  ScanLine,
  Settings2,
  Sparkles,
  Tags,
  Target,
  Trash2,
  User,
  Video,
  Workflow,
} from '@lucide/vue';
import { computed } from 'vue';

const ICON_MAP = {
  alert: CircleAlert,
  archive: Archive,
  back: ArrowLeft,
  check: Check,
  chevronDown: ChevronDown,
  chevronRight: ChevronRight,
  close: CircleX,
  createProject: FolderPlus,
  dataset: FolderTree,
  delete: Trash2,
  detail: ClipboardList,
  download: Download,
  eye: Eye,
  eyeOff: EyeOff,
  evaluate: ChartColumn,
  export: ArrowDownToLine,
  lock: Lock,
  logout: LogOut,
  maximize: Maximize2,
  minimize: Minimize2,
  moreHorizontal: MoreHorizontal,
  next: ArrowRight,
  previous: ArrowLeft,
  rename: Pencil,
  settings: Settings2,
  sparkles: Sparkles,
  split: ScanLine,
  tags: Tags,
  tasks: Workflow,
  target: Target,
  train: Play,
  user: User,
  video: Video,
  workflow: Workflow,
  help: CircleHelp,
};

const props = defineProps({
  name: { type: String, required: true },
  class: { type: String, default: 'h-4 w-4' },
  strokeWidth: { type: Number, default: 2 },
});

const iconComponent = computed(() => ICON_MAP[props.name] || FolderTree);
const iconClass = computed(() => props.class);
</script>
