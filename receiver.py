# This file contains the code needed for communication with the frontend which will be released at a later time.
# Copyright (C) 2022  Nico Pieplow (nitrescov)
# Contact: nitrescov@protonmail.com

# This program is free software: you can redistribute it and/or modify it under the terms of the
# GNU Affero General Public License as published by the Free Software Foundation,
# either version 3 of the License, or (at your option) any later version.

# This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY;
# without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
# See the GNU Affero General Public License for more details.

# You should have received a copy of the GNU Affero General Public License along with this program.
# If not, see <https://www.gnu.org/licenses/>.

import os
import socket
import struct
import threading
from random import randint


def socket_server(host_ip, port, usernames, userdata):
    s_receive = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s_receive.bind((host_ip, port))
    s_receive.listen()

    while True:
        s_client_connection, address = s_receive.accept()
        print(f"[SOCKET LOG] Client with address {address[0]}:{address[1]} connected.")
        threading.Thread(target=handle_connection, args=(s_client_connection, usernames, userdata), daemon=True).start()


def handle_connection(connection, usernames, userdata):
    separator = "<separator>"
    buffer = 65536  # 64K TCP packet size
    frame_counters = [randint(n*42, n*42+42) for n in range(6)]
    fc_list = ",".join([str(m) for m in frame_counters])

    try:
        fc_packet = fc_list.encode()
        send_header(connection, len(fc_packet), frame_counters[0])
        connection.sendall(fc_packet)

        login_len, fc1 = recv_header(connection)
        if not login_len:
            raise ValueError("no packet data")
        login_packet = connection.recv(login_len).decode()
        name, hash_value = login_packet.split(separator)
        name_position = -1
        hash_position = -1
        for i in range(len(usernames)):
            if name == usernames[i]:
                name_position = i
        for j in range(len(userdata)):
            if hash_value == userdata[j]:
                hash_position = j
        if fc1 == frame_counters[1] and 0 <= name_position == hash_position >= 0:
            folder = ""
            for root, dirs, files in os.walk(f"users/{name}"):
                folder_path = root[6:]
                subdir_count = folder_path.count("/")
                if subdir_count <= 1:
                    folder = folder + "\n\n" + folder_path
                else:
                    folder = folder + "\n" + ("  " * (subdir_count - 1)) + folder_path

            folder_packet = folder.encode()
            send_header(connection, len(folder_packet), frame_counters[2])
            connection.sendall(folder_packet)

            file_info_len, fc3 = recv_header(connection)
            if not file_info_len:
                raise ValueError("no packet data")
            file_info_packet = connection.recv(file_info_len).decode()
            file_name, file_size, path = file_info_packet.split(separator)
            file_name = os.path.basename(file_name)

            if fc3 == frame_counters[3] and os.path.isdir(f"users/{path}") and not os.path.isfile(f"users/{path}/{file_name}"):
                confirm_packet = "True".encode()
                send_header(connection, len(confirm_packet), frame_counters[4])
                connection.sendall(confirm_packet)

                file_len, fc5 = recv_header(connection)
                if not file_len:
                    raise ValueError("no packet data")
                if fc5 != frame_counters[5]:
                    raise ValueError("invalid packet data")
                current_file_len = 0
                new_file = open(f"users/{path}/{file_name}", "wb")
                while current_file_len < file_len:
                    file_bytes = connection.recv(buffer)
                    if not file_bytes:
                        break
                    new_file.write(file_bytes)
                    current_file_len += len(file_bytes)
                new_file.close()
            else:
                refuse_packet = "False".encode()
                send_header(connection, len(refuse_packet), frame_counters[4])
                connection.sendall(refuse_packet)
            connection.close()
        else:
            refuse_packet = "False".encode()
            send_header(connection, len(refuse_packet), frame_counters[2])
            connection.sendall(refuse_packet)
            connection.close()
    except ValueError:
        print("[SOCKET LOG] Possible security risk detected: Received no or invalid data.")
        connection.close()

def send_header(sock: socket.socket, msg_len: int, fc: int):
    msg_header = struct.pack("!Q", msg_len) + struct.pack("!H", fc)
    sock.sendall(msg_header)

def recv_header(sock: socket.socket):
    raw_header = sock.recv(10)
    if not raw_header:
        return 0, 0
    return struct.unpack("!Q", raw_header[:8])[0], struct.unpack("!H", raw_header[8:])[0]
