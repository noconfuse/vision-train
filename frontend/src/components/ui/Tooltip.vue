<template>
  <TooltipProvider
    :delay-duration="delayDuration"
    :disable-hoverable-content="disableHoverableContent"
  >
    <TooltipRoot
      :delay-duration="delayDuration"
      :disable-hoverable-content="disableHoverableContent"
    >
      <TooltipTrigger as-child>
        <slot name="trigger" />
      </TooltipTrigger>
      <TooltipPortal>
        <TooltipContent
          :side="side"
          :align="align"
          :side-offset="sideOffset"
          :collision-padding="collisionPadding"
          :avoid-collisions="true"
          class="z-50 border border-slate-300 bg-slate-900 px-2.5 py-2 text-[11px] leading-5 text-white shadow-lg"
          :class="contentClass"
        >
          <slot />
        </TooltipContent>
      </TooltipPortal>
    </TooltipRoot>
  </TooltipProvider>
</template>

<script setup>
import {
  TooltipContent,
  TooltipPortal,
  TooltipProvider,
  TooltipRoot,
  TooltipTrigger,
} from 'reka-ui';

defineProps({
  side: { type: String, default: 'top' },
  align: { type: String, default: 'center' },
  sideOffset: { type: Number, default: 8 },
  collisionPadding: { type: Number, default: 8 },
  delayDuration: { type: Number, default: 150 },
  disableHoverableContent: { type: Boolean, default: true },
  contentClass: { type: [String, Array, Object], default: '' },
});
</script>
