# HeyAR_ChatBot

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

感谢以下项目：
1. [xiaozhi-esp32-server](https://github.com/xinnan-tech/xiaozhi-esp32-server)
2. [ai-app-lab](https://github.com/volcengine/ai-app-lab/tree/main)

## 许可证

本项目采用 [MIT](LICENSE) 开源许可证 - 查看 [LICENSE](LICENSE) 文件了解更多细节。
