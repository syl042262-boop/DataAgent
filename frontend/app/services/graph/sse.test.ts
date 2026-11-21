import { describe, expect, it, vi } from 'vitest';
import type { GraphNodeResponse } from './index';
import { SseFrameParser, streamSearchFetch } from './sse';

describe('SseFrameParser', () => {
	it('parses CRLF, chunked frames, comments, multi-line data, and event types', () => {
		const received: Array<{ event: string; data: string }> = [];
		const parser = new SseFrameParser((frame) => received.push(frame));

		parser.feed(': heartbeat\r\n\r\n');
		parser.feed('event: message\r\ndata: {"text":"a"}\r\n\r');
		parser.feed('\nevent: complete\ndata: {"complete":');
		parser.feed('true}\n');
		parser.feed('data: {"ignored":false}\n\n');
		parser.flush();

		expect(received).toEqual([
			{ event: 'message', data: '{"text":"a"}' },
			{ event: 'complete', data: '{"complete":true}\n{"ignored":false}' },
		]);
	});
});

describe('streamSearchFetch', () => {
	it('sends X-API-Key header, reports 401 before streaming, and never retries', async () => {
		const fetchMock = vi.fn().mockResolvedValue(
			new Response(JSON.stringify({ detail: 'API Key 无效或缺失' }), {
				status: 401,
				headers: { 'Content-Type': 'application/json' },
			}),
		);
		const onMessage = vi.fn();
		const onError = vi.fn();
		const onComplete = vi.fn();

		await streamSearchFetch({
			url: '/api/stream/search?agentId=1&query=hi',
			headers: { 'X-API-Key': 'sk-secret' },
			onMessage,
			onError,
			onComplete,
			fetchImpl: fetchMock as unknown as typeof fetch,
		});

		expect(fetchMock).toHaveBeenCalledTimes(1);
		expect(fetchMock.mock.calls[0]?.[1]?.headers).toEqual({
			'X-API-Key': 'sk-secret',
			Accept: 'text/event-stream',
		});
		expect(onError).toHaveBeenCalledTimes(1);
		expect(onError.mock.calls[0]?.[0]?.message).toContain('401');
		expect(onMessage).not.toHaveBeenCalled();
		expect(onComplete).not.toHaveBeenCalled();
	});

	it('streams message and complete events strictly in order without calling onError', async () => {
		const encoder = new TextEncoder();
		const stream = new ReadableStream<Uint8Array>({
			start(controller) {
				controller.enqueue(
					encoder.encode(
						'event: message\ndata: {"agentId":"1","threadId":"t1","nodeName":"SqlGenerateNode","textType":"SQL","text":"SELECT 1","error":false,"complete":false}\n\n',
					),
				);
				controller.enqueue(
					encoder.encode(
						'event: complete\ndata: {"agentId":"1","threadId":"t1","nodeName":"","textType":"TEXT","text":"","error":false,"complete":true}\n\n',
					),
				);
				controller.close();
			},
		});
		const fetchMock = vi.fn().mockResolvedValue(
			new Response(stream, {
				status: 200,
				headers: { 'Content-Type': 'text/event-stream' },
			}),
		);
		const order: string[] = [];
		const onMessage = vi.fn(async (_response: GraphNodeResponse) => {
			await new Promise((r) => setTimeout(r, 15));
			order.push('message');
		});
		const onError = vi.fn();
		const onComplete = vi.fn(async () => {
			order.push('complete');
		});

		await streamSearchFetch({
			url: '/api/stream/search?agentId=1&query=hi',
			headers: {},
			onMessage,
			onError,
			onComplete,
			fetchImpl: fetchMock as unknown as typeof fetch,
		});

		expect(order).toEqual(['message', 'complete']);
		expect(onMessage.mock.calls[0]?.[0]?.text).toBe('SELECT 1');
		expect(onError).not.toHaveBeenCalled();
	});
});
