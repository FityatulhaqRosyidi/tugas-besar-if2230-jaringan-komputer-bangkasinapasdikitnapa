from classes.tcp_server import TCPServerSocket
from helper.constants import *
import threading
import time
from datetime import datetime
import os
import traceback
import socket
import random

class ChatServer:
    def __init__(self, ip_address="128.0.0.1", port=1234):
        self.server_addr = (ip_address, port)
        self.tcp = None
        self.momentary_buffer = {}  # {addr -> [{messagetype, timestamp, byte, total_length}]}
        self.chat_room = []         # List of messages in the chat room
        self.clients = {}           # {addr: {'name': name, 'heartbeat': time, 'color': color}}
        self.lock = threading.Lock()
        self.all_colors = [BLACK_COLOR, RED_COLOR, GREEN_COLOR, YELLOW_COLOR, BLUE_COLOR, MAGENTA_COLOR, CYAN_COLOR,
            BRIGHT_BLACK_COLOR, BRIGHT_RED_COLOR,
            BRIGHT_YELLOW_COLOR, BRIGHT_BLUE_COLOR, BRIGHT_MAGENTA_COLOR,
            BRIGHT_CYAN_COLOR]
        self.used_colors = []  


    def start(self):
        self.tcp = TCPServerSocket(self.server_addr[1], ip_address=self.server_addr[0], handler=self.handler)
        self.tcp.listen()
        self.tcp.accept()

    # Update the handler method to handle termination messages
    def handler(self, client, type, timestamp, payload, total_payload):
        if (type == 1):  # Message
            if (len(payload) == total_payload):
                self.add_message(f"{self.clients[client]['color']}{self.clients[client]['name']} {RESET_COLOR} [{time.strftime('%H:%M:%S', time.localtime(timestamp))}]: {payload.decode()} ")
            else:
                self.add_to_momentary_buff(client, type, timestamp, payload, total_payload)
        elif (type == 2):  # Join
            self.add_client(client, timestamp, payload.decode())
        elif (type == 3):  # Leave
            self.remove_client(client, timestamp)
        elif (type == 4):
            self.handle_heartbeat(client)
        elif (type == 5):
            decode = payload.decode()
            if (decode.startswith("!change")):
                new_name = decode[len("!change "):].strip()
                old_name = self.clients[client]['name']
                self.clients[client]['name'] = new_name
                for i, line in enumerate(self.chat_room):
                    if old_name in line:
                        self.chat_room[i] = line.replace(old_name, new_name)
                self.send_chat()
                self.server_print()
        elif (type == 7):  #failed kill signal
            self.add_message(f"{RED_COLOR}SERVER [{time.strftime('%H:%M:%S', time.localtime(timestamp))}]: Nice try {self.clients[client]['name']}... {RESET_COLOR}")


    def remove_client(self, client, timestamp):
        name = self.clients[client]['name']
        self.add_message(f"{GREEN_COLOR}SERVER [{time.strftime('%H:%M:%S', time.localtime(timestamp))}]: {name} has left the chat!{RESET_COLOR}")
        if client in self.clients:
            del self.clients[client]
        if client in self.momentary_buffer:
            del self.momentary_buffer[client]
        

    def add_client(self, client, timestamp, name):
        if (self.used_colors == self.all_colors):
            self.used_colors = []  
        available_color = [color for color in self.all_colors if color not in self.used_colors]
        random_color = random.choice(available_color)
        self.used_colors.append(random_color)
        self.clients[client] = {'name': name, 'heartbeat': HEARTBEAT_INTERVAL, 'color': random_color}
        if client not in self.clients:
            threading.Thread(target=self.monitor_heartbeat, args=(client,), daemon=True).start()
        self.add_message(f"{BRIGHT_GREEN_COLOR}SERVER [{time.strftime('%H:%M:%S', time.localtime(timestamp))}]: {name} has joined the chatroom!{RESET_COLOR}")

    def add_message(self, message):
        self.chat_room.append(message)
        if len(self.chat_room) > MAX_MESSAGES:
            self.chat_room.pop(0)
        self.send_chat()
    
    def add_to_momentary_buff(self, client, type, timestamp, payload, total_payload):
        if client not in self.momentary_buffer:
            self.momentary_buffer[client] = []
        self.momentary_buffer[client].append({
            "message_type": type,
            "timestamp": timestamp,
            "payload": payload,
            "payload_length": total_payload
        })

        current_type = self.momentary_buffer[client][0]["message_type"]
        current_buffer_parts = []
        accumulated_length = 0
        i = 0
        while i < len(self.momentary_buffer[client]) and accumulated_length < total_payload and current_type == self.momentary_buffer[client][i]["message_type"]:
            segment = self.momentary_buffer[client][i]
            current_buffer_parts.append(segment["payload"])
            accumulated_length += len(segment["payload"])
            i += 1
            if (accumulated_length == total_payload):
                break

        # print(f"Accumulated lenght: {accumulated_length}")
        # print(f"Total payload: {total_payload}")
        if accumulated_length >= total_payload:
            full_message = b''.join(current_buffer_parts)
            name = self.clients[client]['name']
            self.add_message(f"{self.clients[client]['color']}{name}{RESET_COLOR} [{time.strftime('%H:%M:%S', time.localtime(timestamp))}]: {full_message.decode()}")
            self.momentary_buffer[client] = []
    
    def send_chat(self):
        chat_log = '\n'.join(self.chat_room)
        for client_addr in self.clients:
            threading.Thread(target=self.tcp.send_data, args=(client_addr, chat_log.encode(), 1), daemon=True).start()
        self.server_print()
    
    def server_print(self):
        os.system("cls" if os.name == "nt" else "clear")
        print("---------------- SERVER CONSOLE ----------------")
        for message in self.chat_room:
            print(message)
        print("------------------------------------------------")
    
    def monitor_heartbeat(self, client):
        while client in self.clients:
            time.sleep(1) 
            self.clients[client]['heartbeat'] -= 1
            # print(f"{client} ({self.clients[client]['name']}) heartbeats: {self.clients[client]['heartbeat']}")

            if self.clients[client]['heartbeat'] <= 0:
                print(f"Client {client} is kicked out")
                self.tcp.delete_client(client)
                del self.clients[client]
                break

    def handle_heartbeat(self, client):
        if client in self.clients:
            self.clients[client]['heartbeat'] = HEARTBEAT_INTERVAL

    def monitor_clients(self):
        while True:
            time.sleep(1)
            with self.lock:
                for addr, info in list(self.clients.items()):
                    if time.time() - info['last_heartbeat'] > HEARTBEAT_INTERVAL:
                        self.remove_client(addr, f"{info['name']} was AFK and has been kicked!")

    def monitor_clients(self):
        while True:
            time.sleep(1)
            with self.lock:
                for addr, info in list(self.clients.items()):
                    if time.time() - info['last_heartbeat'] > HEARTBEAT_INTERVAL:
                        self.remove_client(addr, f"{info['name']} was AFK and has been kicked!")

    def disconnect(self):
        self.is_running = False
        print("\033[92m[SERVER] Disconnecting...\033[0m")
        self.udp.close()

if __name__ == "__main__":
    host = "0.0.0.0"
    port = DEFAULT_SERVER_PORT

    server = ChatServer(host, port)
    try:
        server.start()
    except Exception as e:
        print(f"[SERVER] Error: {e}")
        # traceback.print_exc()
    finally:
        server.tcp.handle_killing_signal_ack()
        if (server.tcp):
            server.tcp.udp.close()
            print("[SERVER] Server socket closed.")
