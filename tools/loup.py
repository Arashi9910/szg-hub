"""在獨立的網路命名空間裡把 loopback（lo）打開。給 tools/isotest.sh 用。"""
import socket, fcntl, struct
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
flags = struct.unpack('16sH', fcntl.ioctl(s, 0x8913, struct.pack('16sH', b'lo', 0)))[1]  # SIOCGIFFLAGS
fcntl.ioctl(s, 0x8914, struct.pack('16sH', b'lo', flags | 1))  # SIOCSIFFLAGS：IFF_UP
