from pathlib import Path

import yaml


CONFIG_DIR = Path(__file__).resolve().parents[2] / "config"


def load_config(config_dir: str | Path = CONFIG_DIR) -> dict:
    root = Path(config_dir)
    names = {
        "scoring": "scoring.yaml",
        "rate_card": "rate_card.yaml",
        "kalodata_prices": "kalodata_prices.yaml",
        "llm_caps": "llm_caps.yaml",
        "s1": "pipeline.yaml",
        "product_categories": "product_categories.yaml",
        "video_topics": "video_topics.yaml",
    }
    return {key: yaml.safe_load((root / filename).read_text()) for key, filename in names.items()}
