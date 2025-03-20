import os
import json
import uuid
import asyncio
import logging
import aiofiles
import websockets
from typing import Optional, Dict, Any, AsyncGenerator

from core.component.tts.base import AsyncBaseTTSClient

logger = logging.getLogger(__name__)

# 协议版本和头部大小常量
PROTOCOL_VERSION = 0b0001       # 协议版本号
DEFAULT_HEADER_SIZE = 0b0001    # 默认头部大小

# 消息类型常量
FULL_CLIENT_REQUEST = 0b0001    # 客户端完整请求
AUDIO_ONLY_RESPONSE = 0b1011    # 仅音频响应
FULL_SERVER_RESPONSE = 0b1001   # 服务器完整响应
ERROR_INFORMATION = 0b1111      # 错误信息

# 消息类型特定标志
MsgTypeFlagNoSeq = 0b0000       # 无序列号的非终止包
MsgTypeFlagPositiveSeq = 0b1    # 序列号大于0的非终止包
MsgTypeFlagLastNoSeq = 0b10     # 无序列号的最后一个包
MsgTypeFlagNegativeSeq = 0b11   # 包含事件编号的负序列号
MsgTypeFlagWithEvent = 0b100    # 包含事件

# 消息序列化方式
NO_SERIALIZATION = 0b0000       # 无序列化
JSON = 0b0001                   # JSON序列化

# 消息压缩方式
COMPRESSION_NO = 0b0000         # 无压缩
COMPRESSION_GZIP = 0b0001       # GZIP压缩

# 事件类型常量
# 基础事件
EVENT_NONE = 0                  # 无事件
EVENT_Start_Connection = 1      # 开始连接
EVENT_FinishConnection = 2      # 结束连接
EVENT_ConnectionStarted = 50    # 连接成功建立
EVENT_ConnectionFailed = 51     # 连接失败（如权限认证失败）
EVENT_ConnectionFinished = 52   # 连接结束

# 会话事件（上行）
EVENT_StartSession = 100        # 开始会话
EVENT_FinishSession = 102       # 结束会话

# 会话事件（下行）
EVENT_SessionStarted = 150      # 会话开始
EVENT_SessionFinished = 152     # 会话结束
EVENT_SessionFailed = 153       # 会话失败

# 任务事件（上行）
EVENT_TaskRequest = 200         # 任务请求

# TTS特定事件（下行）
EVENT_TTSSentenceStart = 350    # 句子开始
EVENT_TTSSentenceEnd = 351      # 句子结束
EVENT_TTSResponse = 352         # TTS响应

class Header:
    """消息头部类"""
    def __init__(self,
                 message_type: int = 0,
                 message_type_specific_flags: int = 0,
                 serial_method: int = NO_SERIALIZATION):
        self.protocol_version = PROTOCOL_VERSION
        self.header_size = DEFAULT_HEADER_SIZE
        self.message_type = message_type
        self.message_type_specific_flags = message_type_specific_flags
        self.serial_method = serial_method
        self.compression_type = 0
        self.reserved_data = 0

    def as_bytes(self) -> bytes:
        return bytes([
            (self.protocol_version << 4) | self.header_size,
            (self.message_type << 4) | self.message_type_specific_flags,
            (self.serial_method << 4) | self.compression_type,
            self.reserved_data
        ])

class Optional:
    """可选信息类"""
    def __init__(self, event: int = EVENT_NONE, session_id: str = None):
        self.event = event
        self.session_id = session_id
        self.error_code: int = 0
        self.connection_id: str | None = None
        self.response_meta_json: str | None = None

    def as_bytes(self) -> bytes:
        option_bytes = bytearray()
        if self.event != EVENT_NONE:
            option_bytes.extend(self.event.to_bytes(4, "big", signed=True))
        if self.session_id is not None:
            session_id_bytes = str.encode(self.session_id)
            size = len(session_id_bytes).to_bytes(4, "big", signed=True)
            option_bytes.extend(size)
            option_bytes.extend(session_id_bytes)
        return option_bytes

class Response:
    """响应类"""
    def __init__(self, header: Header, optional: Optional):
        self.header = header
        self.optional = optional
        self.payload: bytes | None = None

class AsyncDouBaoTTSClient(AsyncBaseTTSClient):
    """豆包TTS客户端实现"""
    
    def __init__(self, config: Dict[str, Any]):
        """
        初始化豆包TTS客户端
        Args:
            config: 配置信息，包含appId、token等
        """
        self.app_id = config.get('app_id', '')
        self.token = config.get('access_token', '')

        self.url = config.get('base_url', 'wss://openspeech.bytedance.com/api/v3/tts/bidirection')
        self.speaker = config.get('speaker', 'zh_female_wanwanxiaohe_moon_bigtts')
        self.audio_format = config.get('audio_format', 'pcm')
        self.audio_sample_rate = config.get('audio_sample_rate', 24000)
        self.speech_rate = config.get('speech_rate', 0)
        
        self.ws = None
        self._initialized = False
        
    async def init(self):
        """异步初始化，建立WebSocket连接"""
        if self._initialized:
            return
            
        await self._connect()
        self._initialized = True
        
    async def close(self):
        """关闭连接并清理资源"""
        if self._initialized:
            await self._finish_connection()
            self._initialized = False

    async def _connect(self) -> None:
        """建立WebSocket连接"""
        if self.ws:
            return
            
        ws_header = {
            "X-Api-App-Key": self.app_id,
            "X-Api-Access-Key": self.token,
            "X-Api-Resource-Id": 'volc.service_type.10029',
            "X-Api-Connect-Id": str(uuid.uuid4()),
        }
        
        self.ws = await websockets.connect(
            self.url, 
            additional_headers=ws_header,
            max_size=1000000000
        )
        
        # 建立连接
        await self._start_connection()
        res = await self._parse_response()
        if res.optional.event != EVENT_ConnectionStarted:
            raise RuntimeError("Failed to establish connection")
        logger.debug("WebSocket connection established")

    async def _start_connection(self):
        """启动连接"""
        header = Header(
            message_type=FULL_CLIENT_REQUEST,
            message_type_specific_flags=MsgTypeFlagWithEvent
        ).as_bytes()
        optional = Optional(event=EVENT_Start_Connection).as_bytes()
        payload = str.encode("{}")
        await self._send_event(header, optional, payload)

    async def _start_session(self, session_id: str):
        """启动会话"""
        header = Header(
            message_type=FULL_CLIENT_REQUEST,
            message_type_specific_flags=MsgTypeFlagWithEvent,
            serial_method=JSON
        ).as_bytes()
        optional = Optional(event=EVENT_StartSession, session_id=session_id).as_bytes()
        payload = self._get_payload(event=EVENT_StartSession)
        await self._send_event(header, optional, payload)

    async def _send_text(self, text: str, session_id: str):
        """发送文本"""
        header = Header(
            message_type=FULL_CLIENT_REQUEST,
            message_type_specific_flags=MsgTypeFlagWithEvent,
            serial_method=JSON
        ).as_bytes()
        optional = Optional(event=EVENT_TaskRequest, session_id=session_id).as_bytes()
        payload = self._get_payload(event=EVENT_TaskRequest, text=text)
        await self._send_event(header, optional, payload)

    async def _finish_session(self, session_id: str):
        """结束会话"""
        header = Header(
            message_type=FULL_CLIENT_REQUEST,
            message_type_specific_flags=MsgTypeFlagWithEvent,
            serial_method=JSON
        ).as_bytes()
        optional = Optional(event=EVENT_FinishSession, session_id=session_id).as_bytes()
        payload = str.encode('{}')
        await self._send_event(header, optional, payload)

    async def _finish_connection(self):
        """结束连接"""
        if not self.ws:
            return
            
        header = Header(
            message_type=FULL_CLIENT_REQUEST,
            message_type_specific_flags=MsgTypeFlagWithEvent,
            serial_method=JSON
        ).as_bytes()
        optional = Optional(event=EVENT_FinishConnection).as_bytes()
        payload = str.encode('{}')
        await self._send_event(header, optional, payload)
        await self.ws.close()
        self.ws = None
        logger.debug("WebSocket connection closed")

    async def _send_event(self, header: bytes, optional: bytes, payload: bytes):
        """发送事件"""
        if not self.ws:
            raise RuntimeError("WebSocket connection not established")
            
        request = bytearray(header)
        request.extend(optional)
        if payload:
            payload_size = len(payload).to_bytes(4, 'big', signed=True)
            request.extend(payload_size)
            request.extend(payload)
        await self.ws.send(request)

    def _get_payload(self, event=EVENT_NONE, text='') -> bytes:
        """生成负载数据"""
        return str.encode(json.dumps({
            "user": {"uid": str(uuid.uuid4())},
            "event": event,
            "namespace": "BidirectionalTTS",
            "req_params": {
                "text": text,
                "speaker": self.speaker,
                "audio_params": {
                    "format": self.audio_format,
                    "sample_rate": self.audio_sample_rate,
                    "speech_rate": self.speech_rate
                }
            }
        }))

    async def _parse_response(self) -> Response:
        """解析响应"""
        if not self.ws:
            raise RuntimeError("WebSocket connection not established")
        
        res = await self.ws.recv()

        if isinstance(res, str):
            raise RuntimeError(res)
            
        response = Response(Header(), Optional())
        header = response.header
        
        # 解析头部
        num = 0b00001111
        header.protocol_version = res[0] >> 4 & num
        header.header_size = res[0] & 0x0f
        header.message_type = (res[1] >> 4) & num
        header.message_type_specific_flags = res[1] & 0x0f
        header.serial_method = res[2] >> num
        header.compression_type = res[2] & 0x0f
        header.reserved_data = res[3]
        
        # 解析可选信息和负载
        offset = 4
        optional = response.optional
        if header.message_type in [FULL_SERVER_RESPONSE, AUDIO_ONLY_RESPONSE]:
            if header.message_type_specific_flags == MsgTypeFlagWithEvent:
                optional.event = int.from_bytes(res[offset:offset+4], 'big')
                offset += 4
                if optional.event != EVENT_NONE:
                    if optional.event == EVENT_ConnectionStarted:
                        optional.connection_id, offset = self._read_content(res, offset)
                    elif optional.event == EVENT_ConnectionFailed:
                        optional.response_meta_json, offset = self._read_content(res, offset)
                    elif optional.event in [EVENT_SessionStarted, EVENT_SessionFailed]:
                        optional.session_id, offset = self._read_content(res, offset)
                        optional.response_meta_json, offset = self._read_content(res, offset)
                    else:
                        optional.session_id, offset = self._read_content(res, offset)
                        response.payload, offset = self._read_payload(res, offset)
        elif header.message_type == ERROR_INFORMATION:
            optional.error_code = int.from_bytes(res[offset:offset+4], "big", signed=True)
            offset += 4
            response.payload, offset = self._read_payload(res, offset)
            
        return response

    def _read_content(self, res: bytes, offset: int):
        """读取内容"""
        content_size = int.from_bytes(res[offset:offset+4], 'big')
        offset += 4
        content = res[offset:offset+content_size].decode()
        offset += content_size
        return content, offset

    def _read_payload(self, res: bytes, offset: int):
        """读取负载"""
        payload_size = int.from_bytes(res[offset:offset+4], 'big')
        offset += 4
        payload = res[offset:offset+payload_size]
        offset += payload_size
        return payload, offset

    async def tts_to_file(self, text: str, output_path: str) -> None:
        """
        将文本转换为语音并保存到文件
        Args:
            text: 要转换的文本
            output_path: 输出音频文件路径
        """
        try:
            # 确保已初始化
            await self.init()
            
            # 确保输出目录存在
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            # 开始会话
            session_id = str(uuid.uuid4()).replace('-', '')
            await self._start_session(session_id)
            res = await self._parse_response()
            if res.optional.event != EVENT_SessionStarted:
                raise RuntimeError("Failed to start session")
                
            # 发送文本
            await self._send_text(text, session_id)
            await self._finish_session(session_id)
            
            # 接收并保存音频
            async with aiofiles.open(output_path, mode="wb") as f:
                while True:
                    res = await self._parse_response()
                    if res.optional.event == EVENT_TTSResponse and res.header.message_type == AUDIO_ONLY_RESPONSE:
                        await f.write(res.payload)
                    elif res.optional.event in [EVENT_TTSSentenceStart, EVENT_TTSSentenceEnd]:
                        continue
                    else:
                        break
                        
            logger.info(f"Audio saved to {output_path}")
            
        except Exception as e:
            logger.error(f"TTS failed: {str(e)}")
            raise

    async def astream_tts(self, text_stream: AsyncGenerator[str, None]) -> AsyncGenerator[bytes, None]:
        """
        将文本流转换为语音流
        Args:
            text_stream: 要转换的文本流
        Returns:    
            AsyncGenerator[bytes, None]: 语音流
        """
        try:
            send_text_task = None
            
            # 确保已初始化
            await self.init()
            
            # 开始会话
            session_id = str(uuid.uuid4()).replace('-', '')
            await self._start_session(session_id)
            res = await self._parse_response()
            if res.optional.event != EVENT_SessionStarted:
                # ! 不能直接抛出异常。
                # raise RuntimeError("Failed to start session")
                """
                解释：
                打断，指AI回复的过程中，被用户打断。

                无打断事件发生的情况下:
                1. 先发送EVENT_StartSession，然后等待EVENT_SessionStarted。
                2. 流式的将llm生成的text token发送给tts。
                3. 流式的从tts接收audio chunk。并yield给上层。
                4. llm生成结束后，发送EVENT_FinishSession。
                   tts会在处理完所有请求（返回所有audio chunk）后，发送EVENT_SessionFinished。

                有打断事件发生的情况下:
                ...
                4. 发生打断事件，立即终止发送剩余的text token，并发送EVENT_FinishSession。
                   但服务器会在处理完历史请求后，才返回EVENT_SessionFinished。
                
                考虑一种情形：某次llm的回复非常长，在流式请求tts的过程中，被用户打断。
                直到再一次进入astream_tts()中，打算发送新的EVENT_StartSession时，tts服务器依然没处理完上一次的请求。
                此时等来的就不是EVENT_SessionStarted，而是EVENT_TTSResponse。
                为此必须一直等，直到EVENT_SessionStarted的到来。
                """
                # 等待EVENT_SessionStarted的到来，最多等待3秒
                start_time = asyncio.get_event_loop().time()
                while True:
                    # if asyncio.get_event_loop().time() - start_time > 3:
                    #     raise asyncio.TimeoutError("等待会话开始超时")
                    res = await self._parse_response()
                    if res.optional.event == EVENT_SessionStarted:
                        break
                    elif res.optional.event == EVENT_SessionFailed:
                        logger.error(f"会话启动失败: {res.optional.event}")
                        raise RuntimeError("会话启动失败")
                    await asyncio.sleep(0.1)
                
            # 给tts发送text token
            async def async_send_text_task(text_stream: AsyncGenerator[str, None], session_id: str):
                try:
                    async for text in text_stream:
                        if not text.strip():
                            continue
                        # 发送文本
                        await self._send_text(text, session_id)
                except Exception as e:
                    logger.error(f"发送文本失败: {str(e)}")
                    raise
                finally:
                    # 结束会话并等待确认，即使任务被取消也会执行
                    await self._finish_session(session_id)

            # 创建异步任务，允许被用户打断
            send_text_task = asyncio.create_task(async_send_text_task(text_stream, session_id), name='send_text_task')
            
            # 接收tts返回的audio chunk
            while True:
                res = await self._parse_response()
                if res.optional.event == EVENT_TTSResponse and res.header.message_type == AUDIO_ONLY_RESPONSE:
                    yield res.payload   
                elif res.optional.event in [EVENT_TTSSentenceStart, EVENT_TTSSentenceEnd]:
                    continue
                else:
                    break

            await send_text_task
                
        except Exception as e:
            logger.error(f"Streaming TTS failed: {str(e)}")
            raise
        finally:
            # 如果任务未完成，意味着打断事件发生，此时需要手动取消任务
            if send_text_task and not send_text_task.done():
                send_text_task.cancel()
                try:
                    await send_text_task
                except asyncio.CancelledError:
                    logger.debug("已取消发送文本任务")

    async def astream_tts_to_file(self, text_stream: AsyncGenerator[str, None], output_path: str) -> None:
        """
        将文本流转换为语音流并保存到文件
        Args:
            text_stream: 要转换的文本流
            output_path: 输出音频文件路径
        """ 
        try:
            # 确保输出目录存在
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            async with aiofiles.open(output_path, "wb") as f:
                async for audio_chunk in self.astream_tts(text_stream):
                    await f.write(audio_chunk)
        except Exception as e:
            logger.error(f"Streaming TTS to file failed: {str(e)}")
            raise
