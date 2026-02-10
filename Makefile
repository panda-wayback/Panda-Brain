.PHONY: run install test clean

# 启动 CLI 交互
run:
	uv run panda-brain

# 安装依赖
install:
	uv sync

# 快速测试（验证 agent 导入和基本对话）
test:
	uv run python -c "from panda_brain.orchestrator import orchestrator; r = orchestrator.run_sync('你好，一句话介绍自己'); print(r.output)"

# 清理缓存
clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null; true
	rm -rf .venv dist *.egg-info
