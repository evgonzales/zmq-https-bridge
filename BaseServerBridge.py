class BaseBridge:
    def __init__(self, running: bool):
        self._running = running

    def is_running(self) -> bool:
        return self._running

    def set_running(self, new_state: bool):
        self._running = new_state

    def tick_server(self):
        pass
