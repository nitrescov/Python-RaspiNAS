# This file contains the code needed for communication with the frontend which will be released at a later time.
# Copyright (C) 2021  Nico Pieplow (nitrescov)
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


def guiserver(host_ip, port, usernames, userdata):
    separator = "<separator>"
    send_buffer = 2097152
    receive_buffer = 16384

    s_receive = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s_receive.bind((host_ip, port))
    s_receive.listen()

    while True:
        s_client_login, address_1 = s_receive.accept()
        try:
            login_packet = s_client_login.recv(receive_buffer).decode()
            name, hash_value = login_packet.split(separator)
            name_position = -1
            hash_position = -1
            for i in range(len(usernames)):
                if name == usernames[i]:
                    name_position = i
            for j in range(len(userdata)):
                if hash_value == userdata[j]:
                    hash_position = j
            if (name_position >= 0) and (hash_position >= 0) and (name_position == hash_position):
                folder = ""
                for root, dirs, files in os.walk(f"users/{name}"):
                    folder_path = root[7:]
                    if folder_path.count("\\") > 1 or folder_path.count("/") > 1:
                        folder = folder + "\n" + folder_path
                    else:
                        folder = folder + "\n\n" + folder_path

                folder = folder.encode()
                while True:
                    byte_block = folder[:send_buffer]
                    if not byte_block:
                        break
                    s_client_login.sendall(byte_block)
                    folder = folder[send_buffer:]

                s_client_login.close()
            else:
                s_client_login.send("False".encode())
                s_client_login.close()
                continue
        except ValueError:
            print("[LOG] Possible security risk detected: received data with wrong number of arguments.")
            s_client_login.close()
            continue

        s_client_data, address_2 = s_receive.accept()
        if address_1[0] == address_2[0]:
            try:
                file_info = s_client_data.recv(receive_buffer).decode()
                file_name, file_size, path = file_info.split(separator)
                file_name = os.path.basename(file_name)
                file_size = int(file_size)

                if os.path.isdir(f'users/{path}') and not os.path.isfile(f'users/{path}/{file_name}'):
                    s_client_data.send("True".encode())
                    new_file = open(f'users/{path}/{file_name}', "wb")
                    while True:
                        file_bytes = s_client_data.recv(receive_buffer)
                        if not file_bytes:
                            break
                        new_file.write(file_bytes)
                    new_file.close()
                else:
                    s_client_data.send("False".encode())

                s_client_data.close()
            except ValueError:
                print("[LOG] Possible security risk detected: server remained in wrong state. Resetting now.")
                s_client_data.close()
                continue
        else:
            print("[LOG] Possible security risk detected: IP address of client changed during transfer.")
            s_client_data.close()
