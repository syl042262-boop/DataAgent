<template>
	<div v-if="enabled" class="pa-3">
		<v-text-field
			v-model="credential.credentials[agentId]"
			:disabled="checking"
			label="运行 API Key"
			type="password"
			autocomplete="off"
			hint="仅保存在本页内存，刷新后需重新输入。生成或重置后请复制新密钥。"
			persistent-hint
			hide-details="auto"
			@update:model-value="verified = false"
		/>
		<v-btn class="mt-2" :loading="checking" @click="verify">验证凭据</v-btn>
		<v-btn class="mt-2 ml-2" @click="clear">清除</v-btn>
		<span class="ml-3" role="status">{{ verified ? '凭据有效' : error }}</span>
	</div>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import { useRuntimeCredential } from '~/composables/useRuntimeCredential';

const props = defineProps<{ agentId: number; enabled: boolean }>();
const credential = useRuntimeCredential();
const verified = ref(false);
const checking = ref(false);
const error = ref('');

function clear() {
	credential.clear(props.agentId);
	verified.value = false;
	error.value = '';
}

async function verify() {
	checking.value = true;
	error.value = '';
	verified.value = false;
	try {
		const result = await fetch(`/api/agent/${props.agentId}/access`, {
			headers: credential.headers(props.agentId),
			cache: 'no-store',
		});
		verified.value = result.ok;
		if (!result.ok) error.value = '凭据无效或服务暂不可用';
	} catch {
		error.value = '无法连接服务';
	} finally {
		checking.value = false;
	}
}
</script>
