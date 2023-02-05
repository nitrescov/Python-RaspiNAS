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
#       <------- [CDT]      | Optional command data
# [RDT] ------->            | Optional response data
#
# To indicate an invalid checksum, a check response is received after each packet sent:
# SENDING DATA                  RECEIVING DATA              SIZE
# Send header                   Receive header              58 Bytes                    |
# Send data                     Receive data                Length specified in header  |
# Receive check response        Send check response         2 Bytes                     V
#
# Header structure:         [ 8 Bytes packet length | 1 Byte packet command | 1 Byte content type | 48 Bytes SHA384 checksum ]
# Check response structure: [ 1 Byte packet command | 1 Byte validity indicator ]
#
# Packet command structure: [ 1 Bit additional data indicator | 1 Bit response indicator | 6 Bits command type ]

# List of commands and related data (CMDs are expandable up to 0x3f (63), the other command types are calculated depending on them)
CMD_LOGIN = 0x00
CMD_GET_DIRECTORIES = 0x01
CMD_UPLOAD_FILE = 0x02
CMD_DOWNLOAD_FILE = 0x03
CMD_DOWNLOAD_FOLDER = 0x04

CDT_UPLOAD_FILE = CMD_UPLOAD_FILE | (1 << 7)

# List of responses and related data
RSP_LOGIN = CMD_LOGIN | (1 << 6)
RSP_GET_DIRECTORIES = CMD_GET_DIRECTORIES | (1 << 6)
RSP_UPLOAD_FILE = CMD_UPLOAD_FILE | (1 << 6)
RSP_DOWNLOAD_FILE = CMD_DOWNLOAD_FILE | (1 << 6)
RSP_DOWNLOAD_FOLDER = CMD_DOWNLOAD_FOLDER | (1 << 6)

RDT_UPLOAD_FILE = CMD_UPLOAD_FILE | (1 << 6) | (1 << 7)

# List of content types
TYPE_NONE = 0x00
TYPE_DATA = 0x01
TYPE_FILE = 0x02
TYPE_FAILURE = 0x03
TYPE_SUCCESS = 0x04

# List of validity indicator states
CHECK_INVALID = 0x00
CHECK_VALID = 0x01


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
            packet_len, packet_cmd, packet_type, packet_checksum = receive_header(connection)
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

            pending_data = False
            for counter in range(RETRY_COUNT):  # Loop for receiving commands
                packet_len, packet_cmd, packet_type, packet_checksum = receive_header(connection)
                if packet_type == TYPE_NONE and packet_len == 0:
                    packet_content = None
                    if packet_cmd in [CMD_GET_DIRECTORIES]:
                        send_check_response(connection, packet_cmd, CHECK_VALID)
                        break
                    else:
                        raise ValueError(f"Invalid packet command ({packet_cmd})")
                elif packet_type == TYPE_DATA and packet_len > 0:
                    if packet_len > MAX_CMD_SIZE:
                        raise ValueError(f"Packet is no file, but larger than the maximum of {MAX_CMD_SIZE // (2 ** 20)} MB")
                    packet_content = receive_data(connection, packet_len)
                    if packet_cmd in [CMD_UPLOAD_FILE, CMD_DOWNLOAD_FILE, CMD_DOWNLOAD_FOLDER]:
                        if calc_hash(packet_content) == packet_checksum:
                            send_check_response(connection, packet_cmd, CHECK_VALID)
                            break
                        else:
                            send_check_response(connection, packet_cmd, CHECK_INVALID)
                            continue
                    else:
                        raise ValueError(f"Invalid packet command ({packet_cmd})")
                else:
                    raise ValueError(f"Invalid command packet type ({packet_type}) or inappropriate length ({packet_len})")
            if counter >= (RETRY_COUNT - 1):
                raise ValueError(f"Retry count ({RETRY_COUNT}) exceeded")

            # Process the received data and create responses
            response_len, response_cmd, response_type, response_checksum = 0, 0, 0, bytes(48)
            response_content, file_name, file_path = None, None, None

            if packet_cmd == CMD_GET_DIRECTORIES:
                response_cmd = RSP_GET_DIRECTORIES
                response_type = TYPE_DATA
                folders = list()
                for root, dirs, files in os.walk(os.path.join(basepath, "users", user_name)):
                    folders.append(root.replace(os.path.join(basepath, "users") + "/", ""))
                response_content = ("\n".join(folders)).encode("utf-8")
                response_len = len(response_content)
                response_checksum = calc_hash(response_content)

            elif packet_cmd == CMD_UPLOAD_FILE:
                response_cmd = RSP_UPLOAD_FILE
                target_name, target_path = packet_content.decode("utf-8").split(SEPARATOR)
                file_path = os.path.join(basepath, "users", target_path)
                file_name = os.path.join(basepath, "users", target_path, os.path.basename(target_name))
                if not target_path.startswith(user_name) or not os.path.isdir(file_path) or os.path.isfile(file_name):
                    response_type = TYPE_FAILURE
                else:
                    response_type = TYPE_SUCCESS
                    pending_data = True

            elif packet_cmd == CMD_DOWNLOAD_FILE:
                response_cmd = RSP_DOWNLOAD_FILE
                file_name = os.path.join(basepath, "users", packet_content.decode("utf-8"))
                if SEPARATOR in file_name:
                    raise ValueError(f"Invalid file name (contains {SEPARATOR})")
                if not packet_content.decode("utf-8").startswith(user_name) or not os.path.isfile(file_name):
                    response_type = TYPE_FAILURE
                else:
                    response_len = os.path.getsize(file_name)
                    response_type = TYPE_FILE
                    response_checksum = calc_hash(file_name)

            elif packet_cmd == CMD_DOWNLOAD_FOLDER:
                response_cmd = RSP_DOWNLOAD_FOLDER
                dir_path = os.path.join(basepath, "users", packet_content.decode("utf-8"))
                if not packet_content.decode("utf-8").startswith(user_name) or not os.path.isdir(dir_path):
                    response_type = TYPE_FAILURE
                else:
                    if os.path.basename(dir_path):
                        folder_name = os.path.basename(dir_path)
                    else:
                        folder_name = os.path.basename(os.path.split(dir_path)[0])
                    file_name = os.path.join(basepath, "temp", user_name, folder_name) + ".zip"
                    if SEPARATOR in file_name:
                        raise ValueError(f"Invalid file name (contains {SEPARATOR})")
                    if os.path.isfile(file_name):
                        os.remove(file_name)
                    shutil.make_archive(file_name[:-4], "zip", dir_path)
                    response_len = os.path.getsize(file_name)
                    response_type = TYPE_FILE
                    response_checksum = calc_hash(file_name)

            else:
                raise Exception("Invalid command to process. Command changed after receipt.")

            for counter in range(RETRY_COUNT):  # Loop for sending responses
                send_header(connection, response_len, response_cmd, response_type, response_checksum)
                if response_len > 0:
                    if response_type == TYPE_DATA:
                        if response_len > MAX_CMD_SIZE:
                            raise ValueError("Packet size overflow")
                        send_data(connection, response_content)
                    elif response_type == TYPE_FILE:
                        with open(file_name, "rb") as file_to_send:
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

            if pending_data:
                for counter in range(RETRY_COUNT):  # Loop for receiving additional data
                    packet_len, packet_cmd, packet_type, packet_checksum = receive_header(connection)
                    if packet_type == TYPE_FILE and packet_len > 0:
                        if packet_cmd in [CDT_UPLOAD_FILE]:
                            current_len = 0
                            with open(file_name, "wb") as new_file:
                                while current_len < packet_len:
                                    file_buffer = connection.recv(min(BUFFER, packet_len - current_len))
                                    if not file_buffer:
                                        raise Exception(f"File transfer interrupted (broken file: {file_name})")
                                    new_file.write(file_buffer)
                                    current_len += len(file_buffer)
                            if calc_hash(file_name) == packet_checksum:
                                send_check_response(connection, packet_cmd, CHECK_VALID)
                                break
                            else:
                                os.remove(file_name)
                                send_check_response(connection, packet_cmd, CHECK_INVALID)
                                continue
                        else:
                            raise ValueError(f"Invalid packet command ({packet_cmd})")
                    else:
                        raise ValueError(f"Invalid data packet type ({packet_type}) or inappropriate length ({packet_len})")
                if counter >= (RETRY_COUNT - 1):
                    raise ValueError(f"Retry count ({RETRY_COUNT}) exceeded")

                # Process the received data and create responses
                response_len, response_cmd, response_type, response_checksum = 0, 0, 0, bytes(48)

                if packet_cmd == CDT_UPLOAD_FILE:
                    response_cmd = RDT_UPLOAD_FILE
                    response_type = TYPE_SUCCESS

                else:
                    raise Exception("Invalid command to process. Command changed after receipt.")

                for counter in range(RETRY_COUNT):  # Loop for sending responses
                    send_header(connection, response_len, response_cmd, response_type, response_checksum)
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


def send_header(sock: socket.socket, msg_len: int, msg_cmd: int, msg_type: int, msg_checksum: bytes) -> None:
    assert len(msg_checksum) == 48  # SHA384 hash length
    sock.sendall(struct.pack("!Q", msg_len) + struct.pack("!B", msg_cmd) + struct.pack("!B", msg_type) + msg_checksum)


def receive_header(sock: socket.socket) -> tuple[int, int, int, bytes]:
    raw_header = sock.recv(58)
    if not raw_header:
        raise ConnectionError("Connection closed while receiving packet header")
    return struct.unpack("!Q", raw_header[:8])[0], raw_header[8], raw_header[9], raw_header[10:]


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
