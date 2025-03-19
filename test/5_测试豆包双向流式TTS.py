import asyncio
import json
import uuid

import aiofiles
import websocket
import websockets
from websockets.asyncio.client import ClientConnection


"""
豆包大模型语音合成-双向流式API的实现
官方文档：https://www.volcengine.com/docs/6561/1329505#%E7%A4%BA%E4%BE%8Bsamples

主要功能：
1. 建立WebSocket连接
2. 发送文本内容
3. 接收音频流
4. 保存为音频文件
"""

# 协议版本和头部大小常量
PROTOCOL_VERSION = 0b0001  # 协议版本号
DEFAULT_HEADER_SIZE = 0b0001  # 默认头部大小

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
    """消息头部类，包含协议版本、消息类型等信息"""

    def __init__(self,
                 protocol_version=PROTOCOL_VERSION,
                 header_size=DEFAULT_HEADER_SIZE,
                 message_type: int = 0,
                 message_type_specific_flags: int = 0,
                 serial_method: int = NO_SERIALIZATION,
                 compression_type: int = COMPRESSION_NO,
                 reserved_data=0):
        """
        初始化消息头部
        Args:
            protocol_version: 协议版本
            header_size: 头部大小
            message_type: 消息类型
            message_type_specific_flags: 消息类型特定标志
            serial_method: 序列化方法
            compression_type: 压缩类型
            reserved_data: 保留数据
        """
        self.header_size = header_size
        self.protocol_version = protocol_version
        self.message_type = message_type
        self.message_type_specific_flags = message_type_specific_flags
        self.serial_method = serial_method
        self.compression_type = compression_type
        self.reserved_data = reserved_data

    def as_bytes(self) -> bytes:
        """将头部信息转换为字节序列"""
        return bytes([
            (self.protocol_version << 4) | self.header_size,
            (self.message_type << 4) | self.message_type_specific_flags,
            (self.serial_method << 4) | self.compression_type,
            self.reserved_data
        ])


class Optional:
    """可选信息类，包含事件类型、会话ID等信息"""
    
    def __init__(self, event: int = EVENT_NONE, sessionId: str = None, sequence: int = None):
        """
        初始化可选信息
        Args:
            event: 事件类型
            sessionId: 会话ID
            sequence: 序列号
        """
        self.event = event
        self.sessionId = sessionId
        self.errorCode: int = 0
        self.connectionId: str | None = None
        self.response_meta_json: str | None = None
        self.sequence = sequence

    def as_bytes(self) -> bytes:
        """将可选信息转换为字节序列"""
        option_bytes = bytearray()
        # 添加事件类型
        if self.event != EVENT_NONE:
            option_bytes.extend(self.event.to_bytes(4, "big", signed=True))
        # 添加会话ID
        if self.sessionId is not None:
            session_id_bytes = str.encode(self.sessionId)
            size = len(session_id_bytes).to_bytes(4, "big", signed=True)
            option_bytes.extend(size)
            option_bytes.extend(session_id_bytes)
        # 添加序列号
        if self.sequence is not None:
            option_bytes.extend(self.sequence.to_bytes(4, "big", signed=True))
        return option_bytes


class Response:
    """响应类，包含头部、可选信息和负载数据"""
    
    def __init__(self, header: Header, optional: Optional):
        self.optional = optional
        self.header = header
        self.payload: bytes | None = None

    def __str__(self):
        return super().__str__()


async def send_event(ws: websocket, header: bytes, optional: bytes | None = None,
                     payload: bytes = None):
    """
    发送事件到WebSocket服务器
    Args:
        ws: WebSocket连接
        header: 消息头部
        optional: 可选信息
        payload: 负载数据
    """
    full_client_request = bytearray(header)
    if optional is not None:
        full_client_request.extend(optional)
    if payload is not None:
        payload_size = len(payload).to_bytes(4, 'big', signed=True)
        full_client_request.extend(payload_size)
        full_client_request.extend(payload)
    await ws.send(full_client_request)


def read_res_content(res: bytes, offset: int):
    """
    从响应数据中读取内容
    Args:
        res: 响应数据
        offset: 偏移量
    Returns:
        content: 读取的内容
        offset: 更新后的偏移量
    """
    content_size = int.from_bytes(res[offset: offset + 4], 'big')
    offset += 4
    content = str(res[offset: offset + content_size])
    offset += content_size
    return content, offset


def read_res_payload(res: bytes, offset: int):
    """
    从响应数据中读取负载
    Args:
        res: 响应数据
        offset: 偏移量
    Returns:
        payload: 读取的负载
        offset: 更新后的偏移量
    """
    payload_size = int.from_bytes(res[offset: offset + 4], 'big')
    offset += 4
    payload = res[offset: offset + payload_size]
    offset += payload_size
    return payload, offset


def parser_response(res) -> Response:
    """
    解析服务器响应
    Args:
        res: 原始响应数据
    Returns:
        Response: 解析后的响应对象
    """
    if isinstance(res, str):
        raise RuntimeError(res)
    response = Response(Header(), Optional())
    
    # 解析头部信息
    header = response.header
    num = 0b00001111
    header.protocol_version = res[0] >> 4 & num
    header.header_size = res[0] & 0x0f
    header.message_type = (res[1] >> 4) & num
    header.message_type_specific_flags = res[1] & 0x0f
    header.serialization_method = res[2] >> num
    header.message_compression = res[2] & 0x0f
    header.reserved = res[3]
    
    # 解析可选信息和负载
    offset = 4
    optional = response.optional
    if header.message_type == FULL_SERVER_RESPONSE or AUDIO_ONLY_RESPONSE:
        if header.message_type_specific_flags == MsgTypeFlagWithEvent:
            optional.event = int.from_bytes(res[offset:8], 'big')
            offset += 4
            if optional.event == EVENT_NONE:
                return response
            elif optional.event == EVENT_ConnectionStarted:
                optional.connectionId, offset = read_res_content(res, offset)
            elif optional.event == EVENT_ConnectionFailed:
                optional.response_meta_json, offset = read_res_content(res, offset)
            elif (optional.event == EVENT_SessionStarted
                  or optional.event == EVENT_SessionFailed
                  or optional.event == EVENT_SessionFinished):
                optional.sessionId, offset = read_res_content(res, offset)
                optional.response_meta_json, offset = read_res_content(res, offset)
            else:
                optional.sessionId, offset = read_res_content(res, offset)
                response.payload, offset = read_res_payload(res, offset)
    elif header.message_type == ERROR_INFORMATION:
        optional.errorCode = int.from_bytes(res[offset:offset + 4], "big", signed=True)
        offset += 4
        response.payload, offset = read_res_payload(res, offset)
    return response


async def run_demo(appId: str, token: str, speaker: str, text: str, output_path: str):
    """
    运行TTS演示
    Args:
        appId: 应用ID
        token: 访问令牌
        speaker: 说话人
        text: 要转换的文本
        output_path: 输出音频文件路径
    """
    # 设置WebSocket连接头部
    ws_header = {
        "X-Api-App-Key": appId,
        "X-Api-Access-Key": token,
        "X-Api-Resource-Id": 'volc.service_type.10029',
        "X-Api-Connect-Id": uuid.uuid4(),
    }
    url = 'wss://openspeech.bytedance.com/api/v3/tts/bidirection'
    # websocket.create_connection(url, ws_header) as ws

    async with websockets.connect(url, additional_headers=ws_header, max_size=1000000000) as ws:
        # 建立连接
        await start_connection(ws)
        res = parser_response(await ws.recv())
        print(res)
        print_response(res, 'start_connection res:')
        if res.optional.event != EVENT_ConnectionStarted:
            raise RuntimeError("start connection failed")

        # 开始会话
        session_id = uuid.uuid4().__str__().replace('-', '')
        await start_session(ws, speaker, session_id)
        res = parser_response(await ws.recv())
        print_response(res, 'start_session res:')
        if res.optional.event != EVENT_SessionStarted:
            raise RuntimeError('start session failed!')

        # 发送文本并接收音频
        await send_text(ws, speaker, text, session_id)
        await finish_session(ws, session_id)
        async with aiofiles.open(output_path, mode="wb") as output_file:
            while True:
                res = parser_response(await ws.recv())
                print_response(res, 'send_text res:')
                if res.optional.event == EVENT_TTSResponse and res.header.message_type == AUDIO_ONLY_RESPONSE:
                    await output_file.write(res.payload)
                elif res.optional.event in [EVENT_TTSSentenceStart, EVENT_TTSSentenceEnd]:
                    continue
                else:
                    break
        
        # 结束连接
        await finish_connection(ws)
        res = parser_response(await ws.recv())
        print_response(res, 'finish_connection res:')
        print('===> 退出程序')


def print_response(res, tag: str):
    """打印响应信息"""
    print(f'===>{tag} header:{res.header.__dict__}')
    print(f'===>{tag} optional:{res.optional.__dict__}')


def get_payload_bytes(uid='1234', event=EVENT_NONE, text='', speaker='', audio_format='mp3',
                      audio_sample_rate=24000):
    """
    生成负载数据的字节序列
    Args:
        uid: 用户ID
        event: 事件类型
        text: 文本内容
        speaker: 说话人
        audio_format: 音频格式
        audio_sample_rate: 采样率
    Returns:
        bytes: 负载数据的字节序列
    """
    return str.encode(json.dumps(
        {
            "user": {"uid": uid},
            "event": event,
            "namespace": "BidirectionalTTS",
            "req_params": {
                "text": text,
                "speaker": speaker,
                "audio_params": {
                    "format": audio_format,
                    "sample_rate": audio_sample_rate
                }
            }
        }
    ))


async def start_connection(websocket):
    """启动WebSocket连接"""
    header = Header(message_type=FULL_CLIENT_REQUEST, message_type_specific_flags=MsgTypeFlagWithEvent).as_bytes()
    optional = Optional(event=EVENT_Start_Connection).as_bytes()
    payload = str.encode("{}")
    return await send_event(websocket, header, optional, payload)


async def start_session(websocket, speaker, session_id):
    """启动TTS会话"""
    header = Header(message_type=FULL_CLIENT_REQUEST,
                    message_type_specific_flags=MsgTypeFlagWithEvent,
                    serial_method=JSON
                    ).as_bytes()
    optional = Optional(event=EVENT_StartSession, sessionId=session_id).as_bytes()
    payload = get_payload_bytes(event=EVENT_StartSession, speaker=speaker)
    return await send_event(websocket, header, optional, payload)


async def send_text(ws: ClientConnection, speaker: str, text: str, session_id):
    """发送要转换的文本"""
    header = Header(message_type=FULL_CLIENT_REQUEST,
                    message_type_specific_flags=MsgTypeFlagWithEvent,
                    serial_method=JSON).as_bytes()
    optional = Optional(event=EVENT_TaskRequest, sessionId=session_id).as_bytes()
    payload = get_payload_bytes(event=EVENT_TaskRequest, text=text, speaker=speaker)
    return await send_event(ws, header, optional, payload)


async def finish_session(ws, session_id):
    """结束TTS会话"""
    header = Header(message_type=FULL_CLIENT_REQUEST,
                    message_type_specific_flags=MsgTypeFlagWithEvent,
                    serial_method=JSON
                    ).as_bytes()
    optional = Optional(event=EVENT_FinishSession, sessionId=session_id).as_bytes()
    payload = str.encode('{}')
    return await send_event(ws, header, optional, payload)


async def finish_connection(ws):
    """结束WebSocket连接"""
    header = Header(message_type=FULL_CLIENT_REQUEST,
                    message_type_specific_flags=MsgTypeFlagWithEvent,
                    serial_method=JSON
                    ).as_bytes()
    optional = Optional(event=EVENT_FinishConnection).as_bytes()
    payload = str.encode('{}')
    return await send_event(ws, header, optional, payload)


if __name__ == "__main__":
    # 配置参数
    appId = ''  # 填写你的应用ID
    token = ''  # 填写你的访问令牌
    speaker = 'zh_female_shuangkuaisisi_moon_bigtts'  # 说话人
    text = '明朝开国皇帝朱元璋也称这本书为,万物之根'  # 要转换的文本
    output_path = './tmp/test.mp3'  # 输出文件路径
    asyncio.run(run_demo(appId, token, speaker, text, output_path))
