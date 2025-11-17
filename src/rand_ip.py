import random
from collections import defaultdict

def get_random_ip_port():
    output_file = "client_ip.txt"

    start_port = 1230
    end_port = 1240

    with open(output_file, "w") as f:
        for b in range(0, 33):  # 0 to 32 inclusive
            for c in range(1, 256):  # Skip .0
                ip = f"127.0.{b}.{c}"
                for port in range(start_port, end_port + 1):
                    f.write(f"{ip} {port}\n")

    # print(f"Generated {output_file} with valid [IP PORT] pairs.")

def read_ip_port_list(filename="client_ip.txt"):
    ip_port_array = []
    with open(filename, "r") as f:
        for line in f:
            parts = line.strip().split()
            if len(parts) == 2:
                ip = parts[0]
                port = parts[1]
                if port.isdigit():
                    ip_port_array.append(f"{ip} {port}")
    return ip_port_array

def get_random_address(address_list, mode=0,base_ip=None):
    start_port = 1230
    end_port = 1240
    full_ports_set = set(range(start_port, end_port + 1))

    if mode == 0:
        return random.choice(address_list)

    # Build map: ip -> set of used ports
    ip_port_map = defaultdict(set)
    for addr in address_list:
        ip, port = addr.split()
        ip_port_map[ip].add(int(port))

    if mode == 2:
        if base_ip is None:
            return random.choice(address_list)  # fallback if no base_ip is provided

        base_prefix = ".".join(base_ip.split(".")[:3])  # e.g., "127.0.0"
        candidates = []

        for ip, used_ports in ip_port_map.items():
            if ip.startswith(base_prefix) and 0 < len(used_ports) < len(full_ports_set):
                candidates.append((ip, list(used_ports)))

        if not candidates:
            return random.choice(address_list)

        ip, used_port_list = random.choice(candidates)
        chosen_port = random.choice(used_port_list)
        return f"{ip} {chosen_port}"

    elif mode == 1:
        if base_ip is None:
            base_ip = random.choice(list(ip_port_map.keys()))
        base_third = base_ip.split(".")[2]

        candidates = [
            ip for ip in ip_port_map.keys()
            if ip.split(".")[2] != base_third and ip_port_map[ip]
        ]
        if not candidates:
            return None

        ip = random.choice(candidates)
        port = random.choice(list(ip_port_map[ip]))
        return f"{ip} {port}"

    return None

def write_ip(address_list, new_address=None, output_file="client_ip.txt"):
    # Combine and sort (all are strings like "127.0.0.1 1234")
    if new_address is not None:
        combined = address_list + [new_address]
    else:
        combined = address_list

    def sort_key(address_str):
        ip, port = address_str.split()
        return tuple(map(int, ip.split("."))) + (int(port),)

    combined_sorted = sorted(combined, key=sort_key)

    with open(output_file, "w") as f:
        for address in combined_sorted:
            f.write(address + "\n")

    # print(f"Updated addresses written to {output_file}")
    return combined_sorted

# list_p = read_ip_port_list()
# r = get_random_address(list_p, mode=0)
# print(r)
# list_p.remove(r)
# write_ip(list_p, output_file="new.txt")