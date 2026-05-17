---
name: agent-skills-test
description: 当用户说"测试 Agent Skills 系统"时使用此技能，通过 read_file 工具读取系统文件，验证系统完整性。
---

# Agent Skills 完整性测试

## 概述
使用 `read_file` 读取系统关键文件，验证 Agent Skills 系统是否正常工作。

## 触发条件
用户说"测试 Agent Skills 系统"。

## 工作流程
1. 用 `read_file` 读取 `skills/skills.py`，确认 `SkillsLoader` 类存在
2. 用 `read_file` 读取 `skills/agent-loop.py`，确认 `agent_loop` 函数存在
3. 输出验证报告

## 规范和约束
- 只允许使用 `read_file` 工具

## 示例
**输入：** "测试 Agent Skills 系统"
**输出：**
`
✅ skills.py      — SkillsLoader 存在
✅ agent-loop.py  — agent_loop 存在
结论：系统完整，全程仅用 read_file 工具。
`