import json
from logger_factory import get_logger

logger = get_logger("Utils")

def load_instrument_config(json_path):
    """
    Load instrument configuration from a JSON file.
    
    Expected JSON structure:
    [
      {
        "symbol": "NSE_FO|50969",
        "name": "NIFTY 27000 CE 26 JUN 25",
        "step": [0.1, 0.2, 0.3, 0.4, 0.5],
        "trail": [0.03, 0.05, 0.07, 0.1, 0.12]
      },
      ...
    ]
    """
    try:
        with open(json_path, 'r') as f:
            config = json.load(f)
            logger.info(f"Loaded {len(config)} instruments from {json_path}")
            return config
    except Exception as e:
        logger.error(f"Error reading config file {json_path}: {e}")
        return []
