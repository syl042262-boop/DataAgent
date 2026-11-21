import { reactive } from 'vue';

// Module memory only: never put runtime credentials in routes or browser storage.
const credentials = reactive<Record<number, string>>({});

export function useRuntimeCredential() {
	function headers(agentId: number): Record<string, string> {
		const key = credentials[agentId];
		return key ? { 'X-API-Key': key } : {};
	}

	return {
		credentials,
		headers,
		clear(agentId: number) {
			delete credentials[agentId];
		},
	};
}
