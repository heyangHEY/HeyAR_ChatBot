from mcp.server.fastmcp import FastMCP
import time

class MusicClient:
    def __init__(self):
        self.mcp = FastMCP()
    
    def play_music(self, music_name):
        """播放指定音乐"""
        result = self.mcp.call("play_music", music_name)
        print(result["message"])
    
    def stop_music(self):
        """停止音乐播放"""
        result = self.mcp.call("stop_music")
        print(result["message"])
    
    def list_music(self):
        """列出可用的音乐文件"""
        result = self.mcp.call("list_music")
        if result["status"] == "success":
            print("可用的音乐文件：")
            for file in result["files"]:
                print(f"- {file}")
        else:
            print(result["message"])

def main():
    client = MusicClient()
    
    while True:
        print("\n=== 音乐播放器菜单 ===")
        print("1. 列出所有音乐")
        print("2. 播放音乐")
        print("3. 停止播放")
        print("4. 退出")
        
        choice = input("请选择操作 (1-4): ")
        
        if choice == "1":
            client.list_music()
        elif choice == "2":
            client.list_music()
            music_name = input("请输入要播放的音乐文件名: ")
            client.play_music(music_name)
        elif choice == "3":
            client.stop_music()
        elif choice == "4":
            print("退出程序")
            break
        else:
            print("无效的选择，请重试")
        
        time.sleep(1)

if __name__ == "__main__":
    main() 