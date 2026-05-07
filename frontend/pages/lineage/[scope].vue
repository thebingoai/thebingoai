<template>
  <div class="h-screen">
    <LineageView :scope="scope" />
  </div>
</template>

<script setup lang="ts">
import { useRoute } from 'vue-router'

const route = useRoute()
const scope = String(route.params.scope ?? '')
</script>
