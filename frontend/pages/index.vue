<script setup lang="ts">
// Redirect to chat
definePageMeta({
  middleware: [
    function () {
      return navigateTo('/chat')
    }
  ]
})
</script>

<template>
  <div></div>
</template>
