from uuid import UUID


class PayloadNotFoundError(Exception):
    def __init__(self, payload_id: UUID):
        self.payload_id = payload_id
        super().__init__(f"Payload not found: {payload_id}")
