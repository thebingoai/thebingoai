<script setup lang="ts">
definePageMeta({ middleware: 'admin' })
await navigateTo('/settings?tab=admin', { replace: true })
</script>
