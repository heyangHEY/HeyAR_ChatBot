import os
import time
import json
import random
import aiohttp
import asyncio
import logging
import threading
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
from concurrent.futures import ThreadPoolExecutor
from typing import Optional
import aiofiles

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

# 重定向 pygame 的输出,避免在 stdio 中输出信息
import os
os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = "hide"
from pygame import mixer

# 加载环境变量
load_dotenv()
MUSIC_DIR = os.getenv("MUSIC_DIR")
WEATHER_API_KEY = os.getenv("GAODE_API_KEY")
WEATHER_API_BASE_URL = os.getenv("GAODE_API_BASE_URL")

class WeatherService:
    """天气服务类"""
    def __init__(self, api_key):
        self.api_key = api_key
        self.base_url = WEATHER_API_BASE_URL
        self._session: Optional[aiohttp.ClientSession] = None
        self._lock = threading.Lock()
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """获取或创建aiohttp会话"""
        if self._session is None:
            self._session = aiohttp.ClientSession()
        return self._session
    
    async def get_weather(self, city: str, weather_type: str = "base") -> dict:
        """异步获取指定城市的天气信息"""
        try:
            params = {
                "key": self.api_key,
                "city": city,
                "extensions": weather_type,
                "output": "JSON"
            }
            
            session = await self._get_session()
            async with session.get(self.base_url, params=params) as response:
                data = await response.json()
                
                if data["status"] != "1" or data["infocode"] != "10000":
                    return {"status": "error", "message": f"查询失败：{data.get('info', '未知错误')}"}
                
                if weather_type == "base":
                    live = data["lives"][0]
                    return {
                        "status": "success",
                        "message": (
                            f"{live['province']}{live['city']}的实时天气：\n"
                            f"天气状况：{live['weather']}\n"
                            f"温度：{live['temperature']}℃\n"
                            f"湿度：{live['humidity']}%\n"
                            f"风向：{live['winddirection']}\n"
                            f"风力：{live['windpower']}级\n"
                            f"发布时间：{live['reporttime']}"
                        )
                    }
                else:  # weather_type == "all"
                    forecast = data["forecasts"][0]
                    forecast_text = f"{forecast['province']}{forecast['city']}未来天气预报：\n"
                    for cast in forecast["casts"]:
                        forecast_text += (
                            f"\n{cast['date']} (周{cast['week']})：\n"
                            f"白天：{cast['dayweather']}，{cast['daytemp']}℃，"
                            f"{cast['daywind']}风{cast['daypower']}级\n"
                            f"夜间：{cast['nightweather']}，{cast['nighttemp']}℃，"
                            f"{cast['nightwind']}风{cast['nightpower']}级\n"
                        )
                    return {"status": "success", "message": forecast_text}
                
        except Exception as e:
            return {"status": "error", "message": f"获取天气信息失败: {str(e)}"}
    
    async def get_current_weather(self, city):
        """异步获取指定城市的实时天气"""
        logger.info(f"MCP Server 调用 get_current_weather({city})")
        return await self.get_weather(city, "base")
    
    async def get_weather_forecast(self, city):
        """异步获取指定城市的天气预报"""
        logger.info(f"MCP Server 调用 get_weather_forecast({city})")
        return await self.get_weather(city, "all")
    
    async def close(self):
        """关闭aiohttp会话"""
        if self._session is not None:
            await self._session.close()
            self._session = None

class MusicPlayer:
    """音乐播放器类"""
    def __init__(self, music_dir):
        self.music_dir = music_dir
        self.current_music = None
        self.is_playing = False
        self.play_mode = "single"
        self.music_data = {}
        self.playlist = []
        self.current_index = 0
        self.should_continue = True
        self._lock = asyncio.Lock()
        self._play_queue = asyncio.Queue()
        self._worker_task: Optional[asyncio.Task] = None
        
        mixer.init()
    
    async def initialize(self):
        """异步初始化"""
        await self.load_music_data()
        # 启动异步任务
        async def _play_worker(self):
            """异步播放工作器"""
            logger.info("异步播放工作器启动，等待播放任务")
            while self.should_continue:
                try:
                    # 等待播放队列中的任务
                    logger.info("等待播放队列中的任务")
                    song_id = await self._play_queue.get() # 异步阻塞 # 队列内部的任务计数会+1
                    logger.info(f"获取到播放任务: {song_id}")
                    try:
                        await self._play_song(song_id)
                        
                        # 等待当前歌曲播放完成
                        while mixer.music.get_busy() and self.is_playing:
                            await asyncio.sleep(0.1)
                        
                        # 检查是否需要自动播放下一首
                        if self.is_playing and self.play_mode in ["loop", "random"]:
                            next_song = await self._get_next_song()
                            if next_song:
                                await self._play_queue.put(next_song)
                    finally:
                        # 确保任务完成标记在finally块中执行
                        self._play_queue.task_done() # 队列内部的任务计数会-1，join() 会等待所有任务都被处理完（计数器归零）

                except asyncio.CancelledError:
                    logger.info("播放工作器任务被取消")
                    break
                except Exception as e:
                    logger.error(f"播放工作器错误: {str(e)}")
                
                await asyncio.sleep(0.1)
            
            logger.info("异步播放工作器停止")
        self._worker_task = asyncio.create_task(_play_worker(self))

    async def load_music_data(self):
        """异步加载音乐元数据"""
        json_path = os.path.join(self.music_dir, "music_data.json")
        if os.path.exists(json_path):
            async with aiofiles.open(json_path, 'r', encoding='utf-8') as f:
                data = json.loads(await f.read())
                for playlist_name, songs in data.items():
                    for song in songs:
                        self.music_data[song['id']] = song


    async def _play_song(self, song_id: str):
        """异步播放单首歌曲"""
        logger.info(f"开始播放音乐: {song_id}")
        music_path = os.path.join(self.music_dir, f"{song_id}.mp3")
        
        if not os.path.exists(music_path):
            logger.error(f"音乐文件 {song_id}.mp3 不存在")
            return {"status": "error", "message": f"音乐文件 {song_id}.mp3 不存在"}

        try:
            async with self._lock:
                if self.is_playing:
                    mixer.music.stop()
                
                mixer.music.load(music_path)
                mixer.music.play()
                self.current_music = song_id
                self.is_playing = True
                song_info = self.music_data.get(song_id, {"title": song_id})
                return {"status": "success", "message": f"正在播放: {song_info['title']}"}
        except Exception as e:
            logger.error(f"播放音乐失败: {str(e)}")
            return {"status": "error", "message": str(e)}

    async def _get_next_song(self) -> Optional[str]:
        """异步获取下一首要播放的歌曲ID"""
        if not self.playlist:
            return None
        
        if self.play_mode == "random":
            return random.choice(self.playlist)
        else:  # loop mode
            self.current_index = (self.current_index + 1) % len(self.playlist)
            return self.playlist[self.current_index]

    def _find_song_by_title(self, title: str) -> Optional[str]:
        """通过歌曲名查找歌曲ID"""
        for song_id, song_info in self.music_data.items():
            if song_info["title"].lower() == title.lower():
                return song_id
        return None

    def _find_song_by_index(self, index: int) -> Optional[str]:
        """通过索引查找歌曲ID"""
        try:
            index = int(index)
            if index < 1 or index > len(self.music_data):
                return None
            return list(self.music_data.keys())[index - 1]
        except (ValueError, IndexError):
            return None

    async def play_music(self, song_identifier: str = None):
        """异步播放指定的音乐"""
        logger.info(f"MCP Server 调用 play_music({song_identifier})")
        async with self._lock:
            if not self.music_data:
                logger.info("音乐库为空")
                return {"status": "error", "message": "音乐库为空"}
            
            # 确定要播放的歌曲ID
            song_id = None
            if song_identifier is None or song_identifier.lower() == "random":
                all_songs = list(self.music_data.keys())
                if not all_songs:
                    logger.info("音乐库为空")
                    return {"status": "error", "message": "音乐库为空"}
                self.play_mode = "random"
                song_id = random.choice(all_songs)
            elif song_identifier in self.music_data:
                song_id = song_identifier
            else:
                try:
                    index = int(song_identifier)
                    song_id = self._find_song_by_index(index)
                except ValueError:
                    song_id = self._find_song_by_title(song_identifier)
            
            if not song_id:
                logger.info(f"未找到歌曲: {song_identifier}")
                return {"status": "error", "message": f"未找到歌曲: {song_identifier}"}
            
            # 将歌曲添加到播放队列
            self.playlist = [song_id]
            self.current_index = 0
            await self._play_queue.put(song_id)
            logger.info(f"已添加到播放队列: {self.music_data[song_id]['title']}")
            return {"status": "success", "message": f"已添加到播放队列: {self.music_data[song_id]['title']}"}

    async def stop_music(self):
        """异步停止当前播放的音乐"""
        logger.info(f"MCP Server 调用 stop_music()")
        async with self._lock:
            if self.is_playing:
                mixer.music.stop()
                self.is_playing = False
                # 清空播放队列
                while not self._play_queue.empty():
                    try:
                        self._play_queue.get_nowait()
                        self._play_queue.task_done()
                    except asyncio.QueueEmpty:
                        break
                return {"status": "success", "message": "音乐已停止"}
            return {"status": "info", "message": "当前没有正在播放的音乐"}

    def list_music(self):
        """列出音乐目录下的所有可用音乐"""
        logger.info(f"MCP Server 调用 list_music()")
        if not self.music_data:
            return {"status": "error", "message": "没有找到可用的音乐"}
        
        music_list = []
        for i, (song_id, song_info) in enumerate(self.music_data.items(), 1):
            music_list.append({
                "index": i,
                "id": song_id,
                "title": song_info["title"],
                "artist": song_info.get("artist", "未知艺术家"),
                "album": song_info.get("album", "未知专辑")
            })
        
        return {
            "status": "success",
            "message": "获取音乐列表成功",
            "data": music_list
        }

    async def cleanup(self):
        """异步清理资源"""
        self.should_continue = False
        await self.stop_music()

# 创建FastMCP实例
app = FastMCP("MCP_Server")

class MCP_Server:
    """音乐天气服务器类"""
    def __init__(self):
        self.music_player = MusicPlayer(MUSIC_DIR)
        self.weather_service = WeatherService(WEATHER_API_KEY)
        
    async def initialize(self):
        await self.music_player.initialize()

    def register_tools(self):
        """注册所有工具方法"""
        @app.tool()
        async def play_music(song_identifier):
            return await self.music_player.play_music(song_identifier)
        logger.info("play_music 注册完成")
        
        @app.tool()
        async def stop_music():
            return await self.music_player.stop_music()
        logger.info("stop_music 注册完成")
        
        @app.tool()
        def list_music():
            return self.music_player.list_music()
        logger.info("list_music 注册完成")
        
        @app.tool()
        def set_play_mode(mode):
            return self.music_player.set_play_mode(mode)
        logger.info("set_play_mode 注册完成")
        
        @app.tool()
        def get_current_playing():
            return self.music_player.get_current_playing()
        logger.info("get_current_playing 注册完成")
        
        # 天气相关工具
        @app.tool()
        async def get_current_weather(city):
            return await self.weather_service.get_current_weather(city)
        logger.info("get_current_weather 注册完成")
        
        @app.tool()
        async def get_weather_forecast(city):
            return await self.weather_service.get_weather_forecast(city)
        logger.info("get_weather_forecast 注册完成")

    async def cleanup_async(self):
        """异步清理资源"""
        if self.music_player._worker_task:
            self.music_player.should_continue = False
            # 等待工作器正常退出
            try:
                await asyncio.wait_for(self.music_player._worker_task, timeout=1.0)
            except asyncio.TimeoutError:
                # 如果等待超时，则取消任务
                self.music_player._worker_task.cancel()
                try:
                    await self.music_player._worker_task
                except asyncio.CancelledError:
                    pass
        await self.music_player.stop_music()
        await self.weather_service.close()

if __name__ == "__main__":
    logger.info("--------------------------------\n")
    server = MCP_Server()
    asyncio.run(server.initialize())
    server.register_tools()
    app.run(transport="stdio")
    asyncio.run(server.cleanup_async())
