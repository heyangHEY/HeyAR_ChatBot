# HeyAR_ChatBot

目标：实现低延迟、高拟人化的实时语音交互，支持自然对话打断。

### Pipeline：
1. 语音采集  
   - 25ms 音频分帧：麦克风实时采集语音，每 25ms 生成片段，平衡延迟与数据连贯性
   - VAD 语音活动检测：动态识别有效人声（静默片段自动丢弃，减少无效计算）
2. 交互触发
   - 300ms 静默判定：用户停顿时长超过阈值后，自动触发后续处理流程
3. 语音识别（ASR）
   - 云端 / 本地引擎将语音流转换为文本，支持中英文混合识别
4. 智能回复生成（LLM）
   - 流式响应：大模型实时生成文本片段（非完整回复），降低首字延迟
   - 多轮对话管理：结合历史上下文生成符合场景的回复
   - 支持调用外部工具：通过 Function Call / MCP
5. 语音合成（TTS）
   - 双向流式合成：
     - 输入侧：LLM 生成首个文本 token 后立即触发 TTS
     - 输出侧：合成语音分块流式传输至扬声器
   - 拟人化引擎：采用豆包语音大模型，支持音色语调调节，逼近真人对话体验
6. 音频播放
   - 扬声器实时输出合成语音，支持 24kHz 音质


### Tips：
1. 确保麦克风设备支持“硬件级回声消除”：消除设备自播放语音的干扰，确保用户随时插话可被精准识别。
   - [x] 蓝牙耳机，config.yml/AUDIO/General/echo_cancel: True
   - [x] 会议麦克风（带扬声器）
   - 支持回声消除的硬件，请设置 config.yml/AUDIO/General/echo_cancel: True
   - 普通带麦扬声器，则只能设置为 False
   - config.yml/base/enable_natural_break: True 则启用“对话自然打断”（仅硬件支持回声消除时有效）
2. 火山引擎中，语音合成大模型 TTS，只面向通过企业认证的用户。备选方案是注册机智云账号，无需企业认证，也能用上火山引擎同款 TTS；
3. 对工具的支持：若 LLM 支持 Function Call，则对话助手支持查询天气、播放音乐等，且支持单轮对话中包含多个FC。
4. 通过 config.yml 进行模块的配置和调整 pipeline；
5. 支持 LLM 调用外部工具：
   - [x] 通过 Function Call 调用外部工具
   - [x] 通过 MCP 调用外部工具


### 组件支持
1. VAD 模块
   - [x] WebRTC VAD
   - [x] SileroVAD
2. ASR 模块
   - [x] FunASR，SenseVoice
3. LLM 模块
   - [x] OpenAI LLM
   - [x] Ollama：Qwen2.5
4. TOOL 工具
   - [x] Function Call
     - [x] 高德 天气查询服务，可查当天、未来三天
     - [ ] 本地音乐播放
   - [x] MCP
     - [x] 高德地图MCP服务
     - [ ] playwright
     - [ ] filesystem
     - [ ] Apple Music
5. TTS 模块
   - [x] 豆包语音合成大模型 TTS
   - [x] 机智云

### 项目配置
参考config.yml.copy，在同路径下新建 config.yml，并补充API Key等必要的配置。
```shell
git clone https://github.com/heyangHEY/HeyAR_ChatBot.git
cd HeyAR_ChatBot

conda create --name chatbot python=3.10
conda activate chatbot
pip install -r ./requirements.txt

# 下载ASR：SenseVoiceSmall模型到本地
cd ./models
mkdir SenseVoiceSmall
git clone https://huggingface.co/FunAudioLLM/SenseVoiceSmall
# config.yml中FunASR/model_dir设置为models/SenseVoiceSmall

# 下载 silero-vad 模型到本地
cd ./models
# git clone --branch v5.1.2 https://github.com/snakers4/silero-vad.git
wget --https-only https://github.com/snakers4/silero-vad/archive/refs/tags/v5.1.2.zip
unzip -d ./ v5.1.2.zip
# config.yml 中 SileroVAD/model_dir 设置为 models/silero-vad-5.1.2

# 开启ollama服务，下载 qwen2.5 的模型文件

# 运行ChatBotService，运行日志见：./app.log
python -m core.handler --config='./config.yml'

# 其他测试项：
# 测试音频模块，录音5s后播放，运行日志见：./app.log
python -m core.test.test_audio_handler --config='./config.yml'
# 测试豆包大语言合成模型-双向流式API，合成结果：./tmp/tts/test.mp3 和 ./tmp/tts/test_stream.mp3
python -m core.test.test_doubao_tts_client
# 测试豆包大语言合成模型-双向流式API，以及流式播放
python -m core.test.test_doubao_tts_client_and_play
```

./core/: ChatBot的核心代码；  
./test/: 提供了几个notebook以供单功能测试和学习；  
./models/: 存储模型文件；  
./tmp/: 存储对话过程中产生的临时文件，比如麦克风捕获的录音、tts合成的音频等；  

### TODO
详见 [TODO](TODO.md)

感谢以下项目：
1. [xiaozhi-esp32-server](https://github.com/xinnan-tech/xiaozhi-esp32-server)
2. [ai-app-lab](https://github.com/volcengine/ai-app-lab/tree/main)

## 许可证

本项目采用 [MIT](LICENSE) 开源许可证 - 查看 [LICENSE](LICENSE) 文件了解更多细节。
