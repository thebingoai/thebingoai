<template>
  <div class="hidden lg:flex lg:w-1/2 flex-col items-start bg-[#FAF5ED] dark:bg-neutral-950 p-10">
    <div class="w-full max-w-[515px] flex-1 flex flex-col justify-between">
      <!-- Logo -->
      <div>
        <img src="/logo/BINGO Logo Design_FA_Primary.png" alt="Bingo" style="height: 40px; width: auto;" class="dark:hidden" />
        <img src="/logo/BINGO Logo Design_FA_Primary_W.png" alt="Bingo" style="height: 40px; width: auto;" class="hidden dark:block" />
      </div>

      <!-- Marketing headline -->
      <div class="flex flex-col justify-center pl-8">
        <p class="text-[13px] tracking-widest font-medium text-neutral-500 dark:text-neutral-500 uppercase mb-2.5">
          {{ stepContext }}
        </p>
        <h1 class="font-display text-6xl font-bold leading-[1.1] text-neutral-900 dark:text-neutral-50 mb-3">
          The assistant<br>
          that <em class="italic text-purple-600">queries</em> with<br>
          you.
        </h1>
        <p class="text-base text-neutral-500 dark:text-neutral-400 leading-relaxed max-w-sm">
          Plug in a warehouse, ask a question, read a briefing over coffee. Your data, annotated.
        </p>

        <!-- Setup progress stepper -->
        <div class="mt-5 border-t border-dashed border-neutral-300 dark:border-neutral-700 pt-6">
          <p class="text-[13px] tracking-widest font-medium text-neutral-500 dark:text-neutral-500 uppercase mb-4">
            Setup · {{ step }}/3
          </p>
          <div class="flex gap-1.5 mb-3">
            <div
              v-for="i in 3"
              :key="i"
              class="h-0.5 flex-1 rounded-full"
              :class="i <= step ? 'bg-purple-600' : 'bg-neutral-200 dark:bg-neutral-700'"
            ></div>
          </div>
          <div class="flex text-[13px] text-neutral-400 dark:text-neutral-600">
            <span class="flex-1 text-left">Connect your Account</span>
            <span class="flex-1 text-center">Connect your First Plugin</span>
            <span class="flex-1 text-right">Start your First task</span>
          </div>
        </div>
      </div>

      <!-- Compliance footer -->
      <div>
        <p class="text-[11px] text-neutral-400 dark:text-neutral-600 tracking-wide">SOC 2 Type II · GDPR · HIPAA</p>
        <p class="text-[11px] text-neutral-400 dark:text-neutral-600 mt-1">Your queries never leave your warehouse.</p>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  step: 1 | 2 | 3 | 4
  stepContext: string
}>()
</script>
