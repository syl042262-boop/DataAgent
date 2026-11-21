<template>
	<v-app id="app">
		<v-main>
			<BaseDrawer v-model="drawer" :drawer-width="224">
				<template #drawer>
					<div class="product-nav">
						<NuxtLink to="/workspace" class="brand-link"
							><BrandMark :size="32" /><span>DataAgent</span></NuxtLink
						>
						<div class="workspace-select">
							<span class="nav-label">当前分析助手</span>
							<v-select
								v-model="selectedAgentId"
								:items="agentOptions"
								item-title="title"
								item-value="value"
								variant="outlined"
								density="compact"
								hide-details
								placeholder="选择分析助手"
								aria-label="当前分析助手"
								@update:model-value="handleAgentSwitch"
							/>
						</div>
						<nav class="nav-sections" aria-label="主导航">
							<section
								v-for="group in navGroups"
								:key="group.label"
								class="nav-group"
							>
								<p class="nav-label">{{ group.label }}</p>
								<button
									v-for="item in group.items"
									:key="item.path"
									class="nav-link"
									:class="{ 'is-active': isActive(item.path) }"
									:aria-current="isActive(item.path) ? 'page' : undefined"
									@click="navigateToPath(item.path)"
								>
									<v-icon :icon="item.icon" size="19" /><span>{{
										item.title
									}}</span
									><span v-if="isActive(item.path)" class="active-dot" />
								</button>
							</section>
						</nav>
						<div class="nav-footer">
							<BrandMark :size="22" />
							<div>
								<strong>让数据成为答案</strong><span>你的数据分析工作空间</span>
							</div>
						</div>
					</div>
				</template>
				<template #header="{ toggle, isOpen }">
					<v-btn
						icon
						variant="text"
						size="small"
						:aria-label="isOpen ? '收起导航' : '展开导航'"
						@click="toggle"
						><v-icon icon="mdi-menu" size="20"
					/></v-btn>
					<span class="header-divider" /><span class="route-title">{{
						currentRouteTitle
					}}</span>
					<v-spacer /><span class="header-brand">DataAgent</span>
				</template>
				<slot />
			</BaseDrawer>
		</v-main>
		<ConfirmDialog
			v-model="dialogState.isVisible"
			:title="dialogState.title"
			:message="dialogState.message"
			:prepend-icon="dialogState.icon"
			:confirm-text="dialogState.confirmText"
			@confirm="handleGlobalConfirm"
		/>
		<Tip />
	</v-app>
</template>
<script setup lang="ts">
import BaseDrawer from '../components/BaseDrawer/index.vue';
import agentService from '~/services/agent/index';
import { useDisplay } from 'vuetify';

const { dialogState, handleGlobalConfirm } = useConfirm();
const drawer = ref(true);
const { mobile } = useDisplay();
const router = useRouter();
const route = useRoute();
// 默认都展开
const navGroups = [
	{
		label: '工作空间',
		items: [
			{
				title: '工作台',
				path: '/workspace',
				icon: 'mdi-view-dashboard-outline',
			},
			{ title: '数据分析', path: '/chat', icon: 'mdi-chart-box-outline' },
			{
				title: '分析助手',
				path: '/system/agents',
				icon: 'mdi-account-box-outline',
			},
		],
	},
	{
		label: '数据与知识',
		items: [
			{
				title: '数据连接',
				path: '/system/data-sources',
				icon: 'mdi-database-outline',
			},
			{
				title: '业务知识',
				path: '/knowledge/business',
				icon: 'mdi-book-open-outline',
			},
			{
				title: '助手知识库',
				path: '/knowledge/agents',
				icon: 'mdi-folder-outline',
			},
			{
				title: '语义模型',
				path: '/knowledge/semantic-models',
				icon: 'mdi-vector-intersection',
			},
		],
	},
	{
		label: '配置',
		items: [
			{ title: '提示词', path: '/prompt-config', icon: 'mdi-text-box-outline' },
			{
				title: '模型配置',
				path: '/system/model-config',
				icon: 'mdi-tune-variant',
			},
		],
	},
];

watch(
	mobile,
	(isMobile) => {
		if (isMobile) drawer.value = false;
	},
	{ immediate: true },
);

type DrawerAgentOption = {
	id: number;
	name: string;
	title: string;
	value: number;
	subtitle: string;
	avatar?: string;
	tags?: string;
};

const agents = ref<DrawerAgentOption[]>([]);
const selectedAgentId = ref<number | undefined>(undefined);

const routeTitleMap: Record<string, string> = {
	'/workspace': '工作台',
	'/chat': '数据分析',
	'/system/agents': '分析助手',
	'/dashboard': '数据看板',
	'/prompt-config': '提示词配置',
	'/knowledge/business': '业务知识配置',
	'/knowledge/agents': '智能体知识库',
	'/knowledge/semantic-models': '语义模型配置',
	'/system/data-sources': '数据连接',
	'/system/model-config': '模型配置',
	'/system/settings': '通用设置',
	'/agent/new': '创建分析助手',
};

const agentOptions = computed(() => agents.value);

const currentRouteTitle = computed(() => {
	if (route.path.startsWith('/agent/') && route.path !== '/agent/new') {
		return '助手配置';
	}
	return routeTitleMap[route.path] || 'Data Agent';
});

function parseRouteAgentId() {
	const pathId = Number(route.params.id);
	if (
		route.path.startsWith('/agent/') &&
		route.path !== '/agent/new' &&
		Number.isFinite(pathId) &&
		pathId > 0
	) {
		return pathId;
	}
	const queryId = Number(route.query.agentId);
	if (Number.isFinite(queryId) && queryId > 0) {
		return queryId;
	}
	return undefined;
}

function getQueryWithAgentId(agentId?: number) {
	const query: Record<string, string> = {};
	Object.keys(route.query).forEach((key) => {
		const value = route.query[key];
		if (key === 'agentId') return;
		if (Array.isArray(value)) {
			if (value[0]) query[key] = String(value[0]);
		} else if (value !== undefined) {
			query[key] = String(value);
		}
	});
	if (agentId) query.agentId = String(agentId);
	return query;
}

function applyAgentToCurrentRoute(agentId: number, replace = false) {
	if (route.path === '/agent/new') return;
	const target =
		route.path.startsWith('/agent/') && route.path !== '/agent/new'
			? { path: `/agent/${agentId}` }
			: { path: route.path, query: getQueryWithAgentId(agentId) };
	if (replace) {
		router.replace(target);
	} else {
		router.push(target);
	}
}

function navigateToPath(path: string) {
	if (mobile.value) drawer.value = false;
	if (path === '/agent/new') {
		if (route.path !== path) router.push({ path });
		return;
	}
	if (
		route.path === path &&
		path.startsWith('/agent/') &&
		selectedAgentId.value
	) {
		return;
	}
	if (selectedAgentId.value) {
		if (path.startsWith('/agent/') && path !== '/agent/new') {
			router.push({ path: `/agent/${selectedAgentId.value}` });
			return;
		}
		router.push({ path, query: { agentId: String(selectedAgentId.value) } });
		return;
	}
	router.push({ path });
}

function handleAgentSwitch(value: number | string | undefined) {
	const id = Number(value);
	if (!Number.isFinite(id) || id <= 0) return;
	selectedAgentId.value = id;
	applyAgentToCurrentRoute(id);
}

const isActive = (path: string) => route.path === path;

async function loadAgents() {
	const list = await agentService.list();
	agents.value = list
		.filter((item) => item.id !== undefined && item.id > 0)
		.map((item) => {
			const raw = item as unknown as Record<string, unknown>;
			return {
				id: item.id as number,
				name: item.name || `Agent ${item.id}`,
				title: item.name || `Agent ${item.id}`,
				value: item.id as number,
				subtitle: typeof raw.tags === 'string' ? raw.tags : '',
				avatar: typeof raw.avatar === 'string' ? raw.avatar : undefined,
				tags: typeof raw.tags === 'string' ? raw.tags : '',
			};
		});
}

function syncSelectedFromRoute() {
	const routeAgentId = parseRouteAgentId();
	if (routeAgentId && agents.value.some((item) => item.id === routeAgentId)) {
		selectedAgentId.value = routeAgentId;
	}
}

onMounted(async () => {
	try {
		await loadAgents();
	} catch {
		agents.value = [];
	}
	syncSelectedFromRoute();
	const firstAgent = agents.value[0];
	if (!selectedAgentId.value && firstAgent?.id) {
		selectedAgentId.value = firstAgent.id;
		applyAgentToCurrentRoute(selectedAgentId.value, true);
	}
});

watch(
	() => route.fullPath,
	() => {
		syncSelectedFromRoute();
	},
);
</script>

<style scoped>
.product-nav {
	height: 100%;
	display: flex;
	flex-direction: column;
	padding: 30px 18px 20px;
}
.brand-link {
	display: flex;
	align-items: center;
	gap: 10px;
	text-decoration: none;
	color: #202d28;
	font:
		650 22px 'Segoe UI',
		sans-serif;
	letter-spacing: -0.8px;
	padding: 0 6px;
}
.workspace-select {
	margin: 34px 0 24px;
}
.nav-label {
	display: block;
	font-size: 11px;
	color: #8a948e;
	margin: 0 10px 10px;
	font-weight: 500;
}
.workspace-select :deep(.v-field) {
	background: white;
	font-size: 12px;
	border-radius: 8px;
}
.nav-sections {
	overflow-y: auto;
	flex: 1;
}
.nav-group {
	margin-bottom: 26px;
}
.nav-link {
	width: 100%;
	display: flex;
	align-items: center;
	gap: 12px;
	padding: 11px 12px;
	border-radius: 7px;
	font-size: 13px;
	text-align: left;
	color: #65716a;
	margin: 3px 0;
}
.nav-link:hover {
	background: #eff3f0;
	color: #263e31;
}
.nav-link.is-active {
	background: #e9f3ed;
	color: #23734b;
	font-weight: 600;
}
.active-dot {
	width: 5px;
	height: 5px;
	border-radius: 50%;
	background: #278052;
	margin-left: auto;
}
.nav-footer {
	display: flex;
	align-items: center;
	gap: 10px;
	padding: 20px 6px 0;
	border-top: 1px solid #e8ede9;
}
.nav-footer strong,
.nav-footer span {
	display: block;
	font-size: 11px;
	font-weight: 400;
	color: #718077;
}
.nav-footer span {
	color: #a0aaa3;
	margin-top: 3px;
	font-size: 10px;
}
.header-divider {
	height: 16px;
	width: 1px;
	background: #e5eae7;
	margin: 0 18px 0 12px;
}
.route-title {
	font-size: 13px;
	color: #65716a;
}
.header-brand {
	font-size: 12px;
	color: #98a29b;
}
</style>
