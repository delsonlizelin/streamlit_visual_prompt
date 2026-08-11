# 三种阅读模式回归样例
> 中文、English、Ελληνικά、长链接与窄页面排版检查。

## 中英文长段落

这是用于检查 CJK 严格换行、Latin spacing 和段落孤行控制的长段落。A restrained reading layout should remain calm when English words and 中文标点，出现在同一行中。重要内容只做**局部强调**，不会生成装饰性卡片。

## 参考资料与长链接

1. 带可读标题的链接：[W3C Reflow 指南](https://www.w3.org/WAI/WCAG21/Understanding/reflow)
2. 裸链接：<https://example.com/research/archive/2026/very-long-path-segment-without-natural-breakpoints-and-a-query-string?document=longread&surface=mobile&language=zh-CN>
3. DOI：<https://doi.org/10.1234/example.2026.12345678901234567890>

## 引用与列表

> 好的长文排版应当优先保证阅读连续性。这个引用用于检查平板和手机页面上的边线、内缩与跨页策略。

- 第一项包含普通中文内容。
- 第二项包含 `inline_code_with_a_very_long_unbroken_identifier_that_must_wrap_safely`。
- 第三项包含 [语义化链接](https://example.com/semantic-link)，它不应被套用裸 URL 的小字号。

## 简单表格

| 项目 | Desktop | Tablet | Mobile |
| --- | --- | --- | --- |
| 页面 | A4 | iPad mini 比例 | 9:16 |
| 页眉 | 静态短标题 | 无 | 无 |
| 目标 | 大屏与打印 | 小型平板 | 手机竖屏 |

## 代码块

```text
This_is_a_deliberately_long_line_that_should_wrap_inside_the_code_block_without_crossing_the_page_boundary_1234567890
```
