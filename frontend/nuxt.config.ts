/*
 * Copyright 2026 the original author or authors.
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *      https://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

// https://nuxt.com/docs/api/configuration/nuxt-config
export default defineNuxtConfig({
	runtimeConfig: { public: { backend: 'java' } },
	compatibilityDate: '2025-07-15',
	devtools: { enabled: true },
	modules: ['vuetify-nuxt-module', '@pinia/nuxt', '@nuxt/eslint'],
	//基于组件名称自动导入
	components: [
		{
			path: '~/components', // 扫描 components 目录
			extensions: ['.vue'], // 确保只扫描 .vue 文件
			pathPrefix: false, // 禁用文件夹路径前缀
		},
	],
	imports: {
		dirs: [
			// 递归扫描所有的 index.ts，这样文件夹名就是函数名
			'composables/**/index.ts',
			'app/services/**/index.ts', // 匹配你规范中的 app/services/
			'composables/*.ts',
			'app/services/*.ts',
		],
	},
	vuetify: {
		vuetifyOptions: {
			theme: {
				defaultTheme: 'light',
				themes: { light: { colors: { primary: '#24734D', background: '#F7F9F7', surface: '#FFFFFF', 'on-surface': '#25372D' } } },
			},
			defaults: {
				VBtn: { variant: 'outlined', rounded: 'lg', elevation: 0 },
				VCard: { elevation: 0 },
			},
		},
	},
	vite: {
		build: {
			rollupOptions: {
				output: {
					manualChunks(id) {
						if (id.includes('/node_modules/zrender/')) return 'vendor-zrender';
						if (id.includes('/node_modules/echarts/')) return 'vendor-echarts';
						if (id.includes('/node_modules/highlight.js/'))
							return 'vendor-highlight';
					},
				},
			},
		},
	},
	//全局关闭ssr
	ssr: false,
	// /路由重定向到/create-agent
	routeRules: {
		'/': { redirect: '/workspace' },
		'/api/**': { proxy: `${process.env.DATAAGENT_PROXY_TARGET || 'http://localhost:8065'}/api/**` },
		'/nl2sql/**': { proxy: `${process.env.DATAAGENT_PROXY_TARGET || 'http://localhost:8065'}/nl2sql/**` },
	},
	//全局动画配置
	app: {
		head: { title: 'DataAgent · 数据分析工作空间', link: [{ rel: 'icon', type: 'image/svg+xml', href: '/favicon.svg' }] },
		pageTransition: { name: 'page', mode: 'out-in' },
	},
	css: ['@/assets/css/main.css'],
});
