import struct
import time
import socket
import random
import threading
import sys
import os
from datetime import datetime

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../")))
from helper.constants import *
from helper.utils import *
from classes.tcp_base import *

class TCPServerSocket(TCPBaseSocket):
    def __init__(self, local_port, ip_address="0.0.0.0", udp_socket=None, handler=None):
        super().__init__(local_port, ip_address, udp_socket, handler=handler)
        self.over_recv = False
        self.lock = threading.Lock()
        self.termination_state = {}  # Track termination state for each connection
        self.TIMEOUT_DURATION = 10.0  # seconds for termination timeout

    def disconnect(self):
        self.udp.close()
        os._exit(0)

    def listen(self):
        if self.local_addr is None:
            raise ValueError("No port specified for listening.")
        self.udp.bind(self.local_addr)
        print(f"Listening on port {self.local_addr}...")

    def accept(self):
        print(f"[SERVER] Chat room started on {self.local_addr}")
        while True:
            data, client = self.udp.recvfrom(128)
            seg = TCPSegment.unpack(data)
            # print(f"Payload: {seg.payload.decode()}, Message type: {seg.messagetype}, Flags: {seg.flags}")
            if (not seg):
                print(f"Corrupted/Invalid segment received from {client}")
                continue
            
            flag = seg.flags
            type = seg.messagetype
            if (flag == FLAG_SYN and type == 2): # SYN Threeway Handshake
                if (client in self.remote_addr):
                    print(f"{client} is already connected to server")
                    continue
                threading.Thread(target=self.threeway_handshake_syn, args=(seg, client), daemon=True).start()
            elif (flag == FLAG_FIN_ACK):
                threading.Thread(target=self.handle_killing_signal_ack, daemon=True).start()
            elif (flag == FLAG_FIN):
                if (type == 3):
                    threading.Thread(target=self.handle_client_disconnect, args=(seg, client), daemon=True).start()
            elif (flag == FLAG_ACK): 
                if (type == 1): # Confirmation of chatroom segments
                    if (client not in self.remote_addr): 
                        print(f"{client} tried to ack chat log, but is not in server!")
                        continue 
                    threading.Thread(target=self.receive_ack, args=(seg, client), daemon=True).start()
                elif(type == 2): # FINAL ACK Threeway Handshake
                    if (client not in self.remote_addr):
                        print(f"{client} tried to do threeway handshake out of order")
                        continue
                    threading.Thread(target=self.threeway_handshake_final_ack, args=(seg, client), daemon=True).start()
                elif (type == 3): # FINAL ACK FIN Termination
                    threading.Thread(target=self.handle_termination_ack, args=(seg, client), daemon=True).start()
            elif (flag != FLAG_ACK): # MESSAGE OR OTHER COMMAND
                if (type == 1 or type == 5):
                    if (client not in self.remote_addr):
                        print(f"{client} tried to message, but is not in server!")
                        continue
                    threading.Thread(target=self.handle_sender_data, args=(seg, client), daemon=True).start()
                if (type == 4):
                    threading.Thread(target=self.handler, args=(client, 4, seg.timestamp, b'', 0), daemon=True).start()
                if (type == 6):
                    threading.Thread(target=self.handle_killing_signal, args=(client,), daemon=True).start()
                if (type == 7):
                    threading.Thread(target=self.handler, args=(client, 7, seg.timestamp, b'', 0), daemon=True).start()


    def handle_killing_signal_ack(self):
        ack_seg = TCPSegment(
            src_port=self.local_addr[1],
            dest_port=0,
            seq_num=0,
            ack_num=0,
            flags=FLAG_ACK,
            windowsize=0,
            timestamp=int(time.time()),
            messagetype=6 # Kill command ACK
        )

        for client in self.remote_addr:
            self.udp.sendto(ack_seg.pack(), client)

        self.disconnect()

    

    def handle_killing_signal(self, client):
        """Handle the kill command from a client"""
        fin_seg = TCPSegment(
            src_port=self.local_addr[1],
            dest_port=client[1],
            seq_num=self.next_seq_num.get(client, 0),
            ack_num=self.ack_num.get(client, 0),
            flags=FLAG_FIN,
            windowsize=self.recv_window_size.get(client, 0),
            timestamp=int(time.time()),
            messagetype=6 # Kill command
        )

        self.udp.sendto(fin_seg.pack(), client)
        # print(f"[!] Sent FIN to {client} for termination")
    
    def handle_client_disconnect(self, segment, client):
        """Handle client-initiated connection termination"""
        with self.lock:
            if client not in self.remote_addr:
                print(f"[!] FIN from unconnected client {client}")
                return

            # print(f"← Received FIN (seq={segment.seq_num}) from {client}")
            
            self.expected_seq_nums[client] = segment.seq_num + 1
            
            current_seq = self.next_seq_num.get(client, 0)
            fin_ack_seg = TCPSegment(
                src_port=self.local_addr[1],
                dest_port=client[1],
                seq_num=current_seq,
                ack_num=segment.seq_num + 1,
                flags=FLAG_FIN_ACK,
                windowsize=self.recv_window_size.get(client, 0),
                timestamp=int(time.time()),
                messagetype=3
            )
            
        successful_termination = False
        self.udp.sendto(fin_ack_seg.pack(), client)
        # print(f"→ Sent FIN-ACK (seq={current_seq}, ack={segment.seq_num + 1}) to {client}")
        self.next_seq_num[client] = current_seq + 1

    def handle_termination_ack(self, ack_seg, client):
        try:
            print("line 108")
            if ack_seg.src_port != client[1]:
                print(f"[!] Received ACK from unexpected address {ack_seg.src_port}, expected {client[1]}")
                return

            # Validate final ACK
            if has_flag(ack_seg.flags, FLAG_ACK):
                expected_ack = self.next_seq_num.get(client, 0)
                if ack_seg.ack_num == expected_ack:
                    # print(f"← Received final ACK (ack={ack_seg.ack_num}) from {client}")
                    successful_termination = True
                    self.handler(client, 3, int(time.time()), b"", 0)
                    
                    # Clean up connection state
                    print(f"[✓] Successfully handled disconnect from {client}")
                    self.cleanup_connection(client)
                else:
                    print(f"[!] Invalid final ACK: expected {expected_ack}, got {ack_seg.ack_num}")
                    print(f"[!] Failed to complete disconnect handshake with {client}")

        except Exception as e:
            print(f"[!] Error waiting for final ACK: {e}")
            traceback.print_exc()



    def cleanup_connection(self, client):
        """Clean up all connection state for a client"""
        try:
            # Remove from remote address list
            if client in self.remote_addr:
                self.remote_addr.remove(client)
            
            # Clean up all tracking dictionaries
            self.seq_num.pop(client, None)
            self.send_base.pop(client, None)
            self.next_seq_num.pop(client, None)
            self.ack_num.pop(client, None)
            self.expected_ack_nums.pop(client, None)
            self.expected_seq_nums.pop(client, None)
            self.recv_window_size.pop(client, None)
            self.remote_window_size.pop(client, None)
            self.unacked_segments.pop(client, None)
            self.timer_start.pop(client, None)
            
            # Clean up receive buffers
                
            print(f"[✓] Cleaned up connection state for {client}")
            
        except Exception as e:
            print(f"[!] Error during cleanup: {str(e)}")
            traceback.print_exc()
    
    def threeway_handshake_syn(self, segment, client):
        print(f"← Received SYN from {client}")
        y = random.randint(1, (1 << 31) - 1)
        self.remote_addr.append(client)

        # Setting initial values
        seq_num = y
        self.send_base[client] = y + 1
        self.next_seq_num[client] = y + 1
        self.ack_num[client] = segment.seq_num + 1 # x + 1
        self.recv_window_size[client] = 5 * 104

        synack_seg = TCPSegment(
            src_port=self.local_addr[1],
            dest_port=client[1],
            seq_num=seq_num,
            ack_num=self.ack_num[client], 
            flags=FLAG_SYN_ACK,
            timestamp=int(time.time()),
            windowsize = self.recv_window_size[client]
        )
        self.udp.sendto(synack_seg.pack(), client)
        print("→ Sent SYN-ACK")
    
    def threeway_handshake_final_ack(self, segment, client):
        if segment.ack_num != self.send_base[client]:
            self.remote_addr.remove(client)
            self.send_base.pop(client, None)
            self.next_seq_num.pop(client, None)
            self.ack_num.pop(client, None)
            self.recv_window_size.pop(client, None)
            self.remote_window_size.pop(client, None)
            self.unacked_segments.pop(client, None)

            print(f"[!] Invalid ACK from {client} — handshake rejected.")
            return

        self.remote_window_size[client] = segment.windowsize

        print("← Received final ACK")
        print(f"[✓] Connection established with {client}")
        self.handler(client, 2, segment.timestamp, segment.payload, segment.payloadlength)
    
    def recv_buffer_controller(self, client):
        client_buffer = self.recv_buffer[client]
        current_messagetype = 0
        current_timestamp = 0
        message_parts = [] 
        current_payload_length = 0
        current_total_length = 0

        ends_with_null = False

        for i, part in enumerate(client_buffer):
            message_parts.append(part["payload"])
            current_payload_length += len(part["payload"])
            current_total_length = part["payload_length"]
            current_messagetype = part["message_type"]
            current_timestamp = part["timestamp"]

            if part["payload"].endswith(b'\x00'):
                ends_with_null = True

        is_message_complete = current_payload_length == current_total_length
        force_flush = self.recv_window_size[client] < 104 or (self.next_seq_num.get(client, 0) - self.send_base.get(client, 0) + 64) > self.recv_window_size[client]

        if is_message_complete or ends_with_null or force_flush:
            full_payload = b''.join(message_parts)
            self.recv_window_size[client] += current_payload_length
            self.recv_buffer[client].clear() 
            self.handler(client, current_messagetype, current_timestamp, full_payload, current_total_length)
    
    def delete_client(self, client):
        self.remote_addr.remove(client)
        self.send_base.pop(client, None)
        self.next_seq_num.pop(client, None)
        self.ack_num.pop(client, None)
        self.recv_window_size.pop(client, None)
        self.remote_window_size.pop(client, None)
        self.unacked_segments.pop(client, None)
        self.recv_buffer.pop(client, None)



