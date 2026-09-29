from pybit.unified_trading import HTTP


class BybitClientInitializer:
    def __init__(self, config: dict):
        self.api_config = config["api"]
        self.session = None

    def get_rest_session(self) -> HTTP:
        if not self.session:
            kwargs = {
                "testnet": self.api_config["testnet"],
                "api_key": self.api_config["api_key"],
                "api_secret": self.api_config["api_secret"],
                "recv_window": self.api_config["recv_window_default"],
            }
            domain = self.api_config.get("domain")
            if domain:
                kwargs["domain"] = domain
            self.session = HTTP(**kwargs)
        return self.session
