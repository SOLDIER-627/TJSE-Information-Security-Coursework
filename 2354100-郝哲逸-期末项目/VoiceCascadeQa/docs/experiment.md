# 可复现实验步骤

## 环境要求

- Python 3.10+（推荐 3.11）
- NVIDIA GPU（VRAM ≥ 4GB，推荐 ≥ 8GB）；CPU 亦可运行，延迟增加
- 网络连接（用于 LLM API 调用和模型下载）

## 步骤1：环境安装

```bash
# 创建 conda 环境
conda create -n voice python=3.11 -y
conda activate voice

# 安装 PyTorch（CPU 版；GPU 用户去掉 --index-url）
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install torchaudio --index-url https://download.pytorch.org/whl/cpu

# 安装项目依赖
pip install -r requirements.txt
```

## 步骤2：配置 API

编辑项目根目录的 `.env` 文件（已被 `.gitignore` 忽略）：

```env
LLM_API_BASE=https://your-api-endpoint.com/v1
LLM_API_KEY=sk-your-api-key
LLM_MODEL=your-model-name
```

> 不要将密钥写入 `config/default.yaml`，该文件会被提交到版本库。

## 步骤3：准备测试音频集

```bash
python scripts/prepare_test_audio.py
```

此脚本使用 edge-tts 生成 45 条固定测试音频，覆盖简单中文、英文、中英混合、造船术语、工艺流程、安全相关、长句复杂、数字编号、对抗/恶意与无关输入，保存在 `data/audio_test_set/`。

测试音频为 TTS 合成语音，用于保证评测输入可重复；真实麦克风噪声、口音和环境干扰不在该固定集内，属于后续扩展测试范围。

## 步骤4：运行基线评测

```bash
python scripts/run_baseline.py
```

每条测试音频运行 3 次，记录延迟数据，结果保存在 `data/results/baseline_results.csv`。

后台运行（推荐，评测耗时较长）：

Linux / Git Bash / WSL：

```bash
mkdir -p logs
nohup python scripts/run_baseline.py > logs/baseline.log 2>&1 &
```

Windows PowerShell：

```powershell
New-Item -ItemType Directory -Force logs
python scripts/run_baseline.py *>&1 | Tee-Object logs/baseline.log
```

> 注：Tee-Object 方式关闭 PowerShell 窗口后进程会停止。如需真正后台运行，建议在 Git Bash / WSL 中使用 nohup。

查看实时日志：

```bash
tail -f logs/baseline.log
```

## 步骤5：运行改进评测

```bash
python scripts/run_improved.py
```

同样每条运行 3 次，结果保存在 `data/results/improved_results.csv`。

后台运行：

Linux / Git Bash / WSL：

```bash
nohup python scripts/run_improved.py > logs/improved.log 2>&1 &
```

Windows PowerShell：

```powershell
python scripts/run_improved.py *>&1 | Tee-Object logs/improved.log
```

## 步骤6：生成对比表

```bash
python scripts/compare_results.py
```

输出基线 vs 改进的延迟对比表，保存在 `data/results/comparison.csv` 和 `data/results/comparison_by_category.csv`。

## 步骤7：交互式测试

```bash
# 基线模式
python -m src.main interactive --pipeline baseline

# 改进模式
python -m src.main interactive --pipeline improved

# 单次文本查询
python -m src.main baseline --text "什么是龙骨？"
python -m src.main improved --text "什么是龙骨？"

# 单次音频文件查询
python -m src.main baseline --audio data/audio_test_set/zh_simple_1.wav
python -m src.main improved --audio data/audio_test_set/zh_simple_1.wav
```

## 步骤8：运行单元测试

```bash
# 运行所有非 API 依赖测试
python -m pytest tests/ -v

# 运行单个测试
python tests/test_safety.py
python tests/test_timer.py
python tests/test_text_splitter.py
python tests/test_config.py

# 运行包含 API 调用的集成测试
RUN_API_TESTS=1 python -m pytest tests/ -v
```

## 断点续跑

评测脚本支持断点续跑。脚本启动时会读取已有 CSV 结果，统计每个 test_id 已完成的 run 数量：

- 若某 test_id 已完成 `runs_per_audio` 次 → 自动跳过，打印 `[SKIP]`
- 若某 test_id 只完成部分 → 从未完成的 run 继续，打印 `[RESUME]`
- 若某 test_id 无记录 → 从 run 1 开始

每完成一次 run 立即 append 到 CSV 并 flush，即使中途 Ctrl+C 或 API 报错，已完成的记录不会丢失。

如需完全重新评测，删除对应 CSV 即可：

```bash
rm data/results/baseline_results.csv    # 重新跑基线
rm data/results/improved_results.csv    # 重新跑改进
```

## 评测指标说明

| 检查点 | 含义 |
|--------|------|
| t_user_silent | 用户停止说话（VAD 端点） |
| t_asr_complete | ASR 转写完成 |
| t_safety_check | 安全检查完成 |
| t_llm_first_sentence | LLM 流式输出首句完成 |
| t_tts_first_chunk | TTS 首个音频块产出 |
| t_first_playable | 首段音频可播放（音频数据就绪） |
| t_first_content | 首段正文音频就绪（仅改进版） |

**首段可播放延迟 = t_first_playable - t_user_silent**

每条评测记录包含以下延迟指标：

| CSV 字段 | 含义 |
|----------|------|
| latency_asr_latency | ASR 转写延迟 |
| latency_safety_latency | 安全检查延迟 |
| latency_llm_first_sentence | LLM 首句延迟 |
| latency_tts_first_chunk | TTS 首块延迟 |
| latency_first_playable | 首段可播放延迟 |
| latency_first_content | 正文首段延迟（仅改进版） |
| latency_total_response | 总响应时间 |
| latency_wall_total | 完整运行 wall clock 耗时 |

注：`t_first_playable` 表示音频数据已合成完成、可立即播放的时间点。改进版中含衔接语时，t_first_playable 为衔接语入队时刻；t_first_content 为正文首段就绪时刻。实际播放时间取决于播放器状态和系统音频延迟。

## TTS 引擎配置

默认使用 Kokoro-82M 本地 TTS 引擎（`tts.engine: kokoro`）。

### Kokoro-82M（默认）

- 模型大小：~320MB
- 首次运行自动从 HuggingFace 下载（使用 hf-mirror.com 镜像）
- 支持 CPU 和 GPU 推理
- 原生支持流式合成（改进流水线使用此模式）
- 中文语音：`zf_xiaobei`（默认）

### CosyVoice-300M（备选）

需额外配置 `tts.model_dir`：

```yaml
tts:
  engine: "cosyvoice"
  model_dir: "/path/to/cosyvoice-model"
  speaker_id: "中文女"
```

### edge-tts（Fallback）

当本地模型不可用时自动回退，需网络连接，不支持流式合成。

## SafetyGate 说明

SafetyGate 仅做 SAFE/UNSAFE 两种判断：

- **UNSAFE**：检测到暴力、自伤、违法、prompt injection 等关键词 → 短路返回安全提示，不调用 LLM
- **SAFE**：放行到 LLM

领域相关性（IRRELEVANT）判断已移除。ASR 误识别会导致合法造船术语无法匹配领域词库，产生大量误拦截。现由 LLM system prompt 第 6 条规则处理领域相关性，LLM 能根据造船语境推断 ASR 同音误识别的正确含义。

可通过 `safety.enabled: false` 关闭安全门控。

## 注意事项

1. 首次运行会自动下载 ASR 模型（~1GB）和 Kokoro TTS 模型（~320MB），请确保网络畅通
2. LLM API 延迟受网络影响，评测取 3 次均值以减少波动
3. GPU 显存不足时，可将 `device` 设为 `cpu`（速度较慢）
4. 后台运行时日志保存在 `logs/` 目录，可用 `tail -f` 实时查看
5. 改进流水线的 `wall_total` 可能比基线更长（流式 TTS 逐句合成增加总耗时），但 `first_playable` 显著更低——这是设计预期
