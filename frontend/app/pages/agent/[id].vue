<template>
	<div
		v-if="pythonBackend"
		class="pa-6"
		style="max-width: 1100px; margin: auto"
	>
		<h1 class="mb-4">智能体配置</h1>
		<v-alert
			v-if="notice"
			class="mb-4"
			:type="failed ? 'error' : 'success'"
			role="status"
			>{{ notice }}</v-alert
		>
		<v-card v-if="agent" class="pa-5 mb-4">
			<h2 class="mb-4">基本信息 · {{ agent.status }}</h2>
			<v-text-field v-model="agent.name" :disabled="busy" label="智能体名称" />
			<v-textarea v-model="agent.description" :disabled="busy" label="描述" rows="2" />
			<v-textarea v-model="agent.prompt" :disabled="busy" label="Prompt" rows="2" />
			<div class="d-flex ga-2 flex-wrap">
				<v-btn :disabled="busy" @click="saveAgent">保存信息</v-btn>
				<v-btn :disabled="busy" @click="changeStatus('publish')">发布</v-btn>
				<v-btn :disabled="busy" @click="changeStatus('offline')">下线</v-btn>
				<v-btn :to="`/chat?agentId=${id}`">进入问答</v-btn>
			</div>
		</v-card>
		<v-card class="pa-5 mb-4">
			<h2 class="mb-4">访问密钥</h2>
			<p>
				状态：{{ keyEnabled ? '已启用' : '已关闭' }} ·
				{{ keyExists ? '已配置密钥' : '未配置密钥' }}
			</p>
			<v-text-field
				v-if="revealedKey"
				v-model="revealedKey"
				label="请复制新密钥，仅本次显示"
				type="password"
				readonly
				autocomplete="off"
			/>
			<div class="d-flex ga-2 flex-wrap mt-3">
				<v-btn :disabled="busy" @click="rotateKey('generate')">生成密钥</v-btn>
				<v-btn :disabled="busy" @click="rotateKey('reset')">重置密钥</v-btn>
				<v-btn :disabled="busy" @click="toggleKey">{{
					keyEnabled ? '关闭鉴权' : '启用鉴权'
				}}</v-btn>
				<v-btn :disabled="busy" @click="removeKey">删除密钥</v-btn>
				<v-btn v-if="revealedKey" @click="copyKey">复制新密钥</v-btn>
			</div>
		</v-card>
		<v-card class="pa-5 mb-4">
			<h2 class="mb-4">预设问题</h2>
			<v-textarea v-model="questionLines" :disabled="busy" label="每行一个问题" rows="3" />
			<v-btn :disabled="busy" @click="saveQuestions">保存预设问题</v-btn>
		</v-card>
		<v-card class="pa-5 mb-4">
			<h2 class="mb-4">数据源与选表</h2>
			<v-select
				v-model="sourceId"
				:disabled="busy"
				label="选择数据源"
				:items="sources"
				item-title="name"
				item-value="id"
			/>
			<v-btn :disabled="busy || !sourceId" @click="bindSource"
				>绑定并激活</v-btn
			>
			<v-btn class="ml-2" to="/system/data-sources">配置数据连接</v-btn>
			<div v-for="source in bindings" :key="source.id" class="mt-5">
				<h3>
					{{ source.datasource.name }} ·
					{{ source.isActive ? '已启用' : '未启用' }}
				</h3>
				<v-select
					v-model="source.selectTables"
					:disabled="busy"
					:items="tableOptions[source.datasourceId] || []"
					label="允许查询的表"
					multiple
					chips
				/>
				<div class="d-flex ga-2 flex-wrap">
					<v-btn :disabled="busy" @click="saveTables(source)">保存选表</v-btn>
					<v-btn :disabled="busy" @click="toggleSource(source)">{{
						source.isActive ? '禁用数据源' : '启用数据源'
					}}</v-btn>
					<v-btn :disabled="busy || !source.isActive" @click="initialize"
						>初始化 Schema</v-btn
					>
					<v-btn :disabled="busy" @click="unbindSource(source)"
						>解绑数据源</v-btn
					>
				</div>
			</div>
		</v-card>
	</div>
	<h1 v-else>Agent Dashboard</h1>
</template>

<script setup lang="ts">
import axios from 'axios';
import type { Agent } from '~/services/agent';
import type { Datasource } from '~/services/datasource';

interface Binding {
	id: number;
	datasourceId: number;
	isActive: number;
	selectTables: string[];
	datasource: Datasource;
}
const pythonBackend = useRuntimeConfig().public.backend === 'python';
const route = useRoute();
const id = computed(() => Number(route.params.id));
const path = computed(() => `/api/agent/${id.value}`);
const agent = ref<Agent | null>(null);
const sources = ref<Datasource[]>([]);
const bindings = ref<Binding[]>([]);
const tableOptions = ref<Record<number, string[]>>({});
const sourceId = ref<number>();
const keyEnabled = ref(false);
const keyExists = ref(false);
const revealedKey = ref('');
const questionLines = ref('');
const notice = ref('');
const failed = ref(false);
const busy = ref(false);

async function api(method: string, url: string, data?: unknown) {
	const result = await axios.request({ method, url, data });
	if (result.data?.success === false) throw new Error(result.data.message);
	return result.data;
}
async function load() {
	agent.value = await api('GET', path.value);
	sources.value = await api('GET', '/api/datasource');
	const status = (await api('GET', `${path.value}/api-key`)).data;
	keyEnabled.value = Boolean(status.apiKeyEnabled);
	keyExists.value = Boolean(status.apiKey);
	const questions = (await api('GET', `${path.value}/preset-questions`)) as {
		question: string;
	}[];
	questionLines.value = questions.map((q) => q.question).join('\n');
	bindings.value = (await api('GET', `${path.value}/datasources`)).data;
	for (const binding of bindings.value) {
		try {
			tableOptions.value[binding.datasourceId] = await api(
				'GET',
				`/api/datasource/${binding.datasourceId}/tables`,
			);
		} catch {
			tableOptions.value[binding.datasourceId] = [...binding.selectTables];
		}
	}
}
async function perform(action: () => Promise<unknown>) {
	busy.value = true;
	failed.value = false;
	notice.value = '';
	try {
		await action();
		await load();
		notice.value = '操作成功';
	} catch (error) {
		failed.value = true;
		notice.value = error instanceof Error ? error.message : '操作失败';
	} finally {
		busy.value = false;
	}
}
const saveAgent = () =>
	perform(() =>
		api('PUT', path.value, {
			name: agent.value?.name,
			description: agent.value?.description,
			prompt: agent.value?.prompt,
		}),
	);
const changeStatus = (status: string) =>
	perform(() => api('POST', `${path.value}/${status}`));
const rotateKey = (action: string) =>
	perform(async () => {
		revealedKey.value = (
			await api('POST', `${path.value}/api-key/${action}`)
		).data.apiKey;
	});
const toggleKey = () =>
	perform(() =>
		api('POST', `${path.value}/api-key/enable?enabled=${!keyEnabled.value}`),
	);
const removeKey = () =>
	perform(async () => {
		await api('DELETE', `${path.value}/api-key`);
		revealedKey.value = '';
	});
const copyKey = async () => {
	try {
		await navigator.clipboard.writeText(revealedKey.value);
		notice.value = '已复制';
	} catch {
		failed.value = true;
		notice.value = '复制失败，请手动复制';
	}
};
const saveQuestions = () =>
	perform(() =>
		api(
			'POST',
			`${path.value}/preset-questions`,
			questionLines.value
				.split('\n')
				.map((q) => q.trim())
				.filter(Boolean)
				.map((question) => ({ question, isActive: true })),
		),
	);
const bindSource = () =>
	perform(() => api('POST', `${path.value}/datasources/${sourceId.value}`));
const unbindSource = (source: Binding) =>
	perform(() =>
		api('DELETE', `${path.value}/datasources/${source.datasourceId}`),
	);
const saveTables = (source: Binding) =>
	perform(() =>
		api('POST', `${path.value}/datasources/tables`, {
			datasourceId: source.datasourceId,
			tables: source.selectTables,
		}),
	);
const toggleSource = (source: Binding) =>
	perform(() =>
		api('PUT', `${path.value}/datasources/toggle`, {
			datasourceId: source.datasourceId,
			isActive: !source.isActive,
		}),
	);
const initialize = () =>
	perform(() => api('POST', `${path.value}/datasources/init`));
watch(
	id,
	() => {
		revealedKey.value = '';
		if (pythonBackend) void perform(async () => {});
	},
	{ immediate: true },
);
</script>
