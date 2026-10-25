"""Network guard for the explicitly synthetic repository fixture checker."""
import ipaddress
import socket


def _local(host):
    if host in (None, 'localhost', b'localhost'):
        return True
    try:
        return ipaddress.ip_address(host.decode() if isinstance(host, bytes) else host).is_loopback
    except ValueError:
        return False


def pytest_configure(config):
    original_connect = socket.socket.connect
    original_connect_ex = socket.socket.connect_ex
    original_resolve = socket.getaddrinfo

    def connect(sock, address):
        if not isinstance(address, tuple) or not _local(address[0]):
            raise RuntimeError('synthetic fixture forbids non-loopback connections')
        return original_connect(sock, address)

    def connect_ex(sock, address):
        if not isinstance(address, tuple) or not _local(address[0]):
            raise RuntimeError('synthetic fixture forbids non-loopback connections')
        return original_connect_ex(sock, address)

    def resolve(host, *args, **kwargs):
        if not _local(host):
            raise RuntimeError('synthetic fixture forbids external name resolution')
        return original_resolve(host, *args, **kwargs)

    socket.socket.connect = connect
    socket.socket.connect_ex = connect_ex
    socket.getaddrinfo = resolve
