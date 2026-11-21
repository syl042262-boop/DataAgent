<template>
	<div class="workspace-page">
		<section class="workspace-intro">
			<div class="intro-copy">
				<span class="intro-greeting">欢迎来到 DataAgent</span>
				<h1>从一个问题，<br />发现数据里的答案。</h1>
				<p>连接业务数据，和你的分析助手一起探索。</p>
				<v-btn
					color="primary"
					variant="flat"
					size="large"
					@click="startAnalysis()"
					>开始分析<v-icon icon="mdi-plus" size="18" class="ml-3"
				/></v-btn>
			</div>
			<div class="data-sketch" aria-hidden="true">
				<div class="sketch-orbit orbit-one" />
				<div class="sketch-orbit orbit-two" />
				<div class="sketch-center"><BrandMark :size="64" /></div>
				<div class="sketch-node node-table">
					<v-icon icon="mdi-table" size="24" />
				</div>
				<div class="sketch-node node-chart">
					<svg width="58" height="38" viewBox="0 0 58 38">
						<path
							d="M2 33L17 23L29 27L43 9L56 3"
							fill="none"
							stroke="#24734D"
							stroke-width="2.5"
							stroke-linecap="round"
						/>
						<path d="M2 33L17 23L29 27L43 9L56 3V38H2Z" fill="#eaf4ed" />
					</svg>
				</div>
				<div class="sketch-node node-answer"><span /><span /><span /></div>
			</div>
		</section>
		<section class="workspace-shortcuts" aria-label="快捷入口">
			<NuxtLink
				v-for="entry in entries"
				:key="entry.path"
				:to="entry.path"
				class="shortcut-link"
				><v-icon :icon="entry.icon" size="22" />
				<div>
					<h2>{{ entry.title }}</h2>
					<p>{{ entry.description }}</p>
				</div>
				<v-icon icon="mdi-chevron-right" size="18"
			/></NuxtLink>
		</section>
		<section class="workspace-agents">
			<header class="section-heading">
				<div>
					<h2>你的分析助手</h2>
					<p>选择一个助手，继续探索业务数据。</p>
				</div>
				<NuxtLink to="/system/agents"
					>管理助手<v-icon icon="mdi-chevron-right" size="16"
				/></NuxtLink>
			</header>
			<p v-if="loading" class="workspace-state" role="status">
				正在加载分析助手…
			</p>
			<div v-else-if="error" class="workspace-state" role="alert">
				{{ error }} <button @click="loadAgents">重新加载</button>
			</div>
			<div v-else class="assistant-grid">
				<button
					v-for="agent in agents"
					:key="agent.id"
					class="assistant-tile"
					@click="startAnalysis(agent.id)"
				>
					<div class="assistant-top">
						<v-avatar size="42" rounded="lg" color="primary" variant="tonal"
							><v-img v-if="agent.avatar" :src="agent.avatar" /><v-icon
								v-else
								icon="mdi-chart-box-outline" /></v-avatar
						><span class="assistant-status">{{
							agent.status === 'published'
								? '已发布'
								: agent.status === 'offline'
									? '已下线'
									: '草稿'
						}}</span>
					</div>
					<h3>{{ agent.name }}</h3>
					<p>{{ agent.description || '连接数据，用自然语言开始分析。' }}</p>
					<span class="assistant-action"
						>打开助手<v-icon icon="mdi-arrow-top-right" size="16"
					/></span>
				</button>
				<NuxtLink to="/agent/new" class="assistant-create"
					><v-icon icon="mdi-plus" size="24" />
					<h3>创建分析助手</h3>
					<p>为你的业务建立专属分析空间</p></NuxtLink
				>
			</div>
		</section>
		<footer class="workspace-footnote">让提问更自然，让决策更清晰。</footer>
	</div>
</template>
<script setup lang="ts">
import agentService, { type Agent } from '~/services/agent/index';
const agents = ref<Agent[]>([]);
const loading = ref(true);
const error = ref('');
const router = useRouter();
const entries = [
	{
		title: '连接数据',
		description: '接入你的业务数据库',
		icon: 'mdi-database-outline',
		path: '/system/data-sources',
	},
	{
		title: '整理知识',
		description: '让分析理解业务语境',
		icon: 'mdi-book-open-outline',
		path: '/knowledge/business',
	},
	{
		title: '配置模型',
		description: '选择适合的分析引擎',
		icon: 'mdi-tune-variant',
		path: '/system/model-config',
	},
];
async function loadAgents() {
	loading.value = true;
	error.value = '';
	try {
		agents.value = await agentService.list();
	} catch {
		error.value = '未能加载分析助手，请检查服务连接后重试。';
	} finally {
		loading.value = false;
	}
}
function startAnalysis(id?: number) {
	const agentId = id || agents.value[0]?.id;
	router.push(
		agentId
			? { path: '/chat', query: { agentId: String(agentId) } }
			: '/agent/new',
	);
}
onMounted(loadAgents);
</script>
<style scoped>
.workspace-page {
	max-width: 1240px;
	margin: auto;
	padding: 52px 56px 24px;
}
.workspace-intro {
	display: flex;
	align-items: center;
	justify-content: space-between;
	min-height: 295px;
	padding-bottom: 42px;
}
.intro-greeting {
	font-size: 12px;
	color: #7f8c84;
}
.intro-copy h1 {
	font-size: clamp(30px, 3vw, 42px);
	font-weight: 600;
	line-height: 1.55;
	letter-spacing: -1.2px;
	color: #22392b;
	margin: 16px 0 14px;
}
.intro-copy p {
	font-size: 14px;
	color: #7a877e;
	margin-bottom: 26px;
}
.data-sketch {
	position: relative;
	width: 320px;
	height: 260px;
	margin-right: 28px;
}
.sketch-orbit {
	position: absolute;
	border: 1px solid #e2eae4;
	border-radius: 50%;
	inset: 20px 50px;
	transform: rotate(-25deg);
}
.orbit-two {
	inset: 55px 0;
	transform: rotate(-25deg);
}
.sketch-center {
	position: absolute;
	inset: 94px 128px;
}
.sketch-node {
	position: absolute;
	display: flex;
	align-items: center;
	justify-content: center;
	background: white;
	border: 1px solid #e1e9e3;
	border-radius: 12px;
	color: #73927e;
}
.node-table {
	top: 30px;
	left: 62px;
	width: 48px;
	height: 48px;
	transform: rotate(-10deg);
}
.node-chart {
	top: 65px;
	right: 5px;
	width: 90px;
	height: 66px;
	transform: rotate(8deg);
}
.node-answer {
	bottom: 16px;
	left: 72px;
	width: 78px;
	height: 54px;
	flex-direction: column;
	gap: 6px;
	transform: rotate(-5deg);
}
.node-answer span {
	width: 40px;
	height: 3px;
	background: #c6dccc;
	border-radius: 2px;
}
.node-answer span:last-child {
	width: 25px;
	align-self: flex-start;
	margin-left: 18px;
}
.workspace-shortcuts {
	display: grid;
	grid-template-columns: repeat(3, 1fr);
	padding: 24px 0;
	border-top: 1px solid #e6ece7;
	border-bottom: 1px solid #e6ece7;
	gap: 24px;
}
.shortcut-link {
	display: flex;
	align-items: center;
	gap: 16px;
	text-decoration: none;
	color: #567460;
	padding: 8px 4px;
}
.shortcut-link h2 {
	font-size: 14px;
	font-weight: 600;
	color: #34493c;
	margin-bottom: 4px;
}
.shortcut-link p {
	font-size: 12px;
	color: #76847a;
}
.shortcut-link > .v-icon:last-child {
	margin-left: auto;
	color: #a5b1a8;
}
.shortcut-link:hover h2 {
	color: #24734d;
}
.workspace-agents {
	margin-top: 40px;
}
.section-heading {
	display: flex;
	align-items: center;
	justify-content: space-between;
	gap: 16px;
	margin-bottom: 22px;
}
.section-heading h2 {
	font-size: 18px;
	font-weight: 600;
	margin-bottom: 6px;
}
.section-heading p {
	font-size: 12px;
	color: #76847a;
}
.section-heading a {
	display: flex;
	align-items: center;
	font-size: 12px;
	color: #63776a;
	text-decoration: none;
}
.assistant-grid {
	display: grid;
	grid-template-columns: repeat(3, minmax(0, 1fr));
	gap: 18px;
}
.assistant-tile,
.assistant-create {
	border: 1px solid #e4ebe6;
	border-radius: 12px;
	padding: 24px;
	text-align: left;
	background: white;
	min-width: 0;
}
.assistant-tile:hover,
.assistant-create:hover {
	border-color: #9dbfa8;
}
.assistant-top {
	display: flex;
	align-items: center;
	justify-content: space-between;
	margin-bottom: 20px;
}
.assistant-status {
	font-size: 11px;
	color: #7a897f;
}
.assistant-tile h3 {
	font-size: 15px;
	font-weight: 600;
	margin-bottom: 8px;
}
.assistant-tile p {
	font-size: 12px;
	line-height: 1.8;
	color: #76847a;
	display: -webkit-box;
	-webkit-line-clamp: 2;
	-webkit-box-orient: vertical;
	overflow: hidden;
	min-height: 44px;
}
.assistant-action {
	display: flex;
	align-items: center;
	gap: 8px;
	font-size: 12px;
	color: #24734d;
	margin-top: 22px;
}
.assistant-create {
	text-decoration: none;
	display: flex;
	align-items: center;
	justify-content: center;
	flex-direction: column;
	color: #7a9182;
	border-style: dashed;
	background: transparent;
	min-height: 230px;
}
.assistant-create h3 {
	font-size: 13px;
	font-weight: 500;
	margin: 14px 0 6px;
}
.assistant-create p {
	font-size: 11px;
	color: #95a097;
}
.workspace-footnote {
	text-align: center;
	font-size: 11px;
	color: #a2ada5;
	margin-top: 48px;
}
.workspace-state {
	padding: 32px;
	background: white;
	border-radius: 12px;
	font-size: 13px;
	color: #748478;
}
.workspace-state button {
	color: #24734d;
	text-decoration: underline;
	margin-left: 12px;
}
@media (max-width: 1050px) {
	.workspace-page {
		padding: 32px;
	}
	.data-sketch {
		width: 260px;
		transform: scale(0.85);
		margin-right: 0;
	}
	.assistant-grid {
		grid-template-columns: repeat(2, minmax(0, 1fr));
	}
}
@media (max-width: 650px) {
	.workspace-page {
		padding: 28px 20px;
	}
	.data-sketch {
		display: none;
	}
	.workspace-intro {
		min-height: auto;
		padding-bottom: 30px;
	}
	.workspace-shortcuts {
		grid-template-columns: 1fr;
		gap: 12px;
		padding: 16px 0;
	}
	.assistant-grid {
		grid-template-columns: 1fr;
	}
	.section-heading {
		align-items: flex-start;
	}
}
</style>
