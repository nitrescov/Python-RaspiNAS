# This is the main file. It's designed for deployment on a (NAS-)Server.
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

# Currently recommended Python version: 3.10.4

import os
import paste
import random
import bottle
import shutil
import hashlib
import threading
import receiver
from html_pages import HtmlPages

# import cherrypy  # (100MB upload limit)
# import subprocess  # alternative to shutil

# ----- Server configuration and personalization: ---------------------------------------

LANGUAGE = 'en'  # 'en' for English, 'de' for German (Deutsch)
HOSTIP = '0.0.0.0'  # 'localhost' for test purposes, '0.0.0.0' listens anywhere
PORT = 80  # default HTTP port 80
OWNER = ''  # insert a name here to personalize the webapp (e.g. 'John Doe')
VERSION = '1.1.2'  # rework of the socket receiver file (2022/05/07)
ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz1234567890()+,.-_ "  # used to define allowed characters in directory names
HTML = HtmlPages(OWNER, LANGUAGE)  # import repeatedly used HTML pages (to keep this file short and clear)

# ----- Beginning of the main functions: ------------------------------------------------
#
# __ Load usernames and userdata: __
names = open("usernames.dat", "r", encoding="utf-8")
USERNAMES = names.readlines()
for entry in range(len(USERNAMES)):
    USERNAMES[entry] = USERNAMES[entry].replace("\n", "")
names.close()
data = open("userdata.dat", "r", encoding="utf-8")
USERDATA = data.readlines()
for entry in range(len(USERDATA)):
    USERDATA[entry] = USERDATA[entry].replace("\n", "")
data.close()
#
# __ Increase allowed file size of uploads: __
bottle.BaseRequest.MEMFILE_MAX = 32 * 1024 * 1024
#
# __ Create random cookie-secret: __
SECRET = ''
SECRET_ALPHABET = "abcdefghijklmnopqrstuvwxyz1234567890"
for i in range(64):
    SECRET += SECRET_ALPHABET[random.randint(0, len(SECRET_ALPHABET) - 1)]
#
# __ Initialization of the bottle webapp: __
webapp = bottle.app()


@webapp.route('/')
def to_home():
    bottle.redirect('/home')


@webapp.route('/home')
def home():
    return HTML.Home


@webapp.route('/home', method='POST')
def login():
    name = bottle.request.forms.get('name')
    pin = bottle.request.forms.get('pin')
    hashed = hashlib.sha224(str(pin).encode('utf-8') + str(name).encode('utf-8')).hexdigest()
    login_successful = False
    for item in USERDATA:
        if item == hashed:
            login_successful = True
            break
    if login_successful:
        bottle.response.set_cookie("user", hashed, secret=SECRET)
        bottle.redirect(f'/files/{str(name)}')
    else:
        return HTML.LoginFailed


@webapp.route('/files/<directory:path>')
def list_directory(directory):
    user = check_login()
    if user:
        folder_path = str(directory)
        prior_path = '/'.join(folder_path.split('/')[:-1])
        if prior_path == '':
            prior_path = '/home'
        else:
            prior_path = ('/files/' + prior_path)
        username = folder_path.split('/')[0]
        for position in range(len(USERNAMES)):
            if username == USERNAMES[position] and user == (position + 1):
                files = []
                folders = []
                folder_list = ""
                file_list = ""
                if os.path.isdir(f'users/{folder_path}'):
                    for (pth, fol, dat) in os.walk(f'users/{folder_path}'):
                        folders.extend(fol)
                        files.extend(dat)
                        break
                    folders.sort(key=str.lower)
                    files.sort(key=str.lower)
                    delete_dir_confirm = 'The directory will be deleted permanently. Continue?'
                    if LANGUAGE == 'de':
                        delete_dir_confirm = 'Soll der Ordner wirklich endgültig gelöscht werden?'
                    for folder in folders:
                        folder_list = folder_list + \
                                (f'<div style="text-align:center; background-color:#59595F; font-size:16px; font-family:sans-serif">'
                                 f'<a href="/files/{folder_path}/{folder}" style="text-decoration:none">'
                                 f'<div style="width:500px; display:inline-block; text-align:left; color:white; border-bottom-style:solid; '
                                 f'border-width:1px; border-color:#787878; padding:8px; vertical-align:middle">'
                                 f'<img src="/icons/folder_32x32.png" style="vertical-align:middle"/>'
                                 f'<span style="vertical-align:middle; margin-left:16px">{folder}'
                                 f'</span></div></a>'
                                 f'<a href="/deletedir/{folder_path}/{folder}" onclick="return confirm(\'{delete_dir_confirm}\');" style="text-decoration:none">'
                                 f'<div style="width:20px; padding:8px; margin-left:8px; display:inline-block; vertical-align:middle">'
                                 f'<img src="/icons/trash_16x16.png"/>'
                                 f'</div></a></div>')
                    delete_file_confirm = 'The file will be deleted permanently. Continue?'
                    if LANGUAGE == 'de':
                        delete_file_confirm = 'Soll die Datei wirklich endgültig gelöscht werden?'
                    for file in files:
                        file_extension = str(file).split('.')[-1]
                        file_type = 'file'
                        if file_extension.lower() in ["png", "bmp", "jpg", "jpeg", "gif", "tga", "dds", "heic", "webp"]:
                            file_type = 'image'
                        elif file_extension.lower() in ["zip", "tar", "7z", "gz", "deb", "rpm"]:
                            file_type = 'zip_folder'
                        elif file_extension.lower() in ["mkv", "webm", "flv", "avi", "mov", "wmv", "mp4", "m4v"]:
                            file_type = 'video'
                        elif file_extension.lower() in ["pdf"]:
                            file_type = 'pdf'
                        elif file_extension.lower() in ["aac", "mp3", "m4a", "acc", "wav", "wma", "ogg", "flac", "aiff", "alac", "dsd", "mqa", "opus"]:
                            file_type = 'music'
                        else:
                            pass
                        file_list = file_list + \
                                (f'<div style="text-align:center; background-color:#59595F; font-size:16px; font-family:sans-serif">'
                                 f'<a href="/download/{folder_path}/{file}" style="text-decoration:none">'
                                 f'<div style="width:500px; display:inline-block; text-align:left; color:white; border-bottom-style:solid; '
                                 f'border-width:1px; border-color:#787878; padding:8px; vertical-align:middle">'
                                 f'<img src="/icons/{file_type}_32x32.png" style="vertical-align:middle"/>'
                                 f'<span style="vertical-align:middle; margin-left:16px">{file}'
                                 f'</span></div></a>'
                                 f'<a href="/deletefile/{folder_path}/{file}" onclick="return confirm(\'{delete_file_confirm}\');" style="text-decoration:none">'
                                 f'<div style="width:20px; padding:8px; margin-left:8px; display:inline-block; vertical-align:middle">'
                                 f'<img src="/icons/trash_16x16.png"/>'
                                 f'</div></a></div>')
                    menu_buttons = ['Back to homepage', 'One page back', 'Download folder (zip)',
                                    'Create directory', 'Unpack zip file here', 'Upload file']
                    menu_placeholders = ['folder name', 'file.zip']
                    if LANGUAGE == 'de':
                        menu_buttons = ['zur Hauptseite', 'eine Seite zurück', 'Ordner herunterladen (zip)',
                                        'Ordner erstellen', 'zip-Datei hier entpacken', 'Datei hochladen']
                        menu_placeholders = ['Ordnername', 'Dateiname.zip']
                    menubar = (f'<div style="text-align:center; font-family:sans-serif; font-size:16px">'
                               f'<a href="/files/{username}" style="text-decoration:none">'
                               f'<div style="width:225px; margin:6px; color:black; padding:8px; border-bottom-style:solid; border-right-style:solid; '
                               f'border-width:1px; border-color:black; display:inline-block; background-color:#787878; text-align:left; vertical-align:top">'
                               f'<img src="/icons/home_16x16.png" style="vertical-align:middle"/>'
                               f'<span style="vertical-align:middle; margin-left:12px">{menu_buttons[0]}'
                               f'</span></div></a>'
                               f'<a href="{prior_path}" style="text-decoration:none">'
                               f'<div style="width:225px; margin:6px; color:black; padding:8px; border-bottom-style:solid; border-right-style:solid; '
                               f'border-width:1px; border-color:black; display:inline-block; background-color:#787878; text-align:left; vertical-align:top">'
                               f'<img src="/icons/back_16x16.png" style="vertical-align:middle"/>'
                               f'<span style="vertical-align:middle; margin-left:12px">{menu_buttons[1]}'
                               f'</span></div></a>'
                               f'<a href="/zip/{folder_path}" style="text-decoration:none">'
                               f'<div style="width:225px; margin:6px; color:black; padding:8px; border-bottom-style:solid; border-right-style:solid; '
                               f'border-width:1px; border-color:black; display:inline-block; background-color:#787878; text-align:left; vertical-align:top">'
                               f'<img src="/icons/download_16x16.png" style="vertical-align:middle"/>'
                               f'<span style="vertical-align:middle; margin-left:12px">{menu_buttons[2]}'
                               f'</span></div></a></div>'
                               f'<div style="text-align:center; font-family:sans-serif; font-size:16px">'
                               f'<form action="/newfolder/{folder_path}" method="post" style="width:242px; margin:6px; display:inline-block; vertical-align:top">'
                               f'<input value="{menu_buttons[3]}" type="submit" style="width:242px; background:#787878 url(\'/icons/folder_16x16.png\') no-repeat scroll 8px; '
                               f'font-family:sans-serif; font-size:16px; padding:8px; padding-left:36px; color:black; border-bottom-style:solid; border-right-style:solid; border-width:1px; '
                               f'border-top-style:none; border-left-style:none; border-color:black; cursor:pointer; text-align:left" />'
                               f'<input name="foldername" type="text" style="border-radius:4px; border-style:hidden; padding:7px; width:242px; background-color:#D8D8D8; '
                               f'font-family:sans-serif; font-size:14px; margin-top:8px" placeholder="{menu_placeholders[0]}" required />'
                               f'</form>'
                               f'<form action="/unpack/{folder_path}" method="post" style="width:242px; margin:6px; display:inline-block; vertical-align:top">'
                               f'<input value="{menu_buttons[4]}" type="submit" style="width:242px; background:#787878 url(\'/icons/zip_16x16.png\') no-repeat scroll 8px; '
                               f'font-family:sans-serif; font-size:16px; padding:8px; padding-left:36px; color:black; border-bottom-style:solid; border-right-style:solid; border-width:1px; '
                               f'border-top-style:none; border-left-style:none; border-color:black; cursor:pointer; text-align:left" />'
                               f'<input name="zipfilename" type="text" style="border-radius:4px; border-style:hidden; padding:7px; width:242px; background-color:#D8D8D8; '
                               f'font-family:sans-serif; font-size:14px; margin-top:8px" placeholder="{menu_placeholders[1]}" required />'
                               f'</form>'
                               f'<form action="/upload/{folder_path}" method="post" style="width:242px; margin:6px; display:inline-block; vertical-align:top" enctype="multipart/form-data">'
                               f'<input value="{menu_buttons[5]}" type="submit" style="width:242px; background:#787878 url(\'/icons/upload_16x16.png\') no-repeat scroll 8px; '
                               f'font-family:sans-serif; font-size:16px; padding:8px; padding-left:36px; color:black; border-bottom-style:solid; border-right-style:solid; border-width:1px; '
                               f'border-top-style:none; border-left-style:none; border-color:black; cursor:pointer; text-align:left" />'
                               f'<input name="filename" type="file" style="border-radius:4px; border-style:hidden; padding:4px; width:242px; background-color:#D8D8D8; '
                               f'font-family:sans-serif; font-size:14px; margin-top:8px" required />'
                               f'</form></div>')

                    show_path = ""
                    if len(folder_path.split('/')) > 1:
                        show_path = (' / '.join(folder_path.split('/')[1:])) + " / "
                    header_language = [f'{username}\'s files', 'files', 'folder(s)', 'file(s)', 'version']
                    if LANGUAGE == 'de':
                        header_language = [f'Dateien von {username}', 'Dateien', 'Ordner', 'Dateien', 'Version']
                    return f'''
                        <head>
                            <meta charset="utf-8">
                            <title>{header_language[0]}</title>
                        </head>
                        <body style="background-color:#59595F">
                            <h1 style="font-family:sans-serif; font-size:24px; text-align:center; font-weight:bold; color:black; background-color:#88DD3A; 
                            border-radius:10px; margin:16px; margin-bottom:32px; padding:8px; box-shadow:2px 2px 4px #262626">
                                ~ / {header_language[1]} / {show_path}...
                            </h1>
                            {menubar}<br>
                            {folder_list}<br><br>
                            {file_list}<br><br>
                            <p style="margin:auto; font-family:sans-serif; font-size:16px; text-align:center; color:white">
                                {len(folders)} {header_language[2]}, {len(files)} {header_language[3]}
                            </p><br><br><br>
                            <p style="margin:auto; font-family:sans-serif; font-size:12px; text-align:center; color:#787878; border-top-style:solid; 
                            border-color:#787878; border-width:1px; width:250px; padding:10px">
                                - {OWNER} RaspiNAS {header_language[4]} {VERSION} -
                            </p>
                        </body>
                    '''
                else:
                    return HTML.NoDirectory
    return HTML.AccessDenied


@webapp.route('/download/<filepath:path>')
def download_file(filepath):
    user = check_login()
    if user:
        username = str(filepath).split('/')[0]
        file = str(filepath).split('/')[-1]
        directory = '/'.join(str(filepath).split('/')[:-1])
        for position in range(len(USERNAMES)):
            if username == USERNAMES[position] and user == (position + 1):
                return bottle.static_file(file, root='users/' + directory, download=file)
    return HTML.AccessDenied


@webapp.route('/zip/<zippath:path>')
def download_zip(zippath):
    user = check_login()
    if user:
        directory = str(zippath)
        username = directory.split('/')[0]
        folder_name = directory.split('/')[-1]
        for position in range(len(USERNAMES)):
            if username == USERNAMES[position] and user == (position + 1):
                if os.path.isfile(f'temp/{username}/{folder_name}.zip'):
                    os.remove(f'temp/{username}/{folder_name}.zip')
                shutil.make_archive(f'temp/{username}/{folder_name}', 'zip', f'users/{directory}')
                # subprocess.run(f"zip -r ./temp/{username}/{folder_name}.zip ./users/{directory}/", shell=True, stdout=subprocess.DEVNULL)
                return bottle.static_file(f'{folder_name}.zip', root=f'temp/{username}', download=f'{folder_name}.zip')
    return HTML.AccessDenied


@webapp.route('/deletedir/<deldirectorypath:path>')
def delete_directory(deldirectorypath):
    user = check_login()
    if user:
        directory = str(deldirectorypath)
        prior_folder = '/'.join(directory.split('/')[:-1])
        username = directory.split('/')[0]
        if len(directory.split('/')) < 2:
            bottle.redirect(f'/files/{directory}')
            return
        for position in range(len(USERNAMES)):
            if username == USERNAMES[position] and user == (position + 1):
                if os.path.isdir(f'users/{directory}'):
                    shutil.rmtree(f'users/{directory}')
                    # subprocess.run(f"rm -rf users/{directory}", shell=True, stdout=subprocess.DEVNULL)
                    bottle.redirect(f'/files/{prior_folder}')
                else:
                    return HTML.NoDirectory
    return HTML.AccessDenied


@webapp.route('/deletefile/<delfilepath:path>')
def delete_file(delfilepath):
    user = check_login()
    if user:
        filepath = str(delfilepath)
        folder = '/'.join(filepath.split('/')[:-1])
        username = filepath.split('/')[0]
        for position in range(len(USERNAMES)):
            if username == USERNAMES[position] and user == (position + 1):
                if os.path.isfile(f'users/{filepath}'):
                    os.remove(f'users/{filepath}')
                    bottle.redirect(f'/files/{folder}')
                else:
                    return HTML.NoFile
    return HTML.AccessDenied


@webapp.route('/newfolder/<parentpath:path>', method='POST')
def create_directory(parentpath):
    user = check_login()
    if user:
        new_folder = str(bottle.request.forms.get('foldername'))
        directory = str(parentpath)
        username = directory.split('/')[0]
        for position in range(len(USERNAMES)):
            if username == USERNAMES[position] and user == (position + 1):
                #
                # delete illegal characters from folder name:
                deletion_list = []
                for character in new_folder:
                    if not (character in ALPHABET):
                        deletion_list.append(character)
                for item in deletion_list:
                    new_folder = new_folder.replace(item, '')
                if len(new_folder) == 0 or len(new_folder) == new_folder.count(' '):
                    new_folder = 'new_folder'
                #
                if not os.path.isdir(f'users/{directory}/{new_folder}'):
                    os.mkdir(f'users/{directory}/{new_folder}')
                bottle.redirect(f'/files/{directory}')
    return HTML.AccessDenied


@webapp.route('/unpack/<ziptarget:path>', method='POST')
def unpack_zipfile(ziptarget):
    user = check_login()
    if user:
        zipfile = str(bottle.request.forms.get('zipfilename'))
        folder_name = '.'.join(zipfile.split('.')[:-1])
        target_folder = str(ziptarget)
        username = target_folder.split('/')[0]
        for position in range(len(USERNAMES)):
            if username == USERNAMES[position] and user == (position + 1):
                if os.path.isfile(f'users/{target_folder}/{zipfile}') and \
                        not os.path.isdir(f'users/{target_folder}/{folder_name}') and \
                        zipfile.split('.')[-1] == 'zip':
                    os.mkdir(f'users/{target_folder}/{folder_name}')
                    shutil.unpack_archive(f'users/{target_folder}/{zipfile}', f'users/{target_folder}/{folder_name}', 'zip')
                    # subprocess.run(f"unzip ./users/{target_folder}/{zipfile} -d ./users/{target_folder}/{folder_name}", shell=True, stdout=subprocess.DEVNULL)
                    bottle.redirect(f'/files/{target_folder}/{folder_name}')
                else:
                    error_language = ['Unpacking failed', 'Error: The given file does not exist or the target directory is not empty.', 'Back']
                    if LANGUAGE == 'de':
                        error_language = ['Entpacken fehlgeschlagen', 'Fehler: die angegebene Datei existiert nicht oder das Zielverzeichnis ist nicht leer.', 'Zurück']
                    return f'''
                        <head>
                            <meta charset="utf-8">
                            <title>{error_language[0]}</title>
                        </head>
                        <body style="background-color:#59595F">
                            <p style="margin:auto; font-family:sans-serif; font-size:14px; text-align:center; color:black; 
                            background-color:#FF4C4C; border-radius:4px; margin-top:32px; padding:8px; width:400px">
                                {error_language[1]}
                            </p>
                            <form action="/files/{target_folder}" style="margin:auto; width:250px; height:100px; background-color:#59595F">
                                <input value="{error_language[2]}" type="submit" style="position:relative; left:50px; font-family:sans-serif; font-size:14px; text-align:center; width:150px; 
                                color:black; background-color:#88DD3A; border-radius:4px; border-style:hidden; margin-top:32px; padding:8px; box-shadow:2px 2px 4px #262626" />
                            </form>
                        </body>
                    '''
    return HTML.AccessDenied


@webapp.route('/upload/<targetpath:path>', method='POST')
def upload_file(targetpath):
    user = check_login()
    if user:
        target_folder = str(targetpath)
        username = target_folder.split('/')[0]
        for position in range(len(USERNAMES)):
            if username == USERNAMES[position] and user == (position + 1):
                new_file = bottle.request.files.get('filename')
                copy_count = 0
                while os.path.isfile(f'users/{target_folder}/{new_file.filename}'):
                    copy_count += 1
                    name_parts = new_file.filename.split('.')
                    if copy_count > 1:
                        name_parts[-2] = name_parts[-2][:-3]
                    name_parts[-2] = name_parts[-2] + f"({copy_count})"
                    new_file.filename = '.'.join(name_parts)
                new_file.save(f'users/{target_folder}')
                bottle.redirect(f'/files/{target_folder}')
    return HTML.AccessDenied


@webapp.route('/icons/<image>')
def get_icon(image):
    return bottle.static_file(image, root='icons')


def check_login():
    hashed_credentials = bottle.request.get_cookie("user", secret=SECRET)
    if hashed_credentials:
        for position in range(len(USERDATA)):
            if hashed_credentials == USERDATA[position]:
                return position + 1
    return 0


def background_task():
    while True:
        thread_wait.wait(1800)
        for name in USERNAMES:
            for temp_file in os.listdir(f'temp/{name}'):
                os.remove(f'temp/{name}/{temp_file}')


def start_receiver():
    receiver.socket_server(HOSTIP, 5001, USERNAMES, USERDATA)


#
# __ Start garbage-collector thread: __
thread_wait = threading.Event()
background_thread = threading.Thread(target=background_task, daemon=True)
background_thread.start()
#
# __ Start gui server to receive data from the frontend: __
receiver_thread = threading.Thread(target=start_receiver, daemon=True)
receiver_thread.start()
#
# __ Start the webserver: __
# cherrypy.tree.graft(webapp, '/')
# cherrypy.config.update({'server.socket_host': '0.0.0.0',
#                         'server.socket_port': 80,
#                         'engine.autoreload.on': False,
#                         })
# cherrypy.engine.start()
bottle.run(webapp, server='paste', host=HOSTIP, port=PORT)
