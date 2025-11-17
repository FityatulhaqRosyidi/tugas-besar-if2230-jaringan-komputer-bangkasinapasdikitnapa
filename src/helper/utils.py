def calculate_checksum(data: bytes) -> int:
    if len(data) % 2 == 1:
        data += b'\x00'  # pad to even length

    checksum = 0
    for i in range(0, len(data), 2):
        word = (data[i] << 8) + data[i + 1]  # big-endian
        checksum += word
        checksum = (checksum & 0xFFFF) + (checksum >> 16)  # wrap

    return ~checksum & 0xFFFF

def has_flag(value: int, flag: int) -> bool:
    return (value & flag) == flag

def set_flag(value: int, flag: int) -> int:
    return value | flag

def clear_flag(value: int, flag: int) -> int:
    return value & ~flag