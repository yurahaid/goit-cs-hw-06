import multiprocessing
import mimetypes
import os
import pathlib
from functools import partial
from http.server import HTTPServer, BaseHTTPRequestHandler
import urllib.parse
import socket
from dotenv import load_dotenv
import logging

# Load environment variables from .env file
load_dotenv()

# Configure logging
log_level = os.environ.get('LOG_LEVEL', 'DEBUG').upper()
logging.basicConfig(level=getattr(logging, log_level, logging.DEBUG),
                    format='%(asctime)s - %(levelname)s - %(message)s')

class SocketWriter:
    def __init__(self, socket_ip, socket_port):
        self.socket_client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket_server = socket_ip, socket_port

    def close(self):
        self.socket_client.close()

    def write(self, data):
        self.socket_client.sendto(data, self.socket_server)
        logging.debug(f'Send data: {data.decode()} to socket: {self.socket_server}')
        response, address = self.socket_client.recvfrom(1024)
        logging.debug(f'HTTP Response data: {response.decode()} from address: {address}')



class HttpHandler(BaseHTTPRequestHandler):
    def __init__(self, socket_writer: SocketWriter, *args, **kwargs):
        self.socket_writer = socket_writer

        super().__init__(*args, **kwargs)


    def do_GET(self):
        pr_url = urllib.parse.urlparse(self.path)
        if pr_url.path == '/':
            self.send_html_file('index.html')
        else:
            if pathlib.Path().joinpath(pr_url.path[1:]).exists():
                self.send_static()
            else:
                self.send_html_file('error.html', 404)

    def do_POST(self):
        data = self.rfile.read(int(self.headers['Content-Length']))
        self.socket_writer.write(data)
        self.send_response(302)
        self.send_header('Location', '/message.html')
        self.end_headers()

    def send_html_file(self, filename, status=200):
        self.send_response(status)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        with open(filename, 'rb') as fd:
            self.wfile.write(fd.read())

    def send_static(self):
        self.send_response(200)
        mt = mimetypes.guess_type(self.path)
        if mt:
            self.send_header("Content-type", mt[0])
        else:
            self.send_header("Content-type", 'text/plain')
        self.end_headers()
        with open(f'.{self.path}', 'rb') as file:
            self.wfile.write(file.read())

def run_udp_server(ip, port):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server = ip, port
    sock.bind(server)
    try:
        logging.debug(f"UDP server started on ip: {ip}, port: {port}")
        while True:
            data, address = sock.recvfrom(1024)
            logging.debug(f'UDP Received data: {data.decode()} from: {address}')
            sock.sendto(data, address)
            logging.debug(f'UDP Send data: {data.decode()} to: {address}')

    except KeyboardInterrupt:
        logging.debug('Destroy UDP server')
    finally:
        sock.close()


def run_http_server(port, socket_ip, socket_port,):
    soket_writer = SocketWriter(socket_ip, socket_port)

    server_address = ('', port)
    handler = partial(HttpHandler, soket_writer)
    http = HTTPServer(server_address, handler)

    try:
        logging.debug(f'Http server started on port: {port}')
        http.serve_forever()
    except KeyboardInterrupt:
        logging.debug('Destroy HTTP server')
    finally:
        http.server_close()
        soket_writer.close()


if __name__ == '__main__':
    udp_ip = os.environ.get('UDP_IP', '127.0.0.1')
    udp_port = int(os.environ.get('UDP_PORT', 5000))
    http_port = int(os.environ.get('HTTP_PORT', 3000))

    http_process = multiprocessing.Process(target=run_http_server, args=(http_port, udp_ip, udp_port,))
    udp_process = multiprocessing.Process(  target=run_udp_server, args=(udp_ip, udp_port,))

    http_process.start()
    udp_process.start()
    http_process.join()
    udp_process.join()
