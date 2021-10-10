# In this file the repeatedly used HTML pages are stored.
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

class HtmlPages:
    def __init__(self, owner, language):

        # <meta name="viewport" content="width:device-width,initial-scale=1">  # optional
        if language == 'de':
            self.Home = (f'''
            <head>
                <meta charset="utf-8">
                <title>RaspiNAS Anmeldung</title>
            </head>
            <body style="background-color:#59595F">
                <h1 style="font-family:sans-serif; font-size:24px; text-align:center; font-weight:bold; color:black; background-color:#88DD3A; 
                border-radius:10px; margin:16px; margin-bottom:32px; padding:8px; box-shadow:2px 2px 4px #262626">
                    - {owner} RaspiNAS -
                </h1>
                <form action="/home" method="post" style="margin:auto; width:450px; height:250px; background-color:#59595F; 
                border-style:solid; border-color:#3D3D42; border-width:2px; box-shadow:0px 0px 5px #3D3D42">
                    <input name="name" type="text" style="position:relative; left:75px; font-family:sans-serif; font-size:14px; text-align:left; 
                    width:300px; color:black; background-color:white; border-radius:4px; border-style:hidden; margin-top:18px; padding:8px" placeholder="vorname" />
                    <p style="position:relative; left:75px; font-family:sans-serif; font-size:12px; text-align:left; 
                    width:300px; color:black; background-color:#59595F; margin-top:3px; padding:1px">
                        Vorname (Kleinbuchstaben)
                    </p>
                    <input name="pin" type="password" style="position:relative; left:75px; font-family:sans-serif; font-size:14px; text-align:left; 
                    width:300px; color:black; background-color:white; border-radius:4px; border-style:hidden; margin-top:18px; padding:8px" placeholder="nummer" />
                    <p style="position:relative; left:75px; font-family:sans-serif; font-size:12px; text-align:left; 
                    width:300px; color:black; background-color:#59595F; margin-top:3px; padding:1px">
                        Kennnummer
                    </p>
                    <input value="Anmelden" type="submit" style="position:relative; left:150px; font-family:sans-serif; font-size:14px; text-align:center; 
                    width:150px; color:black; background-color:#88DD3A; border-radius:4px; border-style:hidden; margin-top:24px; padding:8px; box-shadow:2px 2px 4px #262626" />
                </form>
            </body>
            ''')

            self.LoginFailed = ('''
            <head>
                <meta charset="utf-8">
                <title>Anmeldung fehlgeschlagen</title>
            </head>
            <body style="background-color:#59595F">
                <p style="margin:auto; font-family:sans-serif; font-size:14px; text-align:center; color:black; 
                background-color:#FF4C4C; border-radius:4px; margin-top:32px; padding:8px; width:400px">
                    Anmeldung fehlgeschlagen: Daten sind nicht korrekt.
                </p>
                <form action="/home" style="margin:auto; width:250px; height:100px; background-color:#59595F">
                    <input value="Wiederholen?" type="submit" style="position:relative; left:50px; font-family:sans-serif; font-size:14px; text-align:center; 
                    width:150px; color:black; background-color:#88DD3A; border-radius:4px; border-style:hidden; margin-top:32px; padding:8px; box-shadow:2px 2px 4px #262626" />
                </form>
            </body>
            ''')

            self.NoDirectory = ('''
            <head>
                <meta charset="utf-8">
                <title>kein Verzeichnis</title>
            </head>
            <body style="background-color:#59595F">
                <p style="margin:auto; font-family:sans-serif; font-size:14px; text-align:center; color:black; 
                background-color:#FF4C4C; border-radius:4px; margin-top:32px; padding:8px; width:400px">
                    Fehler: Das angegebene Verzeichnis existiert nicht.
                </p>
            </body>
            ''')

            self.NoFile = ('''
            <head>
                <meta charset="utf-8">
                <title>keine Datei</title>
            </head>
            <body style="background-color:#59595F">
                <p style="margin:auto; font-family:sans-serif; font-size:14px; text-align:center; color:black; 
                background-color:#FF4C4C; border-radius:4px; margin-top:32px; padding:8px; width:400px">
                    Fehler: Die angegebene Datei existiert nicht.
                </p>
            </body>
            ''')

            self.AccessDenied = ('''
            <head>
                <meta charset="utf-8">
                <title>kein Zugriff</title>
            </head>
            <body style="background-color:#59595F">
                <p style="margin:auto; font-family:sans-serif; font-size:14px; text-align:center; color:black; 
                background-color:#FF4C4C; border-radius:4px; margin-top:32px; padding:8px; width:400px">
                    Zugriff verweigert: Du bist nicht angemeldet.
                </p>
            </body>
            ''')

        else:
            self.Home = (f'''
            <head>
                <meta charset="utf-8">
                <title>RaspiNAS Login</title>
            </head>
            <body style="background-color:#59595F">
                <h1 style="font-family:sans-serif; font-size:24px; text-align:center; font-weight:bold; color:black; background-color:#88DD3A; 
                border-radius:10px; margin:16px; margin-bottom:32px; padding:8px; box-shadow:2px 2px 4px #262626">
                    - {owner} RaspiNAS -
                </h1>
                <form action="/home" method="post" style="margin:auto; width:450px; height:250px; background-color:#59595F; 
                border-style:solid; border-color:#3D3D42; border-width:2px; box-shadow:0px 0px 5px #3D3D42">
                    <input name="name" type="text" style="position:relative; left:75px; font-family:sans-serif; font-size:14px; text-align:left; 
                    width:300px; color:black; background-color:white; border-radius:4px; border-style:hidden; margin-top:18px; padding:8px" placeholder="name" />
                    <p style="position:relative; left:75px; font-family:sans-serif; font-size:12px; text-align:left; 
                    width:300px; color:black; background-color:#59595F; margin-top:3px; padding:1px">
                        Username (lower case letters)
                    </p>
                    <input name="pin" type="password" style="position:relative; left:75px; font-family:sans-serif; font-size:14px; text-align:left; 
                    width:300px; color:black; background-color:white; border-radius:4px; border-style:hidden; margin-top:18px; padding:8px" placeholder="pin" />
                    <p style="position:relative; left:75px; font-family:sans-serif; font-size:12px; text-align:left; 
                    width:300px; color:black; background-color:#59595F; margin-top:3px; padding:1px">
                        Identification number (pin)
                    </p>
                    <input value="Login" type="submit" style="position:relative; left:150px; font-family:sans-serif; font-size:14px; text-align:center; 
                    width:150px; color:black; background-color:#88DD3A; border-radius:4px; border-style:hidden; margin-top:24px; padding:8px; box-shadow:2px 2px 4px #262626" />
                </form>
            </body>
            ''')

            self.LoginFailed = ('''
            <head>
                <meta charset="utf-8">
                <title>Login failed</title>
            </head>
            <body style="background-color:#59595F">
                <p style="margin:auto; font-family:sans-serif; font-size:14px; text-align:center; color:black; 
                background-color:#FF4C4C; border-radius:4px; margin-top:32px; padding:8px; width:400px">
                    Login failed: Your credentials are not correct.
                </p>
                <form action="/home" style="margin:auto; width:250px; height:100px; background-color:#59595F">
                    <input value="Retry?" type="submit" style="position:relative; left:50px; font-family:sans-serif; font-size:14px; text-align:center; 
                    width:150px; color:black; background-color:#88DD3A; border-radius:4px; border-style:hidden; margin-top:32px; padding:8px; box-shadow:2px 2px 4px #262626" />
                </form>
            </body>
            ''')

            self.NoDirectory = ('''
            <head>
                <meta charset="utf-8">
                <title>Directory not found</title>
            </head>
            <body style="background-color:#59595F">
                <p style="margin:auto; font-family:sans-serif; font-size:14px; text-align:center; color:black; 
                background-color:#FF4C4C; border-radius:4px; margin-top:32px; padding:8px; width:400px">
                    Error: The given directory does not exist.
                </p>
            </body>
            ''')

            self.NoFile = ('''
            <head>
                <meta charset="utf-8">
                <title>File not found</title>
            </head>
            <body style="background-color:#59595F">
                <p style="margin:auto; font-family:sans-serif; font-size:14px; text-align:center; color:black; 
                background-color:#FF4C4C; border-radius:4px; margin-top:32px; padding:8px; width:400px">
                    Error: The given file does not exist.
                </p>
            </body>
            ''')

            self.AccessDenied = ('''
            <head>
                <meta charset="utf-8">
                <title>Access denied</title>
            </head>
            <body style="background-color:#59595F">
                <p style="margin:auto; font-family:sans-serif; font-size:14px; text-align:center; color:black; 
                background-color:#FF4C4C; border-radius:4px; margin-top:32px; padding:8px; width:400px">
                    Access denied: You are not logged in.
                </p>
            </body>
            ''')
