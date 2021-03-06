#
# Copyright 2013, Kamil Wilas (wilas.pl)
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# src page: github.com/wilas/py-zfswrapper
#

"""
.. module:: zfswrapper 
    :platform: Linux, Unix
    :synopsis: Quick'n'dirty warapper for ZFS file system. Tested with ZFS pool version 28.

.. moduleauthor:: Kamil Wilas <wilas.pl>

.. note::

    Zpool and zfs manual is a must !!!

"""

import subprocess

zfs_bin = 'zfs'
zpool_bin = 'zpool'
ssh_bin = 'ssh'

class ZfsException(Exception):
    """Raised when any ZFS operation fails for functions in this module."""

    def __init__(self, command, error_code, message):
        self.command = command
        self.error_code = error_code
        self.message = message

    def __str__(self):
        return repr('Zfs execute %s, error_code:%s, %s' % 
                (self.command, self.error_code, self.message))
    

def _run(cmd):
    """Exec zfs command using subprocess.
    Returns message from subprocess stdout
    or raises a ZfsException when error occured.
    
    :param cmd: zfs command to exec
    :type cmd: list
    :returns: str
    :raises: :class:`ZfsException`
    """
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, 
            stderr=subprocess.STDOUT)
    message = proc.communicate()[0].rstrip()
    if proc.returncode:
        raise ZfsException(cmd, proc.returncode, message)
    return message

def zfs_create(fs, properties=None):
    """Creates a new zfs filesystem with all the non-existing parent datasets.
    Allow customize zfs during creation by specify properties
    or you can do it later using :func:`zfs_set`.

    :param fs: zfs filesystem name
    :type fs: str
    :param properties: specify properties of a new created filesystem
    :type properties: dict or None
    :raises: :class:`ZfsException`
    """
    cmd = [zfs_bin, 'create', '-p']
    if properties:
        for property, value in properties.iteritems():
            cmd += ['-o','%s=%s' % (property, value)]
    cmd += [fs]
    _run(cmd)

def zfs_destroy(fs, options=None):
    """Destroys the given dataset.
    
    :param fs: zfs dataset name
    :type fs: str
    :param options: destroy command options
    :type options: list or None
    :raises: :class:`ZfsException`
    """
    cmd = [zfs_bin, 'destroy']
    if options:
        cmd += options
    cmd += [fs]
    _run(cmd)

def zfs_get(fs, property='all'):
    """Returns properties for the given dataset or None if problem with zfs.

     * If a property is given, then only these properties are returned, by default all properties are returned. 
    
    .. warning::     
        Not work with white space in datasets name.

    :param fs: zfs dataset name
    :type fs: str
    :param property: a comma-separated string of properies
    :type property: str
    :returns: dict or None -- dataset properties
    """
    cmd = [zfs_bin, 'get', '-Hp', '-o', 'property,value', property, fs]
    try:
        output = _run(cmd)
    except ZfsException:
        return None
    properties={}
    for desc in output.splitlines():
       prty, val  = desc.split()
       properties[prty] = val
    return properties

def zfs_list(fs=None, types='filesystem,snapshot', depth=None):
    """Returns list of zfs datasets and recursively any children of the datasets
    or None if problem with zfs.

     * If a fs is given, list recursive starting from that fs.
     * If a types is given, list only dataset with specified type, by default list filesystems and snapshots.
     * If a depth is given, list any children of the dataset, limiting the recursion to depth.
    
    :param fs: zfs dataset name
    :type fs: str or None
    :param types: a comma-separated string of types, where type is one of filesystem, snapshot, volume or all.
    :type types: str
    :param depth: limiting the recursion depth
    :type depth: int or None
    :returns: list or None -- datasets list
    """
    cmd = [zfs_bin, 'list', '-rH', '-o', 'name']
    if types:
        cmd += ['-t', types]
    if depth:
        cmd += ['-d', depth]
    if fs:
        cmd += [fs]
    try:
        output = _run(cmd)
    except ZfsException:
        return None
    if not output or output.startswith('no datasets available'):
        return []
    return output.splitlines()

def zfs_receive(recv_fs, options=None, ssh_host=None):
    """Returns tuple (child process with open stdin, zfs recv command with arguments)
    
    Child process is responsible for creation a snapshot 
    whose contents are as specified in the stream provided on standard input. 
    Streams are created using the :func:`zfs_send`. Look also to :func:`zfs_teleport_snapshot`.

    :param recv_fs: destination zfs dataset name
    :type recv_fs: str
    :param options: receive command options (e.g. ['-F', '-d'])
    :type options: list or None
    :param ssh_host: remote hostname
    :type ssh_host: str or None 
    :returns: tuple -- (child proces, executed command)
    """
    cmd = [zfs_bin, 'recv']
    if options:
        cmd += options
    cmd += [recv_fs]
    if ssh_host:
        cmd = [ssh_bin, ssh_host] + cmd
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, 
            stderr=subprocess.PIPE, bufsize=-1)
    return (proc, cmd)

def zfs_send(send_snapshot, recurse=False, options=None, ssh_host=None):
    """Returns tuple (child process with open stdout, zfs send command with arguments)
    
    Child process is responsible for creation a stream representation of the snapshot,
    which is written to standard output. Look also to :func:`zfs_teleport_snapshot`.

    :param send_snapshot: source zfs snapshot name (full path)
    :type send_snapshot: str
    :param recurse: replicate the specified filesystem, and all descendent filesystems, up to the named snapshot
    :type recurse: bool, default False
    :param options: send command options
    :type options: list or None
    :param ssh_host: remote hostname
    :type ssh_host: str or None 
    :returns: tuple -- (child proces, executed command)
    """
    cmd = [zfs_bin, 'send']
    if recurse:
        cmd += ['-R']
    if options:
        cmd += options
    cmd += [send_snapshot]
    if ssh_host:
        cmd = [ssh_bin, ssh_host] + cmd
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE, bufsize=-1)
    return (proc, cmd)

def zfs_set(fs, property, value):
    """Sets the property to the given value for each dataset.

    :param fs: zfs dataset name
    :type fs: str
    :param property: property name
    :type property: str
    :param value: property value
    :type value: str
    :raises: :class:`ZfsException`
    """
    cmd = [zfs_bin, 'set', '%s=%s' % (property, value), fs]
    _run(cmd)

def zfs_snapshot(fs, tag, recurse=False, properties=None):
    """Creates a snapshot with given name. 
    Allow customize snapshot during creation by specify properties
    or you can do it later using :func:`zfs_set`.

    :param fs: zfs filesystem/volume name
    :type fs: str
    :param tag: snapshot tag name
    :type tag: str
    :param recurse: recursively create snapshots of all descendent datasets, snapshots are taken atomically
    :type recurse: bool, by default False
    :param properties: specify properties of a new created snapshot
    :type properties: dict or None
    :raises: :class:`ZfsException`
    """
    cmd = [zfs_bin, 'snapshot']
    if recurse:
        cmd += ['-r']
    if properties:
        for property, value in properties.iteritems():
            cmd += ['-o','%s=%s' % (property, value)]
    cmd += ['%s@%s' % (fs, tag)]
    _run(cmd)

def zfs_teleport_snapshot(send_snapshot, recv_fs, recv_host=None):
    """Replicates the specified dataset using :func:`zfs_send` and :func:`zfs_receive`.

    .. warning::
        This is not standard command in ZFS API. 
    
    :param send_snapshot: source zfs snapshot name (full path)
    :type send_snapshot: str
    :param recv_fs: destination zfs filesystem/volume name
    :type recv_fs: str
    :param recv_host: destination hostname
    :type recv_host: str or None
    :raises: :class:`ZfsException`
    """
    sender, sender_cmd = zfs_send(send_snapshot, recurse=True)
    receiver, receiver_cmd  = zfs_receive(recv_fs, options=['-F'], ssh_host=recv_host)
    for data in sender.stdout:
        receiver.stdin.write(data)
    # sender close stdout,stderr stream, get returncode and read error_message
    sender.stdout.close()
    sender.wait()
    sender_error = sender.stderr.read()
    sender.stderr.close()
    # receiver close stdin,stderr stream, get returncode and read error_message
    receiver.stdin.close()
    receiver.wait()
    receiver_error = receiver.stderr.read()
    receiver.stderr.close()
    # raise exception if any error
    if sender.returncode or receiver.returncode:
        args = 'sender_cmd:%s receiver_cmd:%s' % (sender_cmd, receiver_cmd)
        error_code = 's:%sr:%s' % (sender.returncode, receiver.returncode)
        error_message = 'sender_error:%s receiver_error:%s' % (sender_error, receiver_error)
        raise ZfsException(args, error_code, error_message)

def zpool_add(pool, vdev):
    """Adds the specified virtual devices to the given pool. Increases zpool size.
   
    vdev example:

    >>> vdev = ['raidz', 'disc01', 'disc02', 'disc03']
    >>> vdev = ['mirror', 'disc01', 'disc02']
    >>> vdev = ['disc01']

    :param pool: zpool name
    :type pool: str
    :param vdev: virtual devices list to add
    :type vdev: list
    :raises: :class:`ZfsException`
    """
    cmd = [zpool_bin, 'add', '-f', pool] + vdev
    _run(cmd)

def zpool_attach(pool, device, new_device):
    """Attaches new_device to an existing zpool device. Creates mirror.
    The existing device cannot be part of a raidz configuration.

    :param pool: zpool name
    :type pool: str
    :param device: existing zpool device
    :type device: str
    :param new_device: new device to attach
    :type new_device: str
    :raises: :class:`ZfsException`
    """
    cmd = [zpool_bin, 'attach', '-f', pool, device, new_device]
    _run(cmd)

def zpool_create(pool, vdev, properties=None):
    """Creates a new storage pool containing the virtual devices specified in vdev parameters.
    Allow customize zpool during creation by specify properties.
    
    vdev example:

    >>> vdev = ['raidz', 'disc01', 'disc02', 'disc03']
    >>> vdev = ['mirror', 'disc01', 'disc02']
    >>> vdev = ['disc01']

    :param pool: zpool name
    :type pool: str
    :param vdev: virtual devices list to add
    :type vdev: list
    :param properties: specify properties of a new created pool
    :type properties: dict or None
    :raises: :class:`ZfsException`
    """
    cmd = [zpool_bin, 'create']
    if properties:
        for property, value in properties.iteritems():
            cmd += ['-o','%s=%s' % (property, value)]
    cmd += [pool]
    cmd += vdev
    _run(cmd)

def zpool_destroy(pool):
    """Destroys the given pool.
    Forces any active datasets contained within the pool to be unmounted.

    :param pool: zpool name
    :type pool: str
    :raises: :class:`ZfsException`
    """
    cmd = [zpool_bin, 'destroy', '-f', pool]
    _run(cmd)

def zpool_detach(pool, device):
    """Detaches device from a mirror.

    :param pool: zpool name
    :type pool: str
    :param device: existing device to deatach
    :type device: str
    :raises: :class:`ZfsException`
    """
    cmd = [zpool_bin, 'detach', pool, device]
    _run(cmd)

def zpool_get(pool, property='all'):
    """Returns properties for the given zpool or None if problem with zfs.

     * If a property is given, then only these properties are returned, by default all properties are returned. 
    
    .. warning::     
        Not work with white space in zpool name.

    Usage example:

    >>> zpool_name = 'example_zpool'
    >>> property = 'version,health'
    >>> zpool_info = zfs.zpool_get(zpool_name, property)

    :param pool: zpool name
    :type pool: str
    :param property: a comma-separated string of properies
    :type property: str
    :returns: dict or None -- pool properties
    """
    cmd = [zpool_bin, 'get', property, pool]
    try:
        output = _run(cmd)
    except ZfsException:
        return None
    properties={}
    # zpool get has always headers
    for desc in output.splitlines()[1:]:
       name, prty, val, source  = desc.split()
       properties[prty] = val
    return properties

def zpool_list(pool=None):
    """Returns lists the given pool or None if probelm with zpool. 
    When given no arguments, all pools in the system are listed.

    :param pool: zpool name
    :type pool: str or None
    :returns: list or None -- pools list
    """
    cmd = [zpool_bin, 'list', '-H', '-o', 'name']
    if pool:
        cmd += [pool]
    try:
        output = _run(cmd)
    except ZfsException:
        return None
    if not output or output.startswith('no pools available'):
        return []
    return output.splitlines()

def zpool_status(pool):
    """Returns health status for the given zpool or None if problem with zfs.

    Usage example:

    >>> zpool_name = 'example_zpool'
    >>> zpool_info = zfs.zpool_status(zpool_name)
    >>> print zpool_info
    ONLINE

    :param pool: zpool name
    :type pool: str
    :returns: str or None -- pool status
    """
    cmd = [zpool_bin, 'list', '-H', '-o', 'health', pool]
    try:
        output = _run(cmd)
    except ZfsException:
        return None
    status = output.rstrip()
    return status
