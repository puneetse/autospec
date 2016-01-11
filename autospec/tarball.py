#!/usr/bin/true
#
# tarball.py - part of autospec
# Copyright (C) 2015 Intel Corporation
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

import build
import buildpattern
import buildreq
import files
import glob
import hashlib
import os
import re
import shutil
import subprocess
import urllib
import urllib.request
from util import call

name = ""
rawname = ""
version = ""
release = "1"
url = ""
path = ""
tarball_prefix = ""
gcov_file = ""


def get_sha1sum(filename):
    sh = hashlib.sha1()
    with open(filename, "rb") as f:
        sh.update(f.read())
    return sh.hexdigest()


def really_download(url, destination, tarfile):
    with urllib.request.urlopen(url) as response:
        with open(destination, "wb") as dfile:
            dfile.write(response.read())


def check_or_get_file(url, tarfile):
    tarball_path = build.download_path + "/" + tarfile
    if not os.path.isfile(tarball_path):
        really_download(url, tarball_path, tarfile)
    return tarball_path


def build_untar(tarball_path):
    tarball_contents = subprocess.check_output(
        ["tar", "-tf", tarball_path], universal_newlines=True)
    extract_cmd = "tar --directory={0} -xf {1}".format(build.base_path, tarball_path)
    if tarball_contents:
        tarball_prefix = tarball_contents.splitlines()[0].rsplit("/")[0]
        if tarball_prefix == ".":
            tarball_prefix = tarball_contents.splitlines()[0].rsplit("/")[1]
    return extract_cmd, tarball_prefix


def download_tarball(url_argument, name_argument, archives, target_dir):
    global name
    global rawname
    global version
    global url
    global path
    global tarball_prefix
    global gcov_file

    url = url_argument
    tarfile = os.path.basename(url)
    pattern_options = [
        r"(.*?)[\-_](v*[0-9]+[alpha\+_spbfourcesigedsvstableP0-9\.\-\~]*)\.src\.(tgz|tar|zip)",
        r"(.*?)[\-_](v*[0-9]+[alpha\+_sbpfourcesigedsvstableP0-9\.\-\~]*)\.(tgz|tar|zip)",
        r"(.*?)[\-_](v*[0-9]+[a-zalpha\+_spbfourcesigedsvstableP0-9\.\-\~]*)\.orig\.tar",
        r"(.*?)[\-_](v*[0-9]+[\+_spbfourcesigedsvstableP0-9\.\~]*)(-.*?)?\.tar",
    ]
    for pattern in pattern_options:
        p = re.compile(pattern)
        m = p.search(tarfile)
        if m:
            name = m.group(1).strip()
            version = m.group(2).strip()
            b = version.find("-")
            if b >= 0:
                version = version[:b]
            break

    rawname = name
    # R package
    if url_argument.find("cran.r-project.org") > 0 or url_argument.find("cran.rstudio.com") > 0:
        buildpattern.set_build_pattern("R", 10)
        files.want_dev_split = 0
        buildreq.add_buildreq("clr-R-helpers")
        p = re.compile(r"([A-Za-z0-9]+)_(v*[0-9]+[\+_spbfourcesigedsvstableP0-9\.\~\-]*)\.tar\.gz")
        m = p.search(tarfile)
        if m:
            name = "R-" + m.group(1).strip()
            rawname = m.group(1).strip()
            version = m.group(2).strip()
            b = version.find("-")
            if b >= 0:
                version = version[:b]

    if url_argument.find("pypi.python.org") > 0:
        buildpattern.set_build_pattern("distutils", 10)

    if url_argument.find(".cpan.org/CPAN/") > 0:
        buildpattern.set_build_pattern("cpan", 10)
        if name:
            name = "perl-" + name
    if url_argument.find(".metacpan.org/") > 0:
        buildpattern.set_build_pattern("cpan", 10)
        if name:
            name = "perl-" + name

    if url_argument.find("github.com") > 0:
        p = re.compile(r"https://github.com/.*/(.*?)/archive/(.*)-final.tar")
        m = p.search(url_argument)
        if m:
            name = m.group(1).strip()
            version = m.group(2).strip()
        else:
            p = re.compile(r"https://github.com/.*/(.*?)/archive/v?(.*).tar")
            m = p.search(url_argument)
            if m:
                name = m.group(1).strip()
                version = m.group(2).strip()

    if url_argument.find("bitbucket.org") > 0:
        p = re.compile(r"https://bitbucket.org/.*/(.*?)/get/[a-zA-Z_-]*([0-9][0-9_.]*).tar")
        m = p.search(url_argument)
        if m:
            name = m.group(1).strip()
            version = m.group(2).strip().replace('_', '.')

    # ruby
    if url_argument.find("rubygems.org/") > 0:
        buildpattern.set_build_pattern("ruby", 10)
        p = re.compile(r"(.*?)[\-_](v*[0-9]+[alpha\+_spbfourcesigedsvstableP0-9\.\-\~]*)\.gem")
        m = p.search(tarfile)
        if m:
            buildreq.add_buildreq("ruby")
            buildreq.add_buildreq("rubygem-rdoc")
            name = "rubygem-" + m.group(1).strip()
            rawname = m.group(1).strip()
            version = m.group(2).strip()
            b = version.find("-")
            if b >= 0:
                version = version[:b]

    # override from commandline
    if name_argument and name_argument[0] != name:
        pattern = name_argument[0] + r"[\-]*(.*)\.(tgz|tar|zip)"
        p = re.compile(pattern)
        m = p.search(tarfile)
        if m:
            name = name_argument[0]
            rawname = name
            version = m.group(1).strip()
            b = version.find("-")
            if b >= 0:
                version = version[:b]
            if version.startswith('.'):
                version = version[1:]
        else:
            name = name_argument[0]

    if not name:
        split = url_argument.split('/')
        if len(split) > 3 and split[-2] in ('archive', 'tarball'):
            name = split[-3]
            version = split[-1]
            if version.startswith('v'):
                version = version[1:]
            # remove extension
            version = '.'.join(version.split('.')[:-1])
            if version.endswith('.tar'):
                version = '.'.join(version.split('.')[:-1])

    b = version.find("-")
    if b >= 0:
        b = b + 1
        version = version[b:]

    if version[0] in ['v', 'r']:
        version = version[1:]

    assert name != ""

    if not target_dir:
        build.download_path = os.getcwd() + "/" + name
    else:
        build.download_path = target_dir
    call("mkdir -p %s" % build.download_path)

    gcov_path = build.download_path + "/" + name + ".gcov"
    if os.path.isfile(gcov_path):
        gcov_file = name + ".gcov"

    tarball_path = check_or_get_file(url, tarfile)
    sha1 = get_sha1sum(tarball_path)
    with open(build.download_path + "/upstream", "w") as file:
        file.write(sha1 + "/" + tarfile + "\n")

    tarball_prefix = name + "-" + version
    if tarfile.lower().endswith('.zip'):
        tarball_contents = subprocess.check_output(
            ["unzip", "-l", tarball_path], universal_newlines=True)
        if tarball_contents and len(tarball_contents.splitlines()) > 3:
            tarball_prefix = tarball_contents.splitlines()[3].rsplit("/")[0].split()[-1]
        extract_cmd = "unzip -d {0} {1}".format(build.base_path, tarball_path)

    elif tarfile.lower().endswith('.gem'):
        tarball_contents = subprocess.check_output(
            ["gem", "unpack", "--verbose", tarball_path], universal_newlines=True)
        extract_cmd = "gem unpack --target={0} {1}".format(build.base_path, tarball_path)
        if tarball_contents:
            tarball_prefix = tarball_contents.splitlines()[-1].rsplit("/")[-1]
            if tarball_prefix.endswith("'"):
                tarball_prefix = tarball_prefix[:-1]
    else:
        extract_cmd, tarball_prefix = build_untar(tarball_path)

    print("\n")

    print("Processing", url_argument)
    print(
        "=============================================================================================")
    print("Name        :", name)
    print("Version     :", version)
    print("Prefix      :", tarball_prefix)

    with open(build.download_path + "/Makefile", "w") as file:
        file.write("PKG_NAME := " + name + "\n")
        file.write("URL := " + url_argument + "\n")
        file.write("ARCHIVES :=")
        for archive in archives:
            file.write(" {}".format(archive))
        file.write("\n")
        file.write("\n")
        file.write("include ../common/Makefile.common\n")

    shutil.rmtree("{}".format(build.base_path), ignore_errors=True)
    os.makedirs("{}".format(build.output_path))
    call("mkdir -p %s" % build.download_path)
    call(extract_cmd)

    path = build.base_path + tarball_prefix

    for archive, destination in zip(archives[::2], archives[1::2]):
        source_tarball_path = check_or_get_file(archive, os.path.basename(archive))
        if source_tarball_path.lower().endswith('.zip'):
            tarball_contents = subprocess.check_output(
                ["unzip", "-l", source_tarball_path], universal_newlines=True)
            if tarball_contents and len(tarball_contents.splitlines()) > 3:
                source_tarball_prefix = tarball_contents.splitlines()[3].rsplit("/")[0].split()[-1]
            extract_cmd = "unzip -d {0} {1}".format(build.base_path, source_tarball_path)
        else:
            extract_cmd, source_tarball_prefix = build_untar(source_tarball_path)
        buildpattern.archive_details[archive + "prefix"] = source_tarball_prefix
        call(extract_cmd)
        tar_files = glob.glob("{0}{1}/*".format(build.base_path, source_tarball_prefix))
        move_cmd = "mv "
        for tar_file in tar_files:
            move_cmd += tar_file + " "
        move_cmd += '{0}/{1}'.format(path, destination)

        mkdir_cmd = "mkdir -p "
        mkdir_cmd += '{0}/{1}'.format(path, destination)

        print("mkdir " + mkdir_cmd)
        call(mkdir_cmd)
        call(move_cmd)

        sha1 = get_sha1sum(source_tarball_path)
        with open(build.download_path + "/upstream", "a") as file:
            file.write(sha1 + "/" + os.path.basename(archive) + "\n")


def write_nvr(file):
    global name
    global version
    global release
    file.write("Name     : " + name + "\n")
    file.write("Version  : " + version + "\n")
    file.write("Release  : " + str(release) + "\n")
    file.write("URL      : " + url + "\n")
    file.write("Source0  : " + url + "\n")
