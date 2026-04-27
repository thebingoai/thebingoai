class LoopDetectedError(Exception):
    def __init__(self, message: str, tool_name: str | None = None, total_calls: int = 0):
        super().__init__(message)
        self.tool_name = tool_name
        self.total_calls = total_calls
