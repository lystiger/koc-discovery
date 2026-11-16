from koc.config import load_config


def test_config_has_required_cost_and_score_values():
    config = load_config()
    assert {"scoring", "kalodata_prices", "llm_caps", "rate_card", "s1"} <= config.keys()
    assert {"s1_weights", "final_weights"} <= config["scoring"].keys()
    assert {"credits_cap", "ui_creator_detail_view"} <= config["kalodata_prices"].keys()
    assert "usd_cap" in config["llm_caps"]
    assert "label" in config["rate_card"]
    assert "s2_limit" in config["s1"]
    assert 0 <= config["kalodata_prices"]["ui_creator_detail_view"]
    assert 0 < config["kalodata_prices"]["credits_cap"] <= 100
    assert config["s1"]["s2_limit"] >= 5
