# HeyAR_ChatBot

参考config.yml.copy，在同路径下新建 config.yml，并补充API Key等必要的配置。
```shell
git clone https://github.com/heyangHEY/HeyAR_ChatBot.git
cd HeyAR_ChatBot

conda create --name chatbot python=3.11
conda activate chatbot
pip install -r ./requirements.txt

python -m core.handler --config='./config.yml' # 运行ChatBotService
# 运行日志见：./app.log
```


./core/: ChatBot的核心代码。  
./test/: 提供了几个notebook以供单功能测试和学习。

感谢项目：
1. [xiaozhi-esp32-server](https://github.com/xinnan-tech/xiaozhi-esp32-server)
2. [ai-app-lab](https://github.com/volcengine/ai-app-lab/tree/main)
