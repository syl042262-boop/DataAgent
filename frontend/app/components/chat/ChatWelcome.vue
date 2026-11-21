/* * Copyright 2026 the original author or authors. * * Licensed under the
Apache License, Version 2.0 (the "License"); * you may not use this file except
in compliance with the License. * You may obtain a copy of the License at * *
https://www.apache.org/licenses/LICENSE-2.0 * * Unless required by applicable
law or agreed to in writing, software * distributed under the License is
distributed on an "AS IS" BASIS, * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
either express or implied. * See the License for the specific language governing
permissions and * limitations under the License. */

<template>
	<div class="welcome-wrap">
		<BrandMark :size="54" />
		<h2>今天，想了解哪些数据？</h2>
		<p>
			{{
				store.currentAgentDescription ||
				'从一个业务问题开始，让数据给出清晰的答案。'
			}}
		</p>
		<div class="welcome-context">
			<span class="context-dot" />{{
				store.currentAgentName || 'DataAgent 分析助手'
			}}
		</div>
	</div>
</template>
<script setup lang="ts">
import { useChatStore } from '~/stores/chat';
const store = useChatStore();
</script>
<style scoped>
.welcome-wrap {
	display: flex;
	flex: 1;
	align-items: center;
	justify-content: center;
	flex-direction: column;
	padding: 48px 24px;
	text-align: center;
}
h2 {
	font-size: clamp(24px, 2.5vw, 32px);
	font-weight: 500;
	letter-spacing: -0.7px;
	margin: 26px 0 12px;
	color: #253d2e;
}
p {
	font-size: 13px;
	line-height: 1.9;
	max-width: 440px;
	color: #8a978e;
}
.welcome-context {
	display: flex;
	align-items: center;
	gap: 7px;
	color: #829087;
	font-size: 11px;
	margin-top: 24px;
}
.context-dot {
	width: 5px;
	height: 5px;
	background: #3e8b5c;
	border-radius: 50%;
}
</style>
