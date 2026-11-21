<template>
	<v-card
		v-if="pythonBackend"
		variant="flat"
		border
		class="rounded-lg mb-4 pa-4"
	>
		<div class="text-subtitle-1 mb-3">知识召回设置</div>
		<div class="d-flex ga-3 align-center flex-wrap">
			<v-text-field
				v-model.number="topK"
				label="最多召回片段数"
				type="number"
				min="1"
				max="100"
				density="compact"
				hide-details
			/>
			<v-text-field
				v-model.number="threshold"
				label="最低相似度"
				type="number"
				min="-1"
				max="1"
				step="0.05"
				density="compact"
				hide-details
			/>
			<v-btn :loading="saving" :disabled="!valid" @click="save"
				>保存召回设置</v-btn
			>
		</div>
		<p class="text-caption mt-3">
			应用于当前智能体的业务知识、语义字段及知识文档。
		</p>
		<v-alert
			v-if="message"
			class="mt-3"
			:type="failed ? 'error' : 'success'"
			density="compact"
			>{{ message }}</v-alert
		>
	</v-card>
</template>

<script setup lang="ts">
const props = defineProps<{ agentId: number }>();
const pythonBackend = useRuntimeConfig().public.backend === 'python';
const topK = ref(8);
const threshold = ref(0);
const saving = ref(false);
const message = ref('');
const failed = ref(false);
const valid = computed(
	() =>
		Number.isInteger(topK.value) &&
		topK.value >= 1 &&
		topK.value <= 100 &&
		Number.isFinite(threshold.value) &&
		threshold.value >= -1 &&
		threshold.value <= 1,
);
interface PolicyResponse {
	success: boolean;
	message?: string;
	data: { topK: number; similarityThreshold: number };
}
let generation = 0;
watch(
	() => props.agentId,
	async (agentId) => {
		const current = ++generation;
		message.value = '';
		if (!pythonBackend || agentId <= 0) return;
		try {
			const result = await $fetch<PolicyResponse>(
				`/api/agent/${agentId}/knowledge/recall-config`,
			);
			if (current !== generation) return;
			if (!result.success) throw new Error(result.message);
			topK.value = result.data.topK;
			threshold.value = result.data.similarityThreshold;
		} catch {
			if (current !== generation) return;
			failed.value = true;
			message.value = '读取召回设置失败，请刷新后重试';
		}
	},
	{ immediate: true },
);
async function save() {
	if (!valid.value) return;
	saving.value = true;
	const current = generation;
	try {
		const result = await $fetch<PolicyResponse>(
			`/api/agent/${props.agentId}/knowledge/recall-config`,
			{
				method: 'PUT',
				body: { topK: topK.value, similarityThreshold: threshold.value },
			},
		);
		if (current !== generation) return;
		failed.value = !result.success;
		message.value = result.success
			? '召回设置已保存'
			: result.message || '保存失败';
	} catch {
		if (current !== generation) return;
		failed.value = true;
		message.value = '保存失败，请重试';
	} finally {
		saving.value = false;
	}
}
</script>
