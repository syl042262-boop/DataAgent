<template>
	<svg
		:width="size"
		:height="size"
		viewBox="0 0 40 40"
		fill="none"
		aria-hidden="true"
	>
		<rect width="40" height="40" rx="12" fill="#24734D" />
		<path
			d="M11 27V20M20 27V12M29 27V16"
			stroke="white"
			stroke-width="4"
			stroke-linecap="round"
		/>
		<circle cx="29" cy="10" r="2" fill="#A8D6BA" />
	</svg>
</template>
<script setup lang="ts">
withDefaults(defineProps<{ size?: number }>(), { size: 32 });
</script>
