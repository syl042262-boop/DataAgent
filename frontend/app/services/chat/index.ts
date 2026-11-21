/*
 * Copyright 2024-2025 the original author or authors.
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

/**
 * @description 聊天会话服务，处理会话的创建、查询、删除、置顶以及消息的保存与报告下载
 */

import axios from 'axios';
import { useRuntimeCredential } from '../../composables/useRuntimeCredential';
import type { ApiResponse } from '../common';

/**
 * @description 聊天会话实体接口
 */
export interface ChatSession {
  /** 会话 ID (UUID) */
  id: string;
  /** 关联的智能体 ID */
  agentId: number;
  /** 会话标题 */
  title: string;
  /** 状态 (active, archived, deleted) */
  status: string;
  /** 是否置顶 */
  isPinned: boolean;
  /** 用户 ID */
  userId?: number;
  /** 创建时间 */
  createTime?: Date;
  /** 更新时间 */
  updateTime?: Date;
}

/**
 * @description 聊天消息实体接口
 */
export interface ChatMessage {
  /** 消息 ID */
  id?: number;
  /** 所属会话 ID */
  sessionId: string;
  /** 角色 (user, assistant, system) */
  role: string;
  /** 消息内容 */
  content: string;
  /** 消息类型 (text, sql, result, error) */
  messageType: string;
  /** 元数据 (JSON 字符串) */
  metadata?: string;
  /** 创建时间 */
  createTime?: Date;
  /** 是否需要生成标题 */
  titleNeeded?: boolean;
}

const API_BASE_URL = '/api';

/**
 * @description 聊天业务逻辑处理类
 */
class ChatService {
  private sessionAgents = new Map<string, number>();

  /**
   * @description 读取持久化运行摘要，恢复原 threadId、计划及卡片版本，不触发执行。
   * @param sessionId - 所属会话 ID
   * @param agentId - 用于当前内存凭据及归属校验的 Agent ID
   * @returns 无占用时为 null；recoverable 为真时可用同一计划版本提交反馈。
   */
  async activeRun(sessionId: string, agentId: number) {
    const response = await axios.get(`/api/sessions/${sessionId}/active-run`, {
      headers: useRuntimeCredential().headers(agentId), params: { agentId },
    });
    return response.data.data as null | {
      threadId: string; status: string; planRevision: number;
      plan: Record<string, unknown>; recoverable: boolean;
      resumeRequest: {query: string; humanFeedback: boolean; nl2sqlOnly: boolean};
    };
  }

  /**
   * @description 使用当前 Agent 凭据取消运行或待审核计划，等待停止入口返回 204。
   * @param sessionId - 必填会话 ID
   * @param agentId - 必填 Agent ID，必须与会话和运行归属一致
   * @param threadId - 可选的目标运行 ID，省略时取消会话的当前占用
   */
  async stopRun(sessionId: string, agentId: number, threadId?: string) {
    await axios.post('/api/stream/stop', null, {
      params: { agentId, conversationId: sessionId, threadId },
      headers: useRuntimeCredential().headers(agentId),
    });
  }

  private auth(sessionId: string) {
    const agentId = this.sessionAgents.get(sessionId);
    return { headers: agentId ? useRuntimeCredential().headers(agentId) : {} };
  }

  /**
   * @description 按游标读取会话的持久化运行列表，不恢复或重新执行工作流。
   * @param sessionId - 所属会话 ID
   * @param agentId - 用于凭据及归属校验的 Agent ID
   * @param cursor - 上一页返回的分页游标
   */
  async listRuns(sessionId: string, agentId: number, cursor?: string) {
    const response = await axios.get(`/api/sessions/${sessionId}/runs`, {
      headers: useRuntimeCredential().headers(agentId), params: { agentId, cursor },
    });
    return response.data.data as {items: {threadId: string; status: string; hasResult: boolean}[];
      nextCursor: string | null; activeThreadId: string | null};
  }

  /**
   * @description 获取已有运行及终态结果，用稳定 messageKey 补存展示消息。
   * @param sessionId - 所属会话 ID
   * @param agentId - 用于凭据及归属校验的 Agent ID
   * @param threadId - 目标运行 ID
   */
  async runDetail(sessionId: string, agentId: number, threadId: string) {
    const response = await axios.get(`/api/sessions/${sessionId}/runs/${threadId}`, {
      headers: useRuntimeCredential().headers(agentId), params: { agentId },
    });
    return response.data.data as {status: string; result: null | {messages:
      {messageKey: string; role: string; content: string; messageType: string; metadata: Record<string, unknown>}[]}};
  }

  /**
   * @description 获取指定智能体的会话列表
   * @param {number} agentId - 智能体 ID
   * @returns {Promise<ChatSession[]>} 会话列表
   */
  async getAgentSessions(agentId: number): Promise<ChatSession[]> {
    const response = await axios.get<ChatSession[]>(`${API_BASE_URL}/agent/${agentId}/sessions`);
    for (const session of response.data) this.sessionAgents.set(session.id, agentId);
    return response.data;
  }

  /**
   * @description 创建新会话
   * @param {number} agentId - 智能体 ID
   * @param {string} [title] - 会话标题
   * @param {number} [userId] - 用户 ID
   * @returns {Promise<ChatSession>} 创建成功的会话详情
   */
  async createSession(agentId: number, title?: string, userId?: number): Promise<ChatSession> {
    const request = {
      title,
      userId,
    };

    const response = await axios.post<ChatSession>(
      `${API_BASE_URL}/agent/${agentId}/sessions`,
      request,
    );
    this.sessionAgents.set(response.data.id, agentId);
    return response.data;
  }

  /**
   * @description 清空指定智能体的所有会话
   * @param {number} agentId - 智能体 ID
   * @returns {Promise<ApiResponse>} 操作结果
   */
  async clearAgentSessions(agentId: number): Promise<ApiResponse> {
    const response = await axios.delete<ApiResponse>(`${API_BASE_URL}/agent/${agentId}/sessions`, {
      headers: useRuntimeCredential().headers(agentId),
    });
    return response.data;
  }

  /**
   * @description 获取指定会话的所有消息
   * @param {string} sessionId - 会话 ID
   * @returns {Promise<ChatMessage[]>} 消息列表
   */
  async getSessionMessages(sessionId: string): Promise<ChatMessage[]> {
    const response = await axios.get<ChatMessage[]>(
      `${API_BASE_URL}/sessions/${sessionId}/messages`,
      this.auth(sessionId),
    );
    return response.data;
  }

  /**
   * @description 保存消息到指定会话
   * @param {string} sessionId - 会话 ID
   * @param {ChatMessage} message - 消息内容
   * @returns {Promise<ChatMessage>} 保存后的消息详情
   */
  async saveMessage(sessionId: string, message: ChatMessage): Promise<ChatMessage> {
    try {
      const messageData = {
        ...message,
        sessionId,
      };

      const response = await axios.post<ChatMessage>(
        `${API_BASE_URL}/sessions/${sessionId}/messages`,
        messageData,
        this.auth(sessionId),
      );
      return response.data;
    } catch (error) {
      if (axios.isAxiosError(error) && error.response?.status === 500) {
        throw new Error('保存消息失败');
      }
      throw error;
    }
  }

  /**
   * @description 置顶或取消置顶会话
   * @param {string} sessionId - 会话 ID
   * @param {boolean} isPinned - 是否置顶
   * @returns {Promise<ApiResponse>} 操作结果
   */
  async pinSession(sessionId: string, isPinned: boolean): Promise<ApiResponse> {
    try {
      const response = await axios.put<ApiResponse>(
        `${API_BASE_URL}/sessions/${sessionId}/pin`,
        null,
        {
          ...this.auth(sessionId),
          params: { isPinned },
        },
      );
      return response.data;
    } catch (error) {
      if (axios.isAxiosError(error) && error.response?.status === 400) {
        throw new Error('isPinned参数不能为空');
      }
      if (axios.isAxiosError(error) && error.response?.status === 500) {
        throw new Error('操作失败');
      }
      throw error;
    }
  }

  /**
   * @description 重命名会话标题
   * @param {string} sessionId - 会话 ID
   * @param {string} title - 新标题
   * @returns {Promise<ApiResponse>} 操作结果
   */
  async renameSession(sessionId: string, title: string): Promise<ApiResponse> {
    try {
      if (!title || title.trim().length === 0) {
        throw new Error('标题不能为空');
      }

      const response = await axios.put<ApiResponse>(
        `${API_BASE_URL}/sessions/${sessionId}/rename`,
        null,
        {
          ...this.auth(sessionId),
          params: { title: title.trim() },
        },
      );
      return response.data;
    } catch (error) {
      if (axios.isAxiosError(error) && error.response?.status === 400) {
        throw new Error('标题不能为空');
      }
      if (axios.isAxiosError(error) && error.response?.status === 500) {
        throw new Error('重命名失败');
      }
      throw error;
    }
  }

  /**
   * @description 删除指定会话
   * @param {string} sessionId - 会话 ID
   * @returns {Promise<ApiResponse>} 操作结果
   */
  async deleteSession(sessionId: string): Promise<ApiResponse> {
    try {
      const response = await axios.delete<ApiResponse>(`${API_BASE_URL}/sessions/${sessionId}`, this.auth(sessionId));
      return response.data;
    } catch (error) {
      if (axios.isAxiosError(error) && error.response?.status === 500) {
        throw new Error('删除失败');
      }
      throw error;
    }
  }

  /**
   * @description 下载会话的 HTML 报告
   * @param {string} sessionId - 会话 ID
   * @param {string} content - 报告内容
   * @returns {Promise<void>}
   */
  async downloadHtmlReport(sessionId: string, content: string): Promise<void> {
    try {
      const response = await axios.post(
        `${API_BASE_URL}/sessions/${sessionId}/reports/html`,
        content,
        {
          responseType: 'blob',
          headers: {
            'Content-Type': 'text/plain;charset=utf-8',
          },
        },
      );

      const contentDisposition = response.headers['content-disposition'];
      let filename = 'report.html';
      if (contentDisposition) {
        const filenameMatch = contentDisposition.match(/filename="?([^;"]+)"?/);
        if (filenameMatch && filenameMatch[1]) {
          filename = filenameMatch[1];
        }
      }

      const blob = new Blob([response.data], { type: 'text/html' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (error) {
      if (axios.isAxiosError(error)) {
        throw new Error(`下载失败: ${error.message}`);
      }
      throw error;
    }
  }
}

export default new ChatService();
