import os
import sys
from pathlib import Path
import hashlib
import argparse
from xmlrpc.server import SimpleXMLRPCServer
from xmlrpc.client import ServerProxy
from config import name_server_url


def whose_file(abs_path):
    path_from_root = abs_path.replace(str(root_dir) + os.sep, '')
    index = path_from_root.find(os.sep)

    if index == -1:
        return -1
    else:
        try:
            user_id = int(path_from_root[0:index].replace('_backup', ''))
            return user_id
        except (ValueError, IndexError):
            return -1


def hash_file(file_path_for_hash):
    hash_obj = hashlib.sha256()

    with open(file_path_for_hash, 'rb') as rbFile:
        while True:
            block = rbFile.read(65536)

            if not block:
                break

            hash_obj.update(block)

    return hash_obj.hexdigest()


def path_check(user_id, path):
    base_dir = root_dir / str(user_id)
    path_obj = (base_dir / path).resolve()
    path_valid = str(path_obj).startswith(str(base_dir))
    return path_valid, path_obj


def get_filenames(user_id, cloud_dir_path):
    """
        user_id,
        cloud_dir_path: directory to list

        returns filename array with create and update dates
    """
    path_valid, path_obj = path_check(user_id, cloud_dir_path)

    if not path_valid:
        return None

    dir_paths = []
    file_paths = []

    for child in path_obj.iterdir():
        if child.is_dir():
            dir_paths.append(child.name)
        else:
            file_paths.append(child.name)

    with ServerProxy(name_server_url) as file_name_proxy:
        file_info = file_name_proxy.get_file_info(user_id, file_paths)

    return dir_paths + file_info


def delete_file(user_id, cloud_file_path):
    """
        user_id,
        cloud_file_path: path of the file to delete

        returns success/error code
        erases file from this server and its backup server
    """
    pass


def upload_file(user_id, file_bin, cloud_dir_path):
    """
        user_id,
        file_bin: binary file pulled from the network (encrypted)
        cloud_dir_path: directory to upload into

        returns success/error code
        uploads file to this server and its backup server
    """
    pass


def fetch_file(user_id, cloud_file_path):
    """
        user_id,
        cloud_file_path: path of the file to fetch

        returns (success/error flag, file binary (encrypted))
        checks if the file is intact by contacting backup server
        if file broken revert from backup
        if backup broken revert from file
        if both broken return (error, None)
    """
    pass


if __name__ == '__main__':
    root_dir = Path.home() / 'rpc_server_files'

    parser = argparse.ArgumentParser()
    parser.add_argument('server_id', help='ID of the file server.', type=int)
    parser.add_argument('port', help='Port of the file server.', type=int)
    args = parser.parse_args()

    with SimpleXMLRPCServer(('localhost', args.port)) as server:
        server.register_function(get_filenames)
        server.register_function(delete_file)
        server.register_function(upload_file)
        server.register_function(fetch_file)

        server_url = 'http://{}:{}'.format(server.server_address[0], server.server_address[1])

        server_registered = False
        with ServerProxy(name_server_url, allow_none=True) as proxy:
            server_registered = proxy.register_file_server(args.server_id, server_url)

        if server_registered:
            root_dir = root_dir / str(args.server_id)
            if not root_dir.exists():
                root_dir.mkdir(parents=True)

            print('Initializing server for files in "{}"...'.format(str(root_dir)))

            file_list = []
            for root, dirs, files in os.walk(str(root_dir)):
                for file_name in files:
                    file_path = os.path.join(root, file_name)
                    whose = whose_file(file_path)
                    file_hash = hash_file(file_path)
                    file_last_modified = os.path.getmtime(file_path)
                    file_info = (whose, args.server_id, file_path, file_name, file_hash, file_last_modified)

                    if whose != -1:
                        print('Added file:', file_info)
                        file_list.append(file_info)

            files_registered = False
            with ServerProxy(name_server_url, allow_none=True) as proxy:
                files_registered = proxy.save_file_info(file_list)

            if files_registered:
                print('Serving file server on {}.'.format(server.server_address))
                try:
                    server.serve_forever()
                except KeyboardInterrupt:
                    with ServerProxy(name_server_url, allow_none=True) as proxy:
                        proxy.unregister_file_server(args.server_id)
            else:
                print('Failed file registration.')
        else:
            print('Failed server registration.')
