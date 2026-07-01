# VoiceCascadeQa — 级联式造船语音问答系统

面向造船领域的级联式语音问答系统，支持基线串行和流式并行两种流水线模式。核心评估指标为**首段可播放延迟**（从用户停止说话到首段音频可播放的时间），改进流水线将感知延迟降低约 **2.88 倍**（34,965ms → 12,151ms）。

## 架构

```text
ASR (语音识别) → SafetyGate (安全门控) → LLM (大语言模型) → TTS (语音合成) → 播放
```

- **基线**：各阶段严格串行，LLM 完整生成后再 TTS 合成，first_playable ≈ 35s
- **改进**：流式 ASR / 流式 LLM / 逐句 TTS / 衔接语 / 热词修正，first_playable ≈ 12s

四项改进：
1. **流式并行**：LLM 流式输出首句即触发 TTS，用户无需等待完整回答
2. **衔接语调度**：预合成短语音填补等待空白，降低主观感知延迟
3. **造船热词纠错 + TTS 发音归一化**：降低"听错—答偏—念怪"的级联误差
4. **安全门控短路**：UNSAFE 输入跳过 LLM，直接返回安全提示

## 组件

| 组件 | 基线 | 改进 |
|------|------|------|
| ASR | SenseVoiceSmall + fsmn-vad | paraformer-zh-streaming + SenseVoiceSmall fallback |
| SafetyGate | SAFE / UNSAFE | 同左 |
| LLM | OpenAI 兼容 API（非流式） | 同左 + SSE 流式输出 |
| TTS | Kokoro-82M（全量合成） | Kokoro-82M（流式逐句合成） |
| 热词修正 | — | 81 个造船术语，edit-distance 纠错 |
| 衔接语 | — | 预合成填充音频，零运行时延迟 |

## 快速开始

```bash
# 创建环境并安装依赖
conda create -n voice python=3.11 -y && conda activate voice
pip install torch torchaudio --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements.txt

# 配置 API 密钥（写入 .env，已被 .gitignore 忽略）
echo 'LLM_API_BASE=https://your-endpoint/v1' >> .env
echo 'LLM_API_KEY=sk-your-key' >> .env
echo 'LLM_MODEL=your-model' >> .env

# 交互式测试（麦克风录音）
python -m src.main interactive --pipeline baseline
python -m src.main interactive --pipeline improved

# 单次文本/音频查询
python -m src.main improved --text "什么是龙骨？"
python -m src.main baseline --audio data/audio_test_set/zh_simple_1.wav

# 运行评测
python scripts/prepare_test_audio.py    # 生成固定音频集
python scripts/run_baseline.py          # 基线评测（135 次运行）
python scripts/run_improved.py          # 改进评测（135 次运行）
python scripts/compare_results.py       # 生成对比表

# 单元测试
python -m pytest tests/ -v
```

## SafetyGate

仅做 SAFE / UNSAFE 两种判断：
- **UNSAFE**：检测到危险关键词 → 短路返回安全提示（不调用 LLM，节省 ~30s）
- **SAFE**：放行到 LLM

领域相关性不再由 SafetyGate 判断（原 IRRELEVANT 已移除），改由 LLM system prompt 处理。ASR 误识别（如"手楼"→"艏楼"、"仓壁"→"舱壁"）会导致关键词匹配失败产生误拦截，LLM 能根据造船语境推断正确含义。

## 实验结果

| 指标 | 基线 (mean±std) | 改进 (mean±std) | 加速比 |
|------|-----------------|-----------------|--------|
| **first_playable** | 34,965 ± 18,630ms | 12,151 ± 6,771ms | **2.88x** |
| llm_first_sentence | 29,619 ± 17,628ms | 8,922 ± 6,746ms | **3.32x** |
| tts_first_chunk | 5,124 ± 1,762ms | 2,432 ± 689ms | **2.11x** |

详细结果见 [实验报告](docs/report.md)。

## 文档

- [实验报告](docs/report.md) — 系统架构、改进点说明、评测结果与结论
- [实验步骤](docs/experiment.md) — 可复现评测步骤

## 项目结构

```text
VoiceCascadeQa/
├── config/
│   ├── default.yaml               # 主配置
│   ├── hotwords_shipbuilding.txt  # 热词列表（81 个造船术语）
│   └── safety_keywords.txt        # 安全关键词
├── data/
│   ├── audio_test_set/            # 测试音频（45 条 × 3 次运行）
│   └── results/                   # 评测结果 CSV
├── docs/
│   ├── report.md                  # 实验报告
│   └── experiment.md              # 实验步骤
├── logs/                          # 运行日志
├── scripts/
│   ├── prepare_test_audio.py      # 生成固定音频集
│   ├── run_baseline.py            # 基线评测
│   ├── run_improved.py            # 改进评测
│   └── compare_results.py         # 生成对比表
├── src/
│   ├── asr/                       # ASR 模块（BaseASR / SenseVoiceASR / StreamingASR）
│   ├── audio/                     # 录音/播放
│   ├── llm/                       # LLM 模块（BaseLLM / OpenAILLM）
│   ├── pipeline/                  # 流水线（BaselinePipeline / ImprovedPipeline）
│   ├── safety/                    # 安全门控（SafetyGate）
│   ├── scheduling/                # 衔接语（TransitionPhrases）
│   ├── tts/                       # TTS 模块（BaseTTS / KokoroTTS / CosyVoiceTTS）
│   └── utils/                     # 工具（Timer / ConfigLoader）
└── tests/
```
