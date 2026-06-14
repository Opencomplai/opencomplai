def pytest_configure(config):
    if getattr(config.option, "importmode", None) != "importlib":
        config.option.importmode = "importlib"
