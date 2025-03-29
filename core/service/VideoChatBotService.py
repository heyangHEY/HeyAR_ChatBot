from typing import Optional
from core.component.video import AsyncVideoHandler

class VideoChatBotService():
    video_handler: Optional[AsyncVideoHandler] = None
    ...

    def init(self):
        pass
