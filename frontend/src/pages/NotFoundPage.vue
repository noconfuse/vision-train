<template>
  <div class="h-screen w-screen bg-slate-950 text-white flex items-center justify-center px-6">
    <div class="w-full max-w-2xl">
      <div class="inline-flex items-center gap-2 px-3 py-1 bg-white/10 text-xs uppercase tracking-[0.2em] text-slate-300">
        404
      </div>
      <h1 class="mt-6 text-4xl md:text-5xl font-bold tracking-tight">
        页面不存在
      </h1>
      <p class="mt-4 text-slate-400 text-base leading-7 max-w-xl">
        你访问的地址可能已被移除、改名，或者链接本身就是错误的。
        可以返回首页、登录页，或者看看产品落地页。
      </p>

      <div class="mt-8 flex flex-wrap gap-3">
        <RouterLink
          to="/"
          class="vt-btn-solid-primary vt-btn-size-lg"
        >
          返回首页
        </RouterLink>
        <RouterLink
          to="/login"
          class="vt-btn-secondary vt-btn-size-lg border-white/15 bg-transparent text-white hover:bg-white/5"
        >
          去登录
        </RouterLink>
        <RouterLink
          to="/landing"
          class="vt-btn-secondary vt-btn-size-lg border-white/15 bg-transparent text-white hover:bg-white/5"
        >
          查看落地页
        </RouterLink>
      </div>
    </div>
  </div>
</template>
