import type { GraphNodeResponse } from './index';

export interface SseFrame {
	event: string;
	data: string;
}

export interface StreamSearchFetchOptions {
	url: string;
	headers: Record<string, string>;
	onMessage: (response: GraphNodeResponse) => Promise<void>;
	onError?: (error: Error) => Promise<void>;
	onComplete?: () => Promise<void>;
	fetchImpl?: typeof fetch;
	signal?: AbortSignal;
	onThreadId?: (threadId: string) => void;
}

export class SseFrameParser {
	private buffer = '';
	private eventName = 'message';
	private dataLines: string[] = [];

	constructor(private readonly onFrame: (frame: SseFrame) => void) {}

	feed(chunk: string): void {
		this.buffer += chunk.replace(/\r\n/g, '\n').replace(/\r/g, '\n');
		let newlineIdx = this.buffer.indexOf('\n');
		while (newlineIdx !== -1) {
			const line = this.buffer.slice(0, newlineIdx);
			this.buffer = this.buffer.slice(newlineIdx + 1);
			this.processLine(line);
			newlineIdx = this.buffer.indexOf('\n');
		}
	}

	flush(): void {
		if (this.buffer.length > 0) {
			this.processLine(this.buffer);
			this.buffer = '';
		}
		this.dispatch();
	}

	private processLine(line: string): void {
		if (line === '') {
			this.dispatch();
			return;
		}
		if (line.startsWith(':')) {
			return;
		}
		const colonIdx = line.indexOf(':');
		const field = colonIdx === -1 ? line : line.slice(0, colonIdx);
		let value = colonIdx === -1 ? '' : line.slice(colonIdx + 1);
		if (value.startsWith(' ')) {
			value = value.slice(1);
		}
		if (field === 'event') {
			this.eventName = value || 'message';
		} else if (field === 'data') {
			this.dataLines.push(value);
		}
	}

	private dispatch(): void {
		if (this.dataLines.length === 0) {
			this.eventName = 'message';
			return;
		}
		const frame: SseFrame = {
			event: this.eventName,
			data: this.dataLines.join('\n'),
		};
		this.eventName = 'message';
		this.dataLines = [];
		this.onFrame(frame);
	}
}

export async function streamSearchFetch(options: StreamSearchFetchOptions): Promise<void> {
	const {
		url,
		headers,
		onMessage,
		onError,
		onComplete,
		fetchImpl = fetch,
		signal,
		onThreadId,
	} = options;

	let response: Response;
	try {
		response = await fetchImpl(url, {
			method: 'GET',
			headers: { ...headers, Accept: 'text/event-stream' },
			signal,
		});
	} catch (err) {
		if (signal?.aborted) return;
		if (onError) {
			await onError(err instanceof Error ? err : new Error('Stream connection failed'));
		}
		return;
	}

	if (!response.ok) {
		let message = `请求失败 (HTTP ${response.status})`;
		try {
			const body = await response.json();
			const detail = body?.message || body?.detail;
			if (detail) {
				message = `HTTP ${response.status}: ${detail}`;
			}
		} catch {
			// Ignore non-JSON error body.
		}
		if (onError) {
			await onError(new Error(message));
		}
		return;
	}

	if (!response.body) {
		if (onError) {
			await onError(new Error('Stream response body is empty'));
		}
		return;
	}

	let finished = false;
	let chain = Promise.resolve();
	const parser = new SseFrameParser((frame) => {
		chain = chain.then(async () => {
			if (finished) return;
			if (frame.event === 'complete') {
				finished = true;
				if (onComplete) await onComplete();
				return;
			}
			if (frame.event === 'error') {
				finished = true;
				try {
					const parsed = JSON.parse(frame.data) as GraphNodeResponse;
					if (onError) {
						await onError(new Error(parsed.text || 'Stream processing failed'));
					}
				} catch {
					if (onError) await onError(new Error('Stream processing failed'));
				}
				return;
			}
			try {
				const nodeResponse = JSON.parse(frame.data) as GraphNodeResponse;
				if (nodeResponse.threadId && onThreadId) {
					onThreadId(nodeResponse.threadId);
				}
				await onMessage(nodeResponse);
			} catch {
				finished = true;
				if (onError) {
					await onError(new Error('Failed to parse server response'));
				}
			}
		});
	});

	const reader = response.body.getReader();
	const decoder = new TextDecoder('utf-8');
	try {
		while (true) {
			const { value, done } = await reader.read();
			if (done) break;
			if (value) {
				parser.feed(decoder.decode(value, { stream: true }));
			}
		}
		parser.feed(decoder.decode());
		parser.flush();
		await chain;
	} catch (err) {
		if (!signal?.aborted && !finished && onError) {
			await onError(err instanceof Error ? err : new Error('Stream connection failed'));
		}
	}
}
