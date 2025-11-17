import struct
import time
import socket
import random
import threading
import sys
import os
from collections import *
import traceback
from abc import ABC, abstractmethod

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../")))

from .tcp_segment import *
from helper.constants import *
from helper.utils import *

class TCPBaseSocket:
    def __init__(self, local_port, ip_address="0.0.0.0", udp_socket=None, handler=None):
        self.udp = udp_socket or socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.local_addr = (ip_address, local_port)

        self.handler = handler
        self.remote_addr = [] # List of (ip, port) tuples

        # Sequence and ACK tracking
        self.ack_num = {}                                       # addr -> ack to send to sender                 RECEIVER
        self.seq_num = {}                                      

        # Sliding window
        self.recv_window_size = defaultdict(lambda: 5 * 104)    # window size advertised to other sockets       RECEIVER
        self.remote_window_size = defaultdict(lambda: 5 * 104)  # window size advertised to this socket         SENDER                         
        self.send_base = {}                                     # base after threeway handshake                 SENDER
        self.next_seq_num = {}                                  # next seq_num after sending                    SENDER
        self.unacked_segments = {}                              # seq_num -> remote, segment still in flight/not ACKED  SENDER
        self.expected_seq_nums = {}                             # addr -> expected seq                      SENDER
        self.expected_ack_nums = {}                              
        self.timer_start = {}  

        # Recv buffer
        self.recv_buffer = {} # addr -> [{seq_num, message_type, timestamp, total_payload_length, payload}]

    def send_segment(self, segment: TCPSegment, remote): 
        # print(f"Send to remote: {remote}")
        packed = segment.pack()
        self.udp.sendto(packed, remote)

    def send_data(self, remote_addr, payload: bytes, message_type):
        payload += b'\x00'
        max_payload = 64
        payload_length = len(payload)
        self.next_seq_num[remote_addr]
        chunks = [payload[i:i + max_payload] for i in range(0, len(payload), max_payload)]

        for chunk in chunks:
            while True:
                # Check sliding window capacity
                send_base = self.send_base.get(remote_addr, 0)
                next_seq = self.next_seq_num.get(remote_addr, 0)
                window = self.remote_window_size.get(remote_addr, 0)
                in_flight = next_seq - send_base
                # print(f"Nextseq: {next_seq}, Sendbase: {send_base}, In-flight: {in_flight}")

                if next_seq >= send_base and in_flight + len(chunk) <= window:
                    # Can send
                    segment = TCPSegment(
                        src_port=self.local_addr[1],
                        dest_port=remote_addr[1],
                        seq_num=next_seq,
                        ack_num=0,
                        flags=0,
                        payload=chunk,
                        payloadlength=payload_length,
                        timestamp=int(time.time()),
                        messagetype=message_type
                    )

                    # Sending
                    self.send_segment(segment, remote_addr)
                    # print(f"[SEND] Sent segment {next_seq} to {remote_addr}")

                    # Track unacked
                    if next_seq not in self.unacked_segments:
                        self.unacked_segments[next_seq] = []
                    self.unacked_segments[next_seq].append((remote_addr, segment))

                    # Advance window
                    self.next_seq_num[remote_addr] = next_seq + len(chunk)
                    break  
                else:
                    # print(f"[WAIT] Window full, waiting to send...")
                    if (next_seq < send_base):
                        print(f"Failed to send message, sequence number error lower than base")
                        return
                    # print(f"[WAIT] Window full: windowsize = {window}, in_flight = {in_flight}, length = {len(chunk)}, waiting to send...")
                    time.sleep(0.2)  # Wait before retrying
    
    def handle_sender_data(self, segment, sender):
        seq = segment.seq_num
        payload = segment.payload

        # Accept and update
        self.ack_num[sender] = seq + len(payload)
        self.recv_window_size[sender] -= len(payload) 
        if sender not in self.recv_buffer:
            self.recv_buffer[sender] = []
        self.recv_buffer[sender].append({
            "seq_num": seq,
            "message_type": segment.messagetype,
            "timestamp": segment.timestamp,
            "payload": segment.payload,
            "payload_length": segment.payloadlength
        })
        self.recv_buffer_controller(sender)

        ack = TCPSegment(
            src_port=self.local_addr[1],
            dest_port=sender[1],
            seq_num=0,
            ack_num=self.ack_num[sender],
            flags=FLAG_ACK,
            timestamp=int(time.time()),
            windowsize=self.recv_window_size[sender],
            messagetype=segment.messagetype
        )
        # print(f"140 address {client}")
        # print(f"server address {self.local_addr}")
        self.udp.sendto(ack.pack(), sender)
        # print(f"Sent ACK to {sender} for received segment {segment.seq_num} with ACK: {self.ack_num[sender]}")
    
    def receive_ack(self, seg, sender):
        to_remove = []
        # print(f"[RECEIVE] Received from {sender} ACK: {seg.ack_num}")
        for seq_num, _ in self.unacked_segments.items():
            if seq_num + len(seg.payload) <= seg.ack_num:
                self.send_base[sender] = max(self.send_base.get(sender, 0), seg.ack_num)
                self.remote_window_size[sender] = seg.windowsize
                to_remove.append(seq_num)
        for seq_num in to_remove:
            del self.unacked_segments[seq_num]

    @abstractmethod
    def recv_buffer_controller(self, sender):
        pass
