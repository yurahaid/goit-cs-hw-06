import multiprocessing
import mimetypes
import os
import pathlib
from http.server import HTTPServer, BaseHTTPRequestHandler
import urllib.parse
import socket
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class HttpHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        pr_url = urllib.parse.urlparse(self.path)
        if pr_url.path == '/':
            self.send_html_file('index.html')
        else:
            if pathlib.Path().joinpath(pr_url.path[1:]).exists():
                self.send_static()
            else:
                self.send_html_file('error.html', 404)

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
        print("Udp server started on ip: ", ip, " port: ", port)
        while True:
            data, address = sock.recvfrom(1024)
            print(f'Received data: {data.decode()} from: {address}')
            sock.sendto(data, address)
            print(f'Send data: {data.decode()} to: {address}')

    except KeyboardInterrupt:
        print(f'Destroy server')
    finally:
        sock.close()


def run_http_server(port):
    server_address = ('', port)
    http = HTTPServer(server_address, HttpHandler)

    try:
        print(f'Http server started on port: {port}')
        http.serve_forever()
    except KeyboardInterrupt:
        http.server_close()


if __name__ == '__main__':
    http_process = multiprocessing.Process(
        target=run_http_server,
        args=(int(os.environ.get('HTTP_PORT', 8000)),)
    )
    udp_process = multiprocessing.Process(
        target=run_udp_server,
        args=(os.environ.get('UDP_IP', '127.0.0.1'), int(os.environ.get('UDP_PORT', 5000)))
    )

    http_process.start()
    udp_process.start()
    http_process.join()
    udp_process.join()
