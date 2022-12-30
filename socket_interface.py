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
import shutil
import hashlib
import threading

# Constants
BUFFER = 2**12  # Recommended INET packet size (4096 Bytes)
MAX_CMD_SIZE = 2**27  # Max command packet size to be cached in RAM (128 MB)
SEPARATOR = "<separator>"

# Communication Protocol:
# SERVER        CLIENT
#       <------- [CMD]
# [RSP] ------->
#       <------- [ACK]
# Packet will be resent, if either RSP or ACK indicate status STAT_INVALID_CHECKSUM
# Zero-byte-packets (header only) that aren't ACKs must use 48 zero bytes (bytes(48)) as their checksum

# List of commands and responses
# CMD_RESERVED = 0x00
CMD_LOGIN = 0x01
RSP_LOGIN = 0x02
CMD_UPLOAD_FILE = 0x03
RSP_UPLOAD_FILE = 0x04
CMD_GET_DIRECTORIES = 0x05
RSP_GET_DIRECTORIES = 0x06
CMD_DOWNLOAD_FILE = 0x07
RSP_DOWNLOAD_FILE = 0x08
CMD_DOWNLOAD_FOLDER = 0x09
RSP_DOWNLOAD_FOLDER = 0x0a
CMD_ACK = 0xff

# List of status indicators
# STAT_RESERVED = 0x00
STAT_INIT = 0x01
STAT_INVALID_CHECKSUM = 0x02
STAT_FAILURE = 0x03
STAT_SUCCESS = 0x04
STAT_FILE = 0x05


def socket_server(host_ip: str, port: int, usernames: list[str], userdata: list[str], basepath: str) -> None:
    s_receive = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s_receive.bind((host_ip, port))
    s_receive.listen()

    while True:
        s_client_connection, address = s_receive.accept()
        print(f"[SOCKET LOG] Client with address {address[0]}:{address[1]} connected")
        threading.Thread(target=handle_connection, args=(s_client_connection, usernames, userdata, basepath), daemon=True).start()


def handle_connection(connection: socket.socket, usernames: list[str], userdata: list[str], basepath: str):
    try:
        # Login phase (executed only once per session)
        while True:
            packet_len, packet_cmd, packet_status, packet_checksum, packet_secondary_header = receive_header(connection)
            if not (0 < packet_len <= MAX_CMD_SIZE) or packet_cmd != CMD_LOGIN or packet_status != STAT_INIT:
                raise ValueError("No login data received")
            packet_content = receive_data(connection, packet_len)
            if calc_hash(packet_content) != packet_checksum:
                connection.sendall(create_header(0, RSP_LOGIN, STAT_INVALID_CHECKSUM, bytes(48)))
                continue
            break
        user_name, user_hash = packet_content.decode("utf-8").split(SEPARATOR)
        name_position = -1
        hash_position = -1
        for i in range(len(usernames)):
            if user_name == usernames[i]:
                name_position = i
        for j in range(len(userdata)):
            if user_hash == userdata[j]:
                hash_position = j
        if name_position == hash_position >= 0:
            while True:
                connection.sendall(create_header(0, RSP_LOGIN, STAT_SUCCESS, bytes(48)))
                packet_len, packet_cmd, packet_status, packet_checksum, packet_secondary_header = receive_header(connection)
                if packet_cmd != CMD_ACK:
                    raise ValueError("Invalid command received on login")
                if packet_checksum[47] != RSP_LOGIN:
                    raise ValueError("Invalid ACK command received on login")
                if packet_status == STAT_INVALID_CHECKSUM:
                    continue
                elif packet_status == STAT_SUCCESS:
                    break
                else:
                    raise ValueError("Invalid ACK status received on login")
        else:
            connection.sendall(create_header(0, RSP_LOGIN, STAT_FAILURE, bytes(48)))
            raise ValueError("Invalid login credentials")

        # Command phase (accepting commands in a loop that only breaks if the connection is closed or an error occurs)
        cached_packet = (False, 0, bytes(), None)  # The cached packet contains a file indicator, the packet command, the header
                                                   # and either a bytes-object with the packet payload or a file path string
        while True:
            packet_len, packet_cmd, packet_status, packet_checksum, packet_secondary_header = receive_header(connection)
            if packet_cmd == CMD_ACK and packet_len == 0:
                if not cached_packet[2]:
                    raise ValueError("Received ACK, but nothing has been sent yet")
                if packet_status == STAT_INVALID_CHECKSUM and cached_packet[1] == packet_checksum[47]:
                    connection.sendall(cached_packet[2])
                    if cached_packet[0] and isinstance(cached_packet[3], str):
                        if not os.path.isfile(cached_packet[3]):
                            raise ValueError("Cached file does not exist anymore (concurrent access)")
                        with open(cached_packet[3], "rb") as file_to_resend:
                            while True:
                                data = file_to_resend.read(BUFFER)
                                if not data:
                                    break
                                connection.sendall(data)
                    else:
                        if cached_packet[3]:
                            connection.sendall(cached_packet[3])
                    continue
                elif packet_status == STAT_SUCCESS:
                    continue
                else:
                    raise ValueError("Received ACK with invalid status")
            elif packet_status == STAT_INIT:
                if packet_len > MAX_CMD_SIZE:
                    raise ValueError(f"Packet is not a file, but larger than the maximum of {MAX_CMD_SIZE / (2**20)} MB")
                if packet_cmd == CMD_GET_DIRECTORIES and packet_len == 0:
                    if bytes(48) != packet_checksum:
                        cached_packet = (False, RSP_GET_DIRECTORIES, create_header(0, RSP_GET_DIRECTORIES, STAT_INVALID_CHECKSUM, bytes(48)), None)
                        connection.sendall(cached_packet[2])
                        continue
                    else:
                        folders = list()
                        for root, dirs, files in os.walk(os.path.join(basepath, "users", user_name)):
                            folders.append(root.replace(os.path.join(basepath, "users") + "/", ""))
                        folder_packet = ("\n".join(folders)).encode("utf-8")
                        if len(folder_packet) > MAX_CMD_SIZE:
                            raise ValueError("Packet size overflow")
                        cached_packet = (False, RSP_GET_DIRECTORIES, create_header(len(folder_packet), RSP_GET_DIRECTORIES, STAT_SUCCESS, calc_hash(folder_packet)), folder_packet)
                        connection.sendall(cached_packet[2])
                        connection.sendall(folder_packet)
                        continue
                elif packet_cmd == CMD_DOWNLOAD_FILE and packet_len > 0:
                    file_path = receive_data(connection, packet_len)
                    complete_file_path = os.path.join(basepath, "users", file_path.decode("utf-8"))
                    if calc_hash(file_path) != packet_checksum:
                        cached_packet = (False, RSP_DOWNLOAD_FILE, create_header(0, RSP_DOWNLOAD_FILE, STAT_INVALID_CHECKSUM, bytes(48)), None)
                        connection.sendall(cached_packet[2])
                        continue
                    elif not file_path.decode("utf-8").startswith(user_name) or not os.path.isfile(complete_file_path):
                        cached_packet = (False, RSP_DOWNLOAD_FILE, create_header(0, RSP_DOWNLOAD_FILE, STAT_FAILURE, bytes(48)), None)
                        connection.sendall(cached_packet[2])
                        continue
                    else:
                        file_name, file_size = os.path.basename(complete_file_path), os.path.getsize(complete_file_path)
                        if SEPARATOR in complete_file_path:
                            raise ValueError(f"Invalid file name (contains {SEPARATOR})")
                        cached_packet = (True,
                                         RSP_DOWNLOAD_FILE,
                                         create_header(file_size, RSP_DOWNLOAD_FILE, STAT_SUCCESS, calc_hash(complete_file_path), (SEPARATOR.join([file_name, file_size])).encode("utf-8")),
                                         complete_file_path)
                        connection.sendall(cached_packet[2])
                        with open(complete_file_path, "rb") as file_to_send:
                            while True:
                                data = file_to_send.read(BUFFER)
                                if not data:
                                    break
                                connection.sendall(data)
                        continue
                elif packet_cmd == CMD_DOWNLOAD_FOLDER and packet_len > 0:
                    folder_path = receive_data(connection, packet_len)
                    complete_folder_path = os.path.join(basepath, "users", folder_path.decode("utf-8"))
                    if calc_hash(folder_path) != packet_checksum:
                        cached_packet = (False, RSP_DOWNLOAD_FOLDER, create_header(0, RSP_DOWNLOAD_FOLDER, STAT_INVALID_CHECKSUM, bytes(48)), None)
                        connection.sendall(cached_packet[2])
                        continue
                    elif not folder_path.decode("utf-8").startswith(user_name) or not os.path.isdir(complete_folder_path):
                        cached_packet = (False, RSP_DOWNLOAD_FOLDER, create_header(0, RSP_DOWNLOAD_FOLDER, STAT_FAILURE, bytes(48)), None)
                        connection.sendall(cached_packet[2])
                        continue
                    else:
                        if os.path.basename(complete_folder_path):
                            folder_name = os.path.basename(complete_folder_path)
                        else:
                            folder_name = os.path.basename(os.path.split(complete_folder_path)[0])
                        zip_path = os.path.join(basepath, "temp", user_name, folder_name)
                        if os.path.isfile(f"{zip_path}.zip"):
                            os.remove(f"{zip_path}.zip")
                        shutil.make_archive(zip_path, "zip", complete_folder_path)
                        zip_name, zip_size = f"{folder_name}.zip", os.path.getsize(f"{zip_path}.zip")
                        if SEPARATOR in f"{zip_path}.zip":
                            raise ValueError(f"Invalid file name (contains {SEPARATOR})")
                        cached_packet = (True,
                                         RSP_DOWNLOAD_FOLDER,
                                         create_header(zip_size, RSP_DOWNLOAD_FOLDER, STAT_SUCCESS, calc_hash(f"{zip_path}.zip"), (SEPARATOR.join([zip_name, zip_size])).encode("utf-8")),
                                         f"{zip_path}.zip")
                        connection.sendall(cached_packet[2])
                        with open(f"{zip_path}.zip", "rb") as file_to_send:
                            while True:
                                data = file_to_send.read(BUFFER)
                                if not data:
                                    break
                                connection.sendall(data)
                        continue
                else:
                    raise ValueError(f"Invalid packet command ({packet_cmd})")
            elif packet_status == STAT_FILE:
                if packet_cmd == CMD_UPLOAD_FILE and packet_len > 0:
                    file_name, file_size, file_path = packet_secondary_header.decode("utf-8").split(SEPARATOR)
                    file_name = os.path.basename(file_name)
                    complete_file_path = os.path.join(basepath, "users", file_path, file_name)
                    if int(file_size) != packet_len or not os.path.isdir(os.path.join(basepath, "users", file_path)) \
                            or os.path.isfile(complete_file_path):
                        cached_packet = (False, RSP_UPLOAD_FILE, create_header(0, RSP_UPLOAD_FILE, STAT_FAILURE, bytes(48)), None)
                        connection.sendall(cached_packet[2])
                        continue
                    else:
                        current_file_len = 0
                        with open(complete_file_path, "wb") as new_file:
                            while current_file_len < packet_len:
                                file_buffer = connection.recv(min(BUFFER, packet_len - current_file_len))
                                if not file_buffer:
                                    raise ValueError(f"File transfer interrupted (broken file: {complete_file_path})")
                                new_file.write(file_buffer)
                                current_file_len += len(file_buffer)
                    if calc_hash(complete_file_path) != packet_checksum:
                        cached_packet = (False, RSP_UPLOAD_FILE, create_header(0, RSP_UPLOAD_FILE, STAT_INVALID_CHECKSUM, bytes(48)), None)
                        connection.sendall(cached_packet[2])
                        os.remove(complete_file_path)
                        continue
                    else:
                        cached_packet = (False, RSP_UPLOAD_FILE, create_header(0, RSP_UPLOAD_FILE, STAT_SUCCESS, bytes(48)), None)
                        connection.sendall(cached_packet[2])
                        continue
                else:
                    raise ValueError(f"Invalid file transfer command ({packet_cmd})")
            else:
                raise ValueError(f"Invalid packet status ({packet_status})")
    except ConnectionError as e:
        print(f"[SOCKET LOG] Error: {e}")
        connection.close()
    except ValueError as e:
        print(f"[SOCKET LOG] Connection closed for security reasons: {e}")
        connection.close()
    except Exception as e:
        print(f"[SOCKET LOG] Fatal Error: {e}")
        connection.close()


def create_header(msg_len: int, msg_cmd: int, msg_status: int, msg_checksum: bytes, secondary_header: bytes = bytes()) -> bytes:
    assert len(msg_checksum) == 48  # SHA384 hash length
    msg_header = struct.pack("!Q", msg_len) + struct.pack("!H", len(secondary_header)) + struct.pack("!B", msg_cmd) + \
                 struct.pack("!B", msg_status) + msg_checksum
    return msg_header if not secondary_header else (msg_header + secondary_header)


def receive_header(sock: socket.socket) -> tuple[int, int, int, bytes, bytes]:
    raw_header = sock.recv(60)
    if not raw_header:
        raise ConnectionError("Connection closed while receiving packet header")
    secondary_header = bytes()
    secondary_header_len = struct.unpack("!H", raw_header[8:10])[0]
    if secondary_header_len > 0:
        secondary_header = receive_data(sock, secondary_header_len)
    return struct.unpack("!Q", raw_header[:8])[0], raw_header[10], raw_header[11], raw_header[12:], secondary_header


def receive_data(sock: socket.socket, data_len: int) -> bytes:
    if data_len <= BUFFER:
        data = sock.recv(data_len)
        if not data:
            raise ConnectionError("Connection closed during transfer")
        return data
    else:
        data = bytearray()
        while len(data) < data_len:
            packet = sock.recv(min(BUFFER, data_len - len(data)))
            if not packet:
                raise ConnectionError("Connection closed during transfer")
            data.extend(packet)
        return bytes(data)


def send_ack(sock: socket.socket, status: int, cmd: int) -> None:
    sock.sendall(create_header(0, CMD_ACK, status, bytes(47) + struct.pack("!B", cmd)))


def calc_hash(obj: bytes | str) -> bytes:
    hash_object = hashlib.sha384()
    if isinstance(obj, bytes):
        hash_object.update(obj)
        return hash_object.digest()
    elif isinstance(obj, str):
        if not os.path.isfile(obj):
            raise ValueError("The file to be hashed does not exist")
        with open(obj, "rb") as f:
            while True:
                data = f.read(BUFFER)
                if not data:
                    break
                hash_object.update(data)
        return hash_object.digest()
    else:
        raise Exception("The object to be hashed must be of type bytes or a path string")
