from pathlib import Path

BASE_DIR: Path = Path(__file__).parent
LOG_FORMAT: str = '%(asctime)s - [%(levelname)s] - %(message)s'
PORT: int = 8000
HOST: str = '127.0.0.1'
VALUE_FOR_RANDOMIZER: int = 6
