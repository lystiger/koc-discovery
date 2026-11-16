import pytest


@pytest.fixture
def stable_test_config(monkeypatch):
    from koc.config import load_config
    from koc import cli, pipeline, report

    config = load_config()
    config["kalodata_prices"]["ui_creator_detail_view"] = 1.0
    config["s1"]["s2_limit"] = 15
    for module in (cli, pipeline, report):
        monkeypatch.setattr(module, "load_config", lambda config=config: config)
    return config
