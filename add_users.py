# This file creates hashed values from the user credentials and can be used to set up the needed directories.
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

import hashlib
import os
import sys

if not os.path.isfile("usernames.dat"):
    print("The file usernames.dat does not exist. Should it be created now? (y/n)")
    if input() == "y":
        userfile = open("usernames.dat", "w", encoding="utf-8")
        userfile.close()
    else:
        sys.exit()

if not os.path.isfile("userdata.dat"):
    print("The file userdata.dat does not exist. Should it be created now? (y/n)")
    if input() == "y":
        datafile = open("userdata.dat", "w", encoding="utf-8")
        datafile.close()
    else:
        sys.exit()

while True:
    print("\n--- add user ---\n")
    name = input("name: ")
    pin = input("pin: ")
    hashed = hashlib.sha384(str(pin).encode("utf-8") + str(name).encode("utf-8")).hexdigest()
    userfile = open("usernames.dat", "a", encoding="utf-8")
    userfile.write(str(name) + "\n")
    userfile.close()
    datafile = open("userdata.dat", "a", encoding="utf-8")
    datafile.write(hashed + "\n")
    datafile.close()
    print("\nAdd another user? (y/n)")
    if input() != "y":
        break

print("\n\nDo you wish to create the required directories now? (y/n)")
if input() == "y":
    if not os.path.isdir("users"):
        os.mkdir("users")
    if not os.path.isdir("temp"):
        os.mkdir("temp")
    file = open("usernames.dat", "r", encoding="utf-8")
    for line in file.readlines():
        currentName = line.replace("\n", "")
        if not os.path.isdir(f"users/{currentName}"):
            os.mkdir(f"users/{currentName}")
        if not os.path.isdir(f"temp/{currentName}"):
            os.mkdir(f"temp/{currentName}")
    file.close()
    print("\n\nTo save the uploaded files in another directory, move \'temp\' and \'users\' to the respective target directory.")
else:
    pass

print("\n\nDone.")
