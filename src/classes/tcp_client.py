import struct
import time
import socket
import random
import threading
import sys
import os
import traceback

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../")))
from helper.constants import *
from helper.utils import *
from classes.tcp_base import *

class TCPClientSocket(TCPBaseSocket):
    def __init__(self, local_port, server_ip, server_port, ip_address="127.0.0.1", udp_socket=None, handler=None):
        super().__init__(local_port, ip_address, udp_socket, handler=handler)
        self.server_addr = (server_ip, server_port)
        self.remote_addr.append(self.server_addr)  
        self.running = True
        self.lock = threading.Lock()
        self.termination_state = {}  # Track termination state
        self.TIMEOUT_DURATION = 10.0  # seconds for termination timeout

    def bind(self):
        if self.local_addr is None:
            raise ValueError("No port specified for listening.")
        self.udp.bind(self.local_addr)
        print(f"Running on {self.local_addr}...")

    def connect(self, username):
        print(f"Client {self.local_addr} is connecting to server ip: {self.remote_addr[0][0]}, server port: {self.remote_addr[0][1]}")
        remote = self.remote_addr[0]

        x = random.randint(1, (1 << 31) - 1)
        seq_num = x
        
        # SENDING SYN
        syn_seg = TCPSegment(
            src_port=self.local_addr[1],
            dest_port=remote[1],
            seq_num=seq_num,
            ack_num=0,
            flags=FLAG_SYN,
            timestamp=int(time.time()),
            messagetype=2,
            payload=username.encode()
        )
        print(f"Remote: {remote}")
        self.udp.sendto(syn_seg.pack(), remote)
        print("\u2192 Sent SYN")

        # RECEIVING SYN-ACK
        synack_seg = None
        try:
            self.udp.settimeout(5.0)
            while True:
                data, _ = self.udp.recvfrom(128)
                synack_seg = TCPSegment.unpack(data)
                if not synack_seg:
                    print("[!] Corrupted SYN-ACK segment — retrying...")
                    continue
                if synack_seg.flags != FLAG_SYN_ACK or synack_seg.ack_num != seq_num + 1:
                    print(f"[!] Invalid SYN-ACK received: ")
                    print(f"Is SYN-ACK: {synack_seg.flags == FLAG_SYN_ACK}")
                    print(f"Expected ACK: {seq_num + 1}")
                    print(f"Received ACK: {synack_seg.ack_num}")
                    continue
                break # success
        except socket.timeout:
            print("[!] Timeout waiting for SYN-ACK — connection failed.")
            return False
        finally:
            self.udp.settimeout(None)

        # Setting the trio and window size
        self.send_base[remote] = x + 1
        self.next_seq_num[remote] = x + 1
        self.ack_num[remote] = synack_seg.seq_num + 1 # y + 1
        self.remote_window_size[remote] = synack_seg.windowsize

        print("\u2190 Received SYN-ACK")

        # SENDING FINAL ACK
        self.recv_window_size[self.server_addr] = 5*104

        ack_seg = TCPSegment(
            src_port=self.local_addr[1],
            dest_port=remote[1],
            seq_num=self.next_seq_num[remote],
            ack_num=self.ack_num[remote],
            flags=FLAG_ACK,
            timestamp=int(time.time()),
            messagetype=2,
            windowsize=self.recv_window_size[self.server_addr],
            payload=username.encode()
        )

        self.udp.sendto(ack_seg.pack(), remote)
        print("\u2192 Sent final ACK")
        print("Connection established.")
        return True

    def initiate_termination(self):
        """Initiate connection termination (client side)"""
        print("[CLIENT] Initiating connection termination...")
        
        with self.lock:
            if self.server_addr in self.termination_state:
                print("[CLIENT] Termination already in progress")
                return
                
            # Set termination state
            self.termination_state[self.server_addr] = "FIN_WAIT_1"
            
            current_seq = self.next_seq_num.get(self.server_addr, 0)
            fin_segment = TCPSegment(
                src_port=self.local_addr[1],
                dest_port=self.server_addr[1],
                seq_num=current_seq,
                ack_num=self.ack_num.get(self.server_addr, 0),
                flags=FLAG_FIN,
                windowsize=self.recv_window_size.get(self.server_addr, 0),
                timestamp=int(time.time()),
                messagetype=3  # Leave message type
            )
            
            try:
                self.udp.sendto(fin_segment.pack(), self.server_addr)
                print(f"→ Sent FIN (seq={current_seq}) to server")
                
                # Update sequence number
                self.next_seq_num[self.server_addr] = current_seq + 1
                
            except Exception as e:
                print(f"[ERROR] Failed to send FIN: {e}")
                traceback.print_exc()
            

                    


    def handle_termination_segment(self, segment):
        current_state = self.termination_state.get(self.server_addr)
        
        if current_state == "FIN_WAIT_1":
            if has_flag(segment.flags, FLAG_FIN_ACK):
                expected_ack = self.next_seq_num.get(self.server_addr, 0)
                print(f"← Received FIN-ACK (ack={segment.ack_num})")
                
                self.send_final_termination_ack(segment)
                self.termination_state[self.server_addr] = "TIME_WAIT"
                return True
        return False

    def send_final_termination_ack(self, received_segment):
        ack_segment = TCPSegment(
            src_port=self.local_addr[1],
            dest_port=self.server_addr[1],
            seq_num=self.next_seq_num.get(self.server_addr, 0),
            ack_num=received_segment.seq_num + 1,
            flags=FLAG_ACK,
            timestamp=int(time.time()),
            messagetype=3  # Leave message type
        )
        
        try:
            self.udp.sendto(ack_segment.pack(), self.server_addr)
            print(f"→ Sent final ACK (ack={ack_segment.ack_num})")
            self.disconnect()  
        except Exception as e:
            print(f"[ERROR] Failed to send final ACK: {e}")

    def handle_server_shutdown(self, segment):
        """Handle server-initiated connection termination"""
        print("[CLIENT] Server initiated shutdown")
        
        with self.lock:
            # Update expected sequence numbers
            if self.server_addr not in self.expected_seq_nums:
                self.expected_seq_nums[self.server_addr] = segment.seq_num
                
            # Send FIN-ACK response
            fin_ack_segment = TCPSegment(
                src_port=self.local_addr[1],
                dest_port=self.server_addr[1],
                seq_num=self.next_seq_num.get(self.server_addr, 0),
                ack_num=segment.seq_num + 1,
                flags=FLAG_FIN_ACK,
                timestamp=int(time.time()),
                messagetype=6  # Shutdown response
            )
            
            try:
                self.udp.sendto(fin_ack_segment.pack(), self.server_addr)
                print(f"→ Sent FIN-ACK (seq={fin_ack_segment.seq_num}, ack={fin_ack_segment.ack_num})")
                
                # Update sequence number
                self.next_seq_num[self.server_addr] = fin_ack_segment.seq_num + 1
                self.termination_state[self.server_addr] = "LAST_ACK"

                # Wait for final ACK
                # self.wait_for_final_ack()

            except Exception as e:
                print(f"[ERROR] Failed to send FIN-ACK: {e}")
                

    def wait_for_final_ack(self):
        try:
            self.udp.settimeout(self.TIMEOUT_DURATION)
            start_time = time.time()

            while time.time() - start_time < self.TIMEOUT_DURATION:
                try:
                    data, addr = self.udp.recvfrom(128)
                    if addr != self.server_addr:
                        continue
 
                    segment = TCPSegment.unpack(data)
                    if not segment:
                        continue
 
                    # Check for final ACK
                    if has_flag(segment.flags, FLAG_ACK):
                        expected_ack = self.next_seq_num.get(self.server_addr, 0)
                        if segment.ack_num == expected_ack:
                            print(f"← Received final ACK (ack={segment.ack_num})")
                            print("[CLIENT] Connection terminated by server")
                            break

                except socket.timeout:
                    continue
                except Exception as e:
                    print(f"[ERROR] During final ACK wait: {e}")
                    break

        except Exception as e:
            print(f"[ERROR] Final ACK timeout: {e}")
        finally:
            self.udp.settimeout(None)

    def send_kill_signal(self, remote_addr):
        # Send a kill signal to the server
        kill_segment = TCPSegment(
            src_port=self.local_addr[1],
            dest_port=remote_addr[1],
            seq_num=self.next_seq_num.get(remote_addr, 0),
            ack_num=self.ack_num.get(remote_addr, 0),
            flags=0, # No flags for kill signal
            timestamp=int(time.time()),
            messagetype=6  # Kill message type
        )
        
        try:
            self.udp.sendto(kill_segment.pack(), remote_addr)
            print(f"→ Sent KILL signal to {remote_addr}")
        except Exception as e:
            print(f"[ERROR] Failed to send KILL signal: {e}")

    def send_failed_kill_signal(self, remote_addr):
        # Send a failed kill signal to the server
        failed_kill_segment = TCPSegment(
            src_port=self.local_addr[1],
            dest_port=remote_addr[1],
            seq_num=self.next_seq_num.get(remote_addr, 0),
            ack_num=self.ack_num.get(remote_addr, 0),
            flags=0, # No flags for failed kill signal
            timestamp=int(time.time()),
            messagetype=7  # Failed kill message type
        )
        
        try:
            self.udp.sendto(failed_kill_segment.pack(), remote_addr)
            print(f"→ Sent FAILED KILL signal to {remote_addr}")
        except Exception as e:
            print(f"[ERROR] Failed to send FAILED KILL signal: {e}")


    def send_message_tcp(self, message):
        try:
            if message.startswith("!"): # COMMAND
                if message == "!disconnect":
                    self.initiate_termination()
                    return
                elif message.startswith("!change"):
                    self.send_data(self.server_addr, message.encode(), 5) 
                elif message.startswith("!kill"):
                    password = message.split(" ", 1)[1] if len(message.split(" ")) > 1 else ""
                    if password == SERVER_KILL_PASSWORD:
                        self.send_kill_signal(self.server_addr)
                    else :
                        self.send_failed_kill_signal(self.server_addr)
                else:
                    print("[CLIENT] Unknown command.")
            else: # MESSAGE
                self.send_data(self.server_addr, message.encode(), 1) 
        except Exception as e:
            print(f"[ERROR] Sending message: {e}")

    def receive_message_tcp(self):
        while self.running:
            try:
                data, receive_addr = self.udp.recvfrom(128)
                segment = TCPSegment.unpack(data)
                
                if receive_addr not in self.remote_addr:
                    self.remote_addr.append(receive_addr)
                    
                if (segment.flags == FLAG_ACK and segment.messagetype == 1): # acknowledgement of data being sent 
                    threading.Thread(target=self.receive_ack(segment, receive_addr), daemon=True).start()
                elif (segment.flags == FLAG_ACK and segment.messagetype == 6): 
                    self.disconnect()  # Handle server shutdown
                elif (segment.flags != FLAG_ACK and segment.messagetype == 1): # message
                    threading.Thread(target=self.handle_sender_data(segment, receive_addr), daemon=True).start()
                elif (segment.flags == FLAG_FIN):
                    self.handle_server_shutdown(segment)
                elif segment.flags == FLAG_FIN_ACK:
                    self.handle_termination_segment(segment)
            except Exception as e:
                if self.running:
                    print(f"[CLIENT] Receive port lost connection. Error: {e}")
                    traceback.print_exc()
                self.running = False

    def recv_buffer_controller(self, server):
        server_buffer = self.recv_buffer[server]
        message_parts = [] 
        current_payload_length = 0
        current_total_length = 0

        ends_with_null = False

        for i, part in enumerate(server_buffer):
            message_parts.append(part["payload"])
            current_payload_length += len(part["payload"])
            current_total_length = part["payload_length"]

            if part["payload"].endswith(b'\x00'):
                ends_with_null = True

        is_message_complete = current_payload_length == current_total_length
        force_flush = self.recv_window_size[server] < 104 or (self.next_seq_num.get(server, 0) - self.send_base.get(server, 0) + 64) > self.recv_window_size[server]

        if is_message_complete or ends_with_null or force_flush:
            full_payload = b''.join(message_parts)
            self.recv_window_size[server] += current_payload_length
            self.recv_buffer[server].clear() 
            self.handler(full_payload, current_total_length)

    def network_heartbeat(self):
        heartbeat_seg = TCPSegment(
            src_port=self.local_addr[1],
            dest_port=self.server_addr[1],
            seq_num=0,
            ack_num=0,
            flags=0,  # No flags for heartbeat
            timestamp=int(time.time()),
            messagetype=4  # Heartbeat message type
        )
        self.udp.sendto(heartbeat_seg.pack(), self.server_addr)

    def disconnect(self):
        self.running = False
        print("[CLIENT] Disconnecting...")
        self.udp.close()
        os._exit(0)
