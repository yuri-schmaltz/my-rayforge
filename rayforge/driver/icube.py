import re
import asyncio
import aiohttp
from typing import Optional
from ..transport import HttpTransport, WebSocketTransport, Status
from ..pathencoder.gcode import GcodeEncoder
from ..models.path import Path
from ..models.machine import Machine
from .driver import Driver


hw_info_url = '/command?plain=%5BESP420%5D&PAGEID='
fw_info_url = '/command?plain=%5BESP800%5D&PAGEID='
eeprom_info_url = '/command?plain=%5BESP400%5D&PAGEID='
command_url = '/command?commandText=?&PAGEID={command}'
upload_url = '/upload'
upload_list_url = '/upload?path=/&PAGEID=0'
execute_url = '/command?commandText=%5BESP220%5D/{filename}'
status_url = command_url.format(command='')


class ICubeDriver(Driver):
    """
    Handles Sparkfun iCube via HTTP+WebSocket
    """
    label = "Sparkfun iCube"
    subtitle = 'Send Gcode via network connection'

    def __init__(self):
        super().__init__()
        self.encoder = GcodeEncoder()
        self.http = None
        self.websocket = None

    def setup(self, host: str):
        super().setup()

        # Initialize transports
        self.http_base = f'http://{host}'
        self.http = HttpTransport(
            f'{self.http_base}{status_url}',
            receive_interval=.5
        )
        self.http.received.connect(self.on_http_data_received)
        self.http.status_changed.connect(self.on_http_status_changed)

        self.websocket = WebSocketTransport(
            f'ws://{host}:81/',
            self.http_base
        )
        self.websocket.received.connect(self.on_websocket_data_received)
        self.websocket.status_changed.connect(self.on_websocket_status_changed)

    async def cleanup(self):
        if self.http:
            await self.http.disconnect()
            del self.http
        if self.websocket:
            await self.websocket.disconnect()
            del self.websocket

    async def _get_hardware_info(self):
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{self.http_base}{hw_info_url}"
            ) as response:
                data = await response.text()
        await session.close()
        return data

    async def _get_firmware_info(self):
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{self.http_base}{fw_info_url}"
            ) as response:
                data = await response.text()
        await session.close()
        return data

    async def _get_eeprom_info(self):
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{self.http_base}{eeprom_info_url}"
            ) as response:
                data = await response.text()
        await session.close()
        return data

    async def _send_gcode_command(self, command):
        async with aiohttp.ClientSession() as session:
            url = command_url.format(command=command)
            async with session.get(
                f"{self.http_base}{url}"
            ) as response:
                data = await response.text()
        await session.close()
        return data

    async def _upload(self, gcode, filename):
        form = aiohttp.FormData([])
        form.add_field('path', '/')
        form.add_field(f'/{filename}S', str(len(gcode)))
        form.add_field('myfile[]', gcode, filename=filename)
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.http_base}{upload_url}",
                data=form
            ) as response:
                data = await response.text()
        await session.close()
        return data

    async def _execute(self, filename):
        async with aiohttp.ClientSession() as session:
            url = execute_url.format(filename=filename)
            async with session.get(f"{self.http_base}{url}") as response:
                data = await response.text()
        await session.close()
        return data

    async def connect(self):
        while True:
            self.connection_status_changed.send(self, status=Status.CONNECTING)
            try:
                hw_info = await self._get_hardware_info()
                self.log_received.send(self, message=hw_info)
                fw_info = await self._get_firmware_info()
                self.log_received.send(self, message=fw_info)
                eeprom_info = await self._get_eeprom_info()
                self.log_received.send(self, message=eeprom_info)
            except Exception as e:
                self.connection_status_changed.send(
                    self,
                    status=Status.ERROR,
                    message=str(e)
                )

            await self.http.connect()
            await self.websocket.connect()
            await asyncio.sleep(5)

    async def run(self, path: Path, machine: Machine) -> None:
        gcode = self.encoder.encode(path, machine)

        try:
            await self._upload(gcode, 'rayforge.gcode')
            await self._execute('rayforge.gcode')
        except Exception as e:
            self.connection_status_changed.send(
                self,
                status=Status.ERROR,
                message=str(e)
            )
            raise

    async def move_to(self, pos_x, pos_y) -> None:
        cmd = f"$J=G90 G21 F1500 X{float(pos_x)} Y{float(pos_y)}"
        await self._send_gcode_command(cmd)

    def on_http_data_received(self, sender, data: bytes):
        pass

    def on_http_status_changed(self,
                               sender,
                               status: Status,
                               message: Optional[str] = None):
        self.command_status_changed.send(self,
                                         status=status,
                                         message=message)

    def _parse_status(self, line):
        """
        I have not figured out what the difference between the positions
        reported by the device are yet. It reports "mpos", "wpos", and
        sometimes "WC0" which also looks like a position.
        All include three floats. I assume the third is Z, but it is
        always 0 fot the iCube as it does not have a Z axis motor.

        FS: the first value looks like a speed. The second probably also
        is, but I have never seen it >0, so no idea.
        """
        try:
            _, mpos_str, wpos_str, fs_str, *_ = line.split('|')
        except ValueError:
            return None

        pos_re = re.compile(r':(\d+\.\d+),(\d+\.\d+),(\d+\.\d+)')
        try:
            match = pos_re.search(mpos_str)
            mpos = [float(i) for i in match.groups()]
        except ValueError:
            return None
        try:
            match = pos_re.search(wpos_str)
            wpos = [float(i) for i in match.groups()]
        except ValueError:
            return None

        fs_re = re.compile(r'FS:(\d+),(\d+)')
        try:
            match = fs_re.match(fs_str)
            fs = [float(i) for i in match.groups()]
        except ValueError:
            return None
        return mpos, wpos, fs

    def on_websocket_data_received(self, sender, data: bytes):
        data = data.decode('utf-8')
        for line in data.splitlines():
            if line.startswith('<Idle|'):
                status = self._parse_status(line)
                if status:
                    mpos, wpos, fs = status
                    self.position_changed.send(self, position=mpos[:2])
            self.log_received.send(self, message=line)

    def on_websocket_status_changed(self,
                                    sender,
                                    status: Status,
                                    message: Optional[str] = None):
        self.connection_status_changed.send(self,
                                            status=status,
                                            message=message)
