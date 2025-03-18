import yaml
import logging

logger = logging.getLogger(__name__)

class ConfigLoader():
    all_cfg: dict = {}
    # 各个组件的类型名称
    cls_video_name: str = ""
    cls_audio_name: str = ""
    cls_vad_name: str = ""
    cls_asr_name: str = ""
    cls_llm_name: str = ""
    cls_tts_name: str = ""

    def __init__(self, config_file):
        with open(config_file, 'r') as f:
            self.all_cfg = yaml.safe_load(f)

            version = self.all_cfg.get('version', "")
            logger.info(f'load config file, version: {version}, path: {config_file}')

            sc_cfg = self.all_cfg.get('selected_component', {})
            self.cls_video_name = sc_cfg.get('VIDEO', "")
            self.cls_audio_name = sc_cfg.get('AUDIO', "")
            self.cls_vad_name = sc_cfg.get('VAD', "")
            self.cls_asr_name = sc_cfg.get('ASR', "")
            self.cls_llm_name = sc_cfg.get('LLM', "")
            self.cls_tts_name = sc_cfg.get('TTS', "")

    def get_cls_name(self, cls_name: str):
        mapping = {
            "VIDEO": self.cls_video_name,
            "AUDIO": self.cls_audio_name,
            "VAD": self.cls_vad_name,
            "ASR": self.cls_asr_name,
            "LLM": self.cls_llm_name,
            "TTS": self.cls_tts_name,
        }
        return mapping.get(cls_name, "")
    
    def get_video_config(self):
        return self.all_cfg.get('VIDEO', {}).get(self.cls_video_name, {})
    
    def get_audio_config(self):
        return self.all_cfg.get('AUDIO', {}).get(self.cls_audio_name, {})
    
    def get_vad_config(self):
        return self.all_cfg.get('VAD', {}).get(self.cls_vad_name, {})
    
    def get_asr_config(self):
        return self.all_cfg.get('ASR', {}).get(self.cls_asr_name, {})
    
    def get_llm_config(self):
        return self.all_cfg.get('LLM', {}).get(self.cls_llm_name, {})
    
    def get_tts_config(self):
        return self.all_cfg.get('TTS', {}).get(self.cls_tts_name, {})
