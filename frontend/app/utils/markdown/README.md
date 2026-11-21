# 逻辑模块: markdown

## 函数 (Functions)
### `renderMarkdownContent`
- **描述**: 无描述
- **签名**: `export function renderMarkdownContent(content: string): string {
	if (!content) return '';
	return md.render(content);
}`


---
> 🤖 AI 提示: 逻辑实现请参考 `markdown\index.ts`。