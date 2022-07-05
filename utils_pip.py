# SPDX-License-Identifier: GPL-2.0-or-later

# ##### BEGIN GPL LICENSE BLOCK #####
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software Foundation,
#  Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
# ##### END GPL LICENSE BLOCK #####

# <pep8 compliant>

# ----------------------------------------------------------
# Author: Stephen Leger (s-leger)
#
# ----------------------------------------------------------
import bpy
import subprocess
import sys


PYPATH = sys.executable #bpy.app.binary_path_python


class Pip:

    def __init__(self):
        self._ensurepip()

    @staticmethod
    def _ensure_user_site_package():
        import os
        import site
        import sys
        site_package = site.getusersitepackages()
        if not os.path.exists(site_package):
            site_package = bpy.utils.user_resource('SCRIPTS', path="site_package", create=True)
            site.addsitedir(site_package)
        if site_package not in sys.path:
            sys.path.append(site_package)
    '''
    @staticmethod
    def _ensure_user_site_package():
        import os
        import site
        import sys
        site_package = site.getusersitepackages()
        if os.path.exists(site_package):
            if site_package not in sys.path:
                sys.path.append(site_package)
        else:
            site_package = bpy.utils.user_resource('SCRIPTS', "site_package", create=True)
            site.addsitedir(site_package)
    '''
    def _cmd(self, action, options, module):
        if options is not None and "--user" in options:
            self._ensure_user_site_package()

        cmd = [PYPATH, "-m", "pip", action]

        if options is not None:
            cmd.extend(options.split(" "))

        cmd.append(module)
        return self._run(cmd)

    def _popen(self, cmd):
        popen = subprocess.Popen(cmd, stdout=subprocess.PIPE, universal_newlines=True)
        for stdout_line in iter(popen.stdout.readline, ""):
            yield stdout_line
        popen.stdout.close()
        popen.wait()

    def _run(self, cmd):
        res = False
        status = ""
        for line in self._popen(cmd):
            if "ERROR:" in line:
                status = line.strip()
            if "Error:" in line:
                status = line.strip()
            print(line)
            if "Successfully" in line:
                status = line.strip()
                res = True
        return res, status

    def _ensurepip(self):
        pip_not_found = False
        try:
            import pip
        except ImportError:
            pip_not_found = True
            pass
        if pip_not_found:
            self._run([PYPATH, "-m", "ensurepip", "--default-pip"])

    @staticmethod
    def upgrade_pip():
        return Pip()._cmd("install", "--upgrade", "pip")

    @staticmethod
    def uninstall(module, options=None):
        """
        :param module: string module name with requirements see:[1]
        :param options: string command line options  see:[2]
        :return: True on uninstall, False if already removed, raise on Error
        [1] https://pip.pypa.io/en/stable/reference/pip_install/#id29
        [2] https://pip.pypa.io/en/stable/reference/pip_install/#id47
        """
        if options is None or options.strip() == "":
            # force confirm
            options = "-y"
        return Pip()._cmd("uninstall", options, module)

    @staticmethod
    def install(module, options=None):
        """
        :param module: string module name with requirements see:[1]
        :param options: string command line options  see:[2]
        :return: True on install, False if already there, raise on Error
        [1] https://pip.pypa.io/en/stable/reference/pip_install/#id29
        [2] https://pip.pypa.io/en/stable/reference/pip_install/#id47
        """
        if options is None or options.strip() == "":
            # store in user writable directory, use wheel, without deps
            options = "--user --only-binary all --no-deps"
        return Pip()._cmd("install", options, module)

    @staticmethod
    def blender_version():
        """
        :return: blender version tuple
        """
        return bpy.app.version

    @staticmethod
    def python_version():
        """
        :return: python version object
        """
        import sys
        # version.major, version.minor, version.micro
        return sys.version_info
