import asyncio
import logging
from typing import Optional
from mcp.server.fastmcp import FastMCP

# 配置日志记录
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('mcp_server.log')
    ]
)
logger = logging.getLogger(__name__)
logging.getLogger("mcp").setLevel(logging.INFO)

class MusicPlayer:
    def __init__(self):
        self.playlist = asyncio.Queue()  # 全局播放队列
        self.current_task: Optional[asyncio.Task] = None  # 播放任务句柄

    async def initialize(self):
        """初始化播放器"""
        logger.info("MusicPlayer 初始化")
        await asyncio.sleep(1)

    async def add_to_playlist(self,song_url: str) -> str:
        """将音乐添加到播放队列（工具）"""
        logger.info(f"MCP Server 调用 add_to_playlist({song_url})")
        await self.playlist.put(song_url)
        return f"成功添加 {song_url} 到播放列表"
    
    async def start_playback(self) -> str:
        """启动后台播放（工具）"""
        logger.info("MCP Server 调用 start_playback()")
                
        # 防止重复启动
        if self.current_task and not self.current_task.done():
            logger.info("播放已在进行中")
            return "播放已在进行中"

        async def _player_loop(self):
            logger.info("异步播放循环")
            """异步播放循环"""
            while not self.playlist.empty():
                logger.info("播放队列不为空")
                song = await self.playlist.get()
                logger.info(f"开始播放：{song}")
                # 这里添加实际播放逻辑
                await asyncio.sleep(10)  # 模拟播放时长
                self.playlist.task_done()
                logger.info(f"播放完成: {song}")
        
        self.current_task = asyncio.create_task(_player_loop(self))
        return "后台播放已启动"

    async def get_playback_status(self) -> str:
        """获取播放状态（资源）"""
        logger.info("MCP Server 调用 get_playback_status()")
        if self.current_task and not self.current_task.done():
            return "当前播放中"
        return "播放器空闲中"

mcp = FastMCP("MusicPlayer")

class MCP_Server:
    def __init__(self):
        self.music_player = MusicPlayer()
    
    async def initialize(self):
        await self.music_player.initialize()

    def register_tools(self):
        @mcp.tool()
        async def add_to_playlist(song_url: str) -> str:
            return await self.music_player.add_to_playlist(song_url)

        @mcp.tool()
        async def start_playback() -> str:
            return await self.music_player.start_playback()

        @mcp.resource("player://status")
        async def get_playback_status() -> str:
            return await self.music_player.get_playback_status()

async def main():
    return server

if __name__ == "__main__":
    logger.info("--------------------------------\n")
    server = MCP_Server()
    asyncio.run(server.initialize())
    server.register_tools()
    logger.info("mcp.run(transport=\"stdio\")")
    mcp.run(transport="stdio")

"""
> mcp dev test/test.py
Starting MCP inspector...
⚙️ Proxy server listening on port 6277
🔍 MCP Inspector is up and running at http://127.0.0.1:6274 🚀

浏览器中打开 http://127.0.0.1:6274
command中输入：python
arguments中输入：test/test.py
然后点击“connect”
在Tools选项卡中点击List Tools，可以看到"add_to_playlist"和"start_playback"两个工具
    点击"add_to_playlist"，输入参数：xx
    点击"start_playback"，可以看到开始播放
在Resources选项卡中点击List Resources，可以看到"player://status"一个资源
    点击"player://status"，可以看到当前播放状态
"""

"""
2025-04-07 - asyncio - DEBUG - Using selector: EpollSelector
2025-04-07 - __main__ - INFO - --------------------------------

2025-04-07 - __main__ - INFO - main() 运行完成
2025-04-07 - asyncio - DEBUG - Using selector: EpollSelector
2025-04-07 - mcp.server.lowlevel.server - INFO - Processing request of type ListToolsRequest
2025-04-07 - mcp.server.lowlevel.server - INFO - Processing request of type ListResourcesRequest
2025-04-07 - mcp.server.lowlevel.server - INFO - Processing request of type ReadResourceRequest
2025-04-07 - __main__ - INFO - MCP Server 调用 get_playback_status()
2025-04-07 - mcp.server.lowlevel.server - INFO - Processing request of type CallToolRequest
2025-04-07 - __main__ - INFO - MCP Server 调用 add_to_playlist(1)
2025-04-07 - mcp.server.lowlevel.server - INFO - Processing request of type CallToolRequest
2025-04-07 - __main__ - INFO - MCP Server 调用 start_playback()
2025-04-07 - __main__ - INFO - 异步播放循环
2025-04-07 - __main__ - INFO - 播放队列不为空
2025-04-07 - __main__ - INFO - 开始播放：1
2025-04-07 - mcp.server.lowlevel.server - INFO - Processing request of type ReadResourceRequest
2025-04-07 - __main__ - INFO - MCP Server 调用 get_playback_status()
2025-04-07 - __main__ - INFO - 播放完成: 1
"""
