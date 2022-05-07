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
    frame_counters = [str(randint(n*42, n*42+42)) for n in range(6)]
    fc_list = ",".join(frame_counters)

    try:
        connection.sendall((frame_counters[0] + separator + fc_list).encode())
        login_packet = connection.recv(buffer).decode()
        fc1, name, hash_value = login_packet.split(separator)
        name_position = -1
        hash_position = -1
        for i in range(len(usernames)):
            if name == usernames[i]:
                name_position = i
        for j in range(len(userdata)):
            if hash_value == userdata[j]:
                hash_position = j
        if (fc1 == frame_counters[1]) and (name_position >= 0) and (hash_position >= 0) and (name_position == hash_position):
            folder = ""
            for root, dirs, files in os.walk(f"users/{name}"):
                folder_path = root[6:]
                subdir_count = folder_path.count("/")
                if subdir_count <= 1:
                    folder = folder + "\n\n" + folder_path
                else:
                    folder = folder + "\n" + ("  " * (subdir_count - 1)) + folder_path

            folder_bytes = (frame_counters[2] + separator + folder).encode()
            while True:
                byte_block = folder_bytes[:buffer]
                if not byte_block:
                    break
                connection.sendall(byte_block)
                folder_bytes = folder_bytes[buffer:]

            file_info = connection.recv(buffer).decode()
            fc3, file_name, file_size, path = file_info.split(separator)
            file_name = os.path.basename(file_name)

            if fc3 == frame_counters[3] and os.path.isdir(f"users/{path}") and not os.path.isfile(f"users/{path}/{file_name}"):
                connection.sendall((frame_counters[4] + separator + "True").encode())
                new_file = open(f"users/{path}/{file_name}", "wb")
                while True:
                    file_bytes = connection.recv(buffer)
                    if not file_bytes:
                        break
                    new_file.write(file_bytes)
                new_file.close()
            else:
                connection.sendall((frame_counters[4] + separator + "False").encode())
            connection.close()
        else:
            connection.sendall((frame_counters[2] + separator + "False").encode())
            connection.close()
    except ValueError:
        print("[SOCKET LOG] Possible security risk detected: received data with wrong number of arguments.")
        connection.close()
