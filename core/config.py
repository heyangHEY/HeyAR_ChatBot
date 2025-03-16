import yaml
import logging

logger = logging.getLogger(__name__)

class ConfigLoader:
    def __init__(self, config_path):
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)
            version = self.config.get('version', "")
            logger.info(f'load config file, version: {version}, path: {config_path}')

    def get_component_config(self):
        return self.config.get('component', {})

    def get_video_config(self):
        return self.config.get('video', {})
    
    def get_audio_config(self):
        return self.config.get('audio', {})
    
    def get_vad_config(self):
        return self.config.get('vad', {})
    
    def get_asr_config(self):
        return self.config.get('asr', {})
    
    def get_llm_config(self):
        return self.config.get('llm', {})
    
    def get_tts_config(self):
        return self.config.get('asr', {})
