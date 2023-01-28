# This file contains the code needed for communication with the frontend which will be released at a later time.
# Copyright (C) 2023  Nico Pieplow (nitrescov)
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
MAX_CMD_SIZE = 2**28  # Max command packet size to be cached in RAM (256 MB)
RETRY_COUNT = 5  # Max number of loop passes before an error is raised (must be a positive integer)
SEPARATOR = "\n"

# Communication Protocol:
# SERVER        CLIENT
#       <------- [CMD]
# [RSP] ------->
#
# To indicate an invalid checksum, a check response is received after each packet sent:
# SENDING DATA                  RECEIVING DATA              SIZE
# Send header                   Receive header              60 Bytes                    |
# Send data                     Receive data                Length specified in header  |
# Receive check response        Send check response         2 Bytes                     V
#
# Header structure:         [ 8 Bytes packet length | 2 Bytes secondary header length | 1 Byte packet command | 1 Byte content type | 48 Bytes SHA384 checksum ]
# Check response structure: [ 1 Byte packet command | 1 Byte validity indicator ]

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

# List of content types
# TYPE_RESERVED = 0x00
TYPE_DATA = 0x01
TYPE_FILE = 0x02
TYPE_FAILURE = 0x03
TYPE_SUCCESS = 0x04

# List of validity indicator states
# CHECK_RESERVED = 0x00
CHECK_VALID = 0x01
CHECK_INVALID = 0x02


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
        assert RETRY_COUNT > 0  # Ensure that the retry count is a positive integer
        assert isinstance(RETRY_COUNT, int)

        # Login phase (executed only once per session)
        for counter in range(RETRY_COUNT):  # Loop for receiving the login data
            packet_len, packet_cmd, packet_type, packet_checksum, packet_secondary_header = receive_header(connection)
            if packet_cmd != CMD_LOGIN or packet_type != TYPE_DATA or not (0 < packet_len <= MAX_CMD_SIZE):
                raise ValueError("No login data received")
            packet_content = receive_data(connection, packet_len)
            if calc_hash(packet_content) == packet_checksum:
                send_check_response(connection, CMD_LOGIN, CHECK_VALID)
                break
            else:
                send_check_response(connection, CMD_LOGIN, CHECK_INVALID)
        if counter >= (RETRY_COUNT - 1):
            raise ValueError(f"Retry count ({RETRY_COUNT}) exceeded")
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
            for counter in range(RETRY_COUNT):  # Loop for sending the login acceptance
                send_header(connection, 0, RSP_LOGIN, TYPE_SUCCESS, bytes(48))
                if receive_check_response(connection, RSP_LOGIN):
                    break
            if counter >= (RETRY_COUNT - 1):
                raise ValueError(f"Retry count ({RETRY_COUNT}) exceeded")
        else:
            for counter in range(RETRY_COUNT):  # Loop for sending the login rejection
                send_header(connection, 0, RSP_LOGIN, TYPE_FAILURE, bytes(48))
                if receive_check_response(connection, RSP_LOGIN):
                    break
            raise ValueError("Invalid login credentials")

        # Command phase (accepting commands in a loop that only breaks if the connection is closed or an error occurs)
        while True:

            for counter in range(RETRY_COUNT):  # Loop for receiving commands
                packet_len, packet_cmd, packet_type, packet_checksum, packet_secondary_header = receive_header(connection)
                if packet_type == TYPE_DATA:
                    if packet_len > MAX_CMD_SIZE:
                        raise ValueError(f"Packet is no file, but larger than the maximum of {MAX_CMD_SIZE // (2 ** 20)} MB")
                    if packet_cmd == CMD_GET_DIRECTORIES and packet_len == 0:
                        packet_content = None
                        send_check_response(connection, CMD_GET_DIRECTORIES, CHECK_VALID)
                        break
                    elif packet_cmd == CMD_DOWNLOAD_FILE and packet_len > 0:
                        packet_content = receive_data(connection, packet_len)
                        if calc_hash(packet_content) == packet_checksum:
                            send_check_response(connection, CMD_DOWNLOAD_FILE, CHECK_VALID)
                            break
                        else:
                            send_check_response(connection, CMD_DOWNLOAD_FILE, CHECK_INVALID)
                            continue
                    elif packet_cmd == CMD_DOWNLOAD_FOLDER and packet_len > 0:
                        packet_content = receive_data(connection, packet_len)
                        if calc_hash(packet_content) == packet_checksum:
                            send_check_response(connection, CMD_DOWNLOAD_FOLDER, CHECK_VALID)
                            break
                        else:
                            send_check_response(connection, CMD_DOWNLOAD_FOLDER, CHECK_INVALID)
                            continue
                    else:
                        raise ValueError(f"Invalid packet command ({packet_cmd}) or length ({packet_len})")
                elif packet_type == TYPE_FILE and packet_secondary_header:
                    if packet_cmd == CMD_UPLOAD_FILE and packet_len > 0:
                        file_name, file_size, file_path = packet_secondary_header.decode("utf-8").split(SEPARATOR)
                        file_name = os.path.basename(file_name)
                        path_to_save = os.path.join(basepath, "users", file_path, file_name)
                        if int(file_size) != packet_len or not file_path.startswith(user_name) \
                                or not os.path.isdir(os.path.join(basepath, "users", file_path)) or os.path.isfile(path_to_save):
                            packet_content = None
                            send_check_response(connection, CMD_UPLOAD_FILE, CHECK_VALID)
                            break
                        else:
                            current_file_len = 0
                            with open(path_to_save, "wb") as new_file:
                                while current_file_len < packet_len:
                                    file_buffer = connection.recv(min(BUFFER, packet_len - current_file_len))
                                    if not file_buffer:
                                        raise Exception(f"File transfer interrupted (broken file: {path_to_save})")
                                    new_file.write(file_buffer)
                                    current_file_len += len(file_buffer)
                            if calc_hash(path_to_save) == packet_checksum:
                                packet_content = path_to_save.encode("utf-8")
                                send_check_response(connection, CMD_UPLOAD_FILE, CHECK_VALID)
                                break
                            else:
                                os.remove(path_to_save)
                                send_check_response(connection, CMD_UPLOAD_FILE, CHECK_INVALID)
                                continue
                    else:
                        raise ValueError(f"Invalid file transfer command ({packet_cmd}) or file size ({packet_len})")
                else:
                    raise ValueError(f"Invalid command packet type ({packet_type})")
            if counter >= (RETRY_COUNT - 1):
                raise ValueError(f"Retry count ({RETRY_COUNT}) exceeded")

            # Process the received data and create responses
            response_len = 0
            response_type = TYPE_FAILURE
            response_checksum = bytes(48)
            response_secondary_header = bytes()

            if packet_cmd == CMD_GET_DIRECTORIES:
                response_cmd = RSP_GET_DIRECTORIES
                folders = list()
                for root, dirs, files in os.walk(os.path.join(basepath, "users", user_name)):
                    folders.append(root.replace(os.path.join(basepath, "users") + "/", ""))
                response_content = ("\n".join(folders)).encode("utf-8")
                response_len = len(response_content)
                response_type = TYPE_DATA
                response_checksum = calc_hash(response_content)

            elif packet_cmd == CMD_DOWNLOAD_FILE:
                response_cmd = RSP_DOWNLOAD_FILE
                response_file = os.path.join(basepath, "users", packet_content.decode("utf-8"))
                if SEPARATOR in response_file:
                    raise ValueError(f"Invalid file name (contains {SEPARATOR})")
                if packet_content.decode("utf-8").startswith(user_name) and os.path.isfile(response_file):
                    response_len = os.path.getsize(response_file)
                    response_type = TYPE_FILE
                    response_checksum = calc_hash(response_file)
                    response_secondary_header = (SEPARATOR.join([os.path.basename(response_file), str(response_len)])).encode("utf-8")

            elif packet_cmd == CMD_DOWNLOAD_FOLDER:
                response_cmd = RSP_DOWNLOAD_FOLDER
                folder_to_compress = os.path.join(basepath, "users", packet_content.decode("utf-8"))
                if packet_content.decode("utf-8").startswith(user_name) and os.path.isdir(folder_to_compress):
                    if os.path.basename(folder_to_compress):
                        folder_name = os.path.basename(folder_to_compress)
                    else:
                        folder_name = os.path.basename(os.path.split(folder_to_compress)[0])
                    response_file = os.path.join(basepath, "temp", user_name, folder_name) + ".zip"
                    if SEPARATOR in response_file:
                        raise ValueError(f"Invalid file name (contains {SEPARATOR})")
                    if os.path.isfile(response_file):
                        os.remove(response_file)
                    shutil.make_archive(response_file[:-4], "zip", folder_to_compress)
                    response_len = os.path.getsize(response_file)
                    response_type = TYPE_FILE
                    response_checksum = calc_hash(response_file)
                    response_secondary_header = (SEPARATOR.join([f"{folder_name}.zip", str(response_len)])).encode("utf-8")

            elif packet_cmd == CMD_UPLOAD_FILE:
                response_cmd = RSP_UPLOAD_FILE
                if packet_content is not None:
                    response_type = TYPE_SUCCESS

            else:
                raise Exception("Invalid command to process. Command changed after receipt.")

            for counter in range(RETRY_COUNT):  # Loop for sending responses
                send_header(connection, response_len, response_cmd, response_type, response_checksum, response_secondary_header)
                if response_len > 0:
                    if response_type == TYPE_DATA:
                        if response_len > MAX_CMD_SIZE:
                            raise ValueError("Packet size overflow")
                        send_data(connection, response_content)
                    elif response_type == TYPE_FILE:
                        with open(response_file, "rb") as file_to_send:
                            while True:
                                raw_data = file_to_send.read(BUFFER)
                                if not raw_data:
                                    break
                                send_data(connection, raw_data)
                    else:
                        raise Exception("Invalid response type defined")
                if receive_check_response(connection, response_cmd):
                    break
            if counter >= (RETRY_COUNT - 1):
                raise ValueError(f"Retry count ({RETRY_COUNT}) exceeded")

    except ConnectionError as e:
        print(f"[SOCKET LOG] Error: {e}")
        connection.close()
    except ValueError as e:
        print(f"[SOCKET LOG] Connection closed for security reasons: {e}")
        connection.close()
    except Exception as e:
        print(f"[SOCKET LOG] Fatal Error: {e}")
        connection.close()


def send_header(sock: socket.socket, msg_len: int, msg_cmd: int, msg_type: int, msg_checksum: bytes, secondary_header: bytes = bytes()) -> None:
    assert len(msg_checksum) == 48  # SHA384 hash length
    msg_header = struct.pack("!Q", msg_len) + struct.pack("!H", len(secondary_header)) + struct.pack("!B", msg_cmd) + \
                 struct.pack("!B", msg_type) + msg_checksum
    sock.sendall(msg_header)
    if secondary_header:
        sock.sendall(secondary_header)


def receive_header(sock: socket.socket) -> tuple[int, int, int, bytes, bytes]:
    raw_header = sock.recv(60)
    if not raw_header:
        raise ConnectionError("Connection closed while receiving packet header")
    secondary_header = bytes()
    secondary_header_len = struct.unpack("!H", raw_header[8:10])[0]
    if secondary_header_len > 0:
        secondary_header = receive_data(sock, secondary_header_len)
    return struct.unpack("!Q", raw_header[:8])[0], raw_header[10], raw_header[11], raw_header[12:], secondary_header


def send_data(sock: socket.socket, data: bytes) -> None:
    sock.sendall(data)


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


def send_check_response(sock: socket.socket, msg_cmd: int, validity_indicator: int) -> None:
    sock.sendall(struct.pack("!B", msg_cmd) + struct.pack("!B", validity_indicator))


def receive_check_response(sock: socket.socket, msg_cmd: int) -> bool:
    raw_response = sock.recv(2)
    if not raw_response:
        raise ConnectionError("Connection closed while receiving check response")
    if raw_response[0] != msg_cmd:
        raise ValueError("Received check response does not match the associated command type")
    return True if raw_response[1] == CHECK_VALID else False


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
