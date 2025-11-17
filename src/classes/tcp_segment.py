import struct
import time
import socket
import random
import threading
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../")))

from helper.constants import *
from helper.utils import *

class TCPSegment:
    FORMAT = '!HHQQBH H H Q B 4s' # Total = 40 bytes
    HEADER_SIZE = struct.calcsize(FORMAT)

    def __init__(self, src_port, dest_port, seq_num, ack_num, flags, checksum=0, windowsize=0, payloadlength=0, timestamp=None, messagetype=0,
                 padding=b'\x00\x00\x00\x00', payload=b''):
        # HEADER (40 bytes)
        self.src_port = src_port            # 16 bit (2 byte)
        self.dest_port = dest_port          # 16 bit (2 byte)
        self.seq_num = seq_num              # 64 bit (8 byte)
        self.ack_num = ack_num              # 64 bit (8 byte)
        self.flags = flags                  # 8 bit (CWR, ECE, URG, ACK, PSH, RST, SYN, FIN) (1 byte)
        self.checksum = checksum            # 16 bit (2 byte)
        self.windowsize = windowsize        # 16 bit (2 byte)
        self.payloadlength = payloadlength  # 16 bit (2 byte)
        self.timestamp = timestamp          # 64 bit (8 byte)
        self.messagetype = messagetype      # 8 bit (1 byte) -> (0: other, 1: message, 2: join, 3: leave, 4: heartbeat, 5: other_command, 6: kill)
        self.padding = padding              # 8 bit (4 byte)

        # === Field Normalization Logic ===
        if self.timestamp is None:
            self.timestamp = int(time.time())
        if self.payloadlength is None and payload is not None:
            self.payloadlength = len(payload)

        # PAYLOAD 
        self.payload = payload              # <= 64 byte

    def pack(self): # get checksum
        temp_header = struct.pack(
            self.FORMAT,
            self.src_port,
            self.dest_port,
            self.seq_num,
            self.ack_num,
            self.flags,
            0, # initial checksum
            self.windowsize,
            self.payloadlength,
            self.timestamp,
            self.messagetype,
            self.padding
        )

        segment = temp_header + self.payload
        self.checksum = calculate_checksum(segment)

        header = struct.pack(
            self.FORMAT,
            self.src_port,
            self.dest_port,
            self.seq_num,
            self.ack_num,
            self.flags,
            self.checksum,
            self.windowsize,
            self.payloadlength,
            self.timestamp,
            self.messagetype,
            self.padding
        )

        return header + self.payload

    @classmethod
    def unpack(cls, data):
        if len(data) < cls.HEADER_SIZE: # data is shorter than header
            return None

        header = data[:cls.HEADER_SIZE] # get header
        payload = data[cls.HEADER_SIZE:] # get payload
        unpacked = struct.unpack(cls.FORMAT, header) # return python tuple of FORMAT

        temp_header = struct.pack(
            cls.FORMAT,
            unpacked[0],  # src_port
            unpacked[1],  # dest_port
            unpacked[2],  # seq_num
            unpacked[3],  # ack_num
            unpacked[4],  # flags
            0,            # checksum replaced with zero
            unpacked[6],  # windowsize
            unpacked[7],  # payloadlength
            unpacked[8],  # timestamp
            unpacked[9],  # messagetype
            unpacked[10]  # padding
        )
        computed_checksum = calculate_checksum(temp_header + payload)
        if computed_checksum != unpacked[5]: # check if checksum is same from the one that is sent
            return None

        return cls(
            src_port=unpacked[0],
            dest_port=unpacked[1],
            seq_num=unpacked[2],
            ack_num=unpacked[3],
            flags=unpacked[4],
            checksum=unpacked[5],
            windowsize=unpacked[6],
            payloadlength=unpacked[7],
            timestamp=unpacked[8],
            messagetype=unpacked[9],
            padding=unpacked[10],
            payload=payload
        )
