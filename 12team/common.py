import pickle
import binascii
from enum import Enum


BUFFER_SIZE = 256

class MessageType(Enum):
    WORK_ORDER = 1
    INVENTORY_UPDATE_FROM_WARE = 2
    INVENTORY_UPDATE_FROM_WORKER = 3

class SendType(Enum):
    SEND_FROM_WAREHOUSE = 1
    SEND_FROM_WORKER = 2
    SEND_FROM_CENTRAL = 3

class Message:
    def __init__(self, type, send_type, content):
        self.type = type
        self.send_type = send_type
        self.content = content

    def serialize(self):
        data = pickle.dumps(self)
        # print(f"직렬화 후 데이터: {binascii.hexlify(data)}")
        """Serialize the Message object to bytes."""
        return pickle.dumps(self)

    @staticmethod
    def deserialize(data):
        # print(f"역직렬화 전 데이터: {binascii.hexlify(data)}")
        """Deserialize bytes to a Message object."""
        return pickle.loads(data)

"""
김예나: 192.168.122.5
조성빈: 192.168.0.3
강예린: 192.168.124.3
"""
# CENTRAL_SERVER_IP = "192.168.124.3"
# WORKER_SERVER_IP = "192.168.122.5"
# CENTRAL_SERVER_PORT = 8080
# WORKER_SERVER_PORT = 8081

CENTRAL_SERVER_IP = "127.0.0.1"
WORKER_SERVER_IP = "127.0.0.1"
CENTRAL_SERVER_PORT = 8080
WORKER_SERVER_PORT = 8081
