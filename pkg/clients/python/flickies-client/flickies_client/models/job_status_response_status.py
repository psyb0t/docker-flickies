from enum import Enum


class JobStatusResponseStatus(str, Enum):
    CANCELLED = "cancelled"
    COMPLETE = "complete"
    FAILED = "failed"
    PENDING = "pending"
    RUNNING = "running"

    def __str__(self) -> str:
        return str(self.value)
