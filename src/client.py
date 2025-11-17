from classes.tcp_client import TCPClientSocket
from helper.constants import *
from rand_ip import *

import socket
import threading
import time
import os
import traceback
import sys

class ChatClient:
    def __init__(self, server_ip, server_port, local_ip="127.0.0.2", local_port=8932):
        self.server_addr = (server_ip, server_port)
        self.local_addr = (local_ip, local_port)
        self.name = "Unknown"
        self.tcp = None
        self.running = True
        self.chat_buffer = []

    def start(self):
        while True:
            name = input("Enter your username: ")
            if name.lower() != "server":
                break
            print("Invalid username. Please try again.")

        self.tcp = TCPClientSocket(self.local_addr[1], self.server_addr[0], self.server_addr[1], self.local_addr[0], handler=self.handler)
        self.tcp.bind()
        res = self.tcp.connect(name)
        if (not res):
            print("Failed to connect to server")
            return
        self.name = name
        threading.Thread(target=self.send_messages).start()
        threading.Thread(target=self.receive_messages).start()
        threading.Thread(target=self.send_heartbeats).start()
        # threading.Thread(target=self.periodic_clear).start()

        while self.running:
            continue

    def periodic_clear(self):
        while self.running:
            time.sleep(5)
            self.tcp.recv_buffer[self.server_addr].clear()

    def send_messages(self):
        while self.running:
            msg = input("")
            self.tcp.send_message_tcp(msg)
    
    def receive_messages(self):
        self.tcp.receive_message_tcp()
    
    def handler(self, payload, payload_length):
        if payload_length == 0:  # Termination message
            self.running = False
            print("\n[CLIENT] Server terminated the connection")
            self.tcp.cleanup_connection()
            return
            
        if (len(payload) == payload_length):
            self.client_print(payload.decode())
        else:
            self.add_to_chat_buffer(payload, payload_length)

    def add_to_chat_buffer(self, payload, total_payload):
        self.chat_buffer.append(payload)
        total_length = 0
        for i in range(len(self.chat_buffer)):
            total_length += len(self.chat_buffer[i])

        if (total_length == total_payload):
            full_message = b''.join(self.chat_buffer)
            self.client_print(full_message.decode())
            self.chat_buffer = []

    def client_print(self, message):
        os.system("cls" if os.name == "nt" else "clear")
        print("---------------- JARKOM CHATROOM ----------------")
        print(f"{message}\n", end="")
        print("------------------------------------------------\n>> ", end="")
    
    def send_heartbeats(self):
        while self.running:
            # print("Sending heartbeats")
            time.sleep(HEARTBEAT_SEND_INTERVAL)
            self.tcp.network_heartbeat()




if __name__ == "__main__":
    # main()
    para = 1

    address_list = read_ip_port_list()
    address = get_random_address(address_list, mode=para) # 0 = random, 1 = different, 2 = same

    s_ip = DEFAULT_SERVER_IP
    s_port = DEFAULT_SERVER_PORT

    l_ip, port = address.split()
    l_port = int(port)

    client = ChatClient(server_ip=s_ip, server_port=s_port, local_ip=l_ip, local_port=l_port)
    try:
        client.start()
    except Exception as e:
        print(f"An error occurred while starting the client: {e}")
        traceback.print_exc()
    
