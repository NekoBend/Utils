# import asyncio
# import functools
import io
import json
# import multiprocessing
import queue
import re
# import select
import subprocess
import threading
# import time
from collections import namedtuple

from datetime import datetime
from typing import Callable, Union, List, Any, Iterator


class PwshRequests:

    def _auto_encoder(stream: io.TextIOWrapper) -> str:
        for encoding in ['utf-8', 'shift-jis', 'euc-jp', 'cp932']:
            try:
                return stream.read().decode(encoding)

            except UnicodeDecodeError:
                continue

        print('Warning: Encoding is not supported.')
        return stream.read()

    def _run_cmd(cmd: str) -> dict:
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        stdout = PwshRequests._auto_encoder(process.stdout)
        stderr = PwshRequests._auto_encoder(process.stderr)

        if stderr:
            print(f'Error: {stderr}')
            return False

        return stdout

    def _gen_cmd(cmd: str, headers: dict, body: dict = '') -> str:
        pwsh = 'powershell -Command'

        encode = '$encode = [System.Text.Encoding]::UTF8;'

        headers = ' | '.join([
            f"$headers = @{{}}; ('{json.dumps(headers)}'",
            "ConvertFrom-Json).psobject.properties",
            "ForEach-Object { $headers[$_.Name] = $_.Value.ToString() };",
        ])

        if body:
            body = f"$body = '{json.dumps(body, ensure_ascii=False)}'; $body = $encode.GetBytes($body);"

        rest = f'$response = Invoke-RestMethod {cmd} -ContentType "application/json";'

        end = "$jsonResponse = $response | ConvertTo-Json -Depth 3; $encode.GetString($jsonResponse);"

        return f'{pwsh} {encode} {headers} {body} {rest} {end}'

    @staticmethod
    def get(url: str, headers: dict) -> dict:
        cmd = f'-Method GET -Uri "{url}" -Headers $headers'
        request_cmd = PwshRequests._gen_cmd(cmd, headers)

        return PwshRequests._run_cmd(request_cmd)

    @staticmethod
    def post(url: str, headers: dict, body: dict) -> dict:
        cmd = f'-Method POST -Uri "{url}" -Headers $headers -Body $body'
        request_cmd = PwshRequests._gen_cmd(cmd, headers, body)

        return PwshRequests._run_cmd(request_cmd)

    @staticmethod
    def put(url: str, headers: dict, body: dict) -> dict:
        return

    @staticmethod
    def delete(url: str, headers: dict) -> dict:
        return


class CmdObserver:
    _is_running = False
    _readline = namedtuple('Readline', ['time', 'stdout', 'stderr'])
    _output = queue.Queue()

    def __init__(self, cmd: str) -> None:
        self.cmd = cmd

    def __str__(self) -> str:
        return self.cmd

    def __repr__(self) -> str:
        return self.cmd

    def _run(self):
        self._process = subprocess.Popen(self.cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=65536, encoding='utf-8')

        stdout_thread = threading.Thread(target=self._read_stdout)
        stderr_thread = threading.Thread(target=self._read_stderr)

        stdout_thread.start()
        stderr_thread.start()

        stdout_thread.join()
        stderr_thread.join()

        self._process.terminate()

    def _read_stdout(self):
        while self._is_running:
            readline = self._process.stdout.readline().strip()

            if readline:
                self._put(stdout=readline)

    def _read_stderr(self):
        while self._is_running:
            readline = self._process.stderr.readline().strip()

            if readline:
                print(f'Warning: {readline}')
                self._put(stderr=readline)

    def _put(self, stdout: str = None, stderr: str = None):
        self._output.put(self._readline(
            datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            stdout,
            stderr,
        ))

    def is_empty(self) -> bool:
        return self._output.empty()

    def get(self, timeout: int = 1) -> dict | None:
        try:
            return self._output.get(timeout=timeout)

        except queue.Empty:
            return False

    def is_running(self) -> bool:
        return self._is_running

    def start(self):
        self._is_running = True
        self._thread = threading.Thread(target=self._run)
        self._thread.start()

    def stop(self):
        self._is_running = False
        self._thread.join()


class Clipboard:

    @staticmethod
    def copy(value: str):
        subprocess.Popen('clip', stdin=subprocess.PIPE, text=True).communicate(input=value)

    @staticmethod
    def paste() -> str:
        return subprocess.Popen('powershell -Command Get-Clipboard', stdout=subprocess.PIPE, text=True).communicate()[0]


class ReString(str):

    def __new__(cls, value: str) -> 'ReString':
        return super().__new__(cls, value)

    def __str__(self) -> str:
        return self

    def __repr__(self) -> str:
        return self

    def to_string(self) -> str:
        return str(self)

    def match(self, pattern: str, flags=0) -> Union[re.Match[str], None]:
        return re.match(pattern, self, flags)

    def fullmatch(self, pattern: str, flags=0) -> Union[re.Match[str], None]:
        return re.fullmatch(pattern, self, flags)

    def search(self, pattern: str, flags=0) -> Union[re.Match[str], None]:
        return re.search(pattern, self, flags)

    def sub(self, pattern: str, repl: str, count: int = 0, flags=0) -> 'ReString':
        result = re.sub(pattern, repl, self, count, flags)
        return ReString(result)

    def subn(self, pattern: str, repl: str, count: int = 0, flags=0) -> tuple['ReString', int]:
        result, num_subs = re.subn(pattern, repl, self, count, flags)
        return ReString(result), num_subs

    def resplit(self, pattern: str, maxsplit: int = 0, flags=0) -> List[Union['ReString', Any]]:
        results = re.split(pattern, self, maxsplit, flags)
        return [ReString(item) for item in results if isinstance(item, str)]

    def findall(self, pattern: str, flags=0) -> List[Union[Any]]:
        results = re.findall(pattern, self, flags)
        return [ReString(item) for item in results if isinstance(item, str)]

    def finditer(self, pattern: str, flags=0) -> Iterator[re.Match[str]]:
        return re.finditer(pattern, self, flags)
