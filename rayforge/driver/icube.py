import re
import asyncio
import aiohttp
from typing import Optional
from ..transport import HttpTransport, WebSocketTransport, TransportStatus
from ..opsencoder.gcode import GcodeEncoder
from ..models.ops import Ops
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
    Handles Sculpfun iCube via HTTP+WebSocket
    """
    label = "Sculpfun iCube"
    subtitle = 'Send Gcode via network connection'

    def __init__(self):
        super().__init__()
        self.encoder = GcodeEncoder()
        self.http = None
        self.websocket = None
        self.keep_running = False
        self._connection_task: Optional[asyncio.Task] = None

    def setup(self, host: str):
        assert not self.did_setup
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
        self.keep_running = False
        if self._connection_task:
            self._connection_task.cancel()
        if self.websocket:
            await self.websocket.disconnect()
            self.websocket.received.disconnect(self.on_websocket_data_received)
            self.websocket.status_changed.disconnect(self.on_websocket_status_changed)
            del self.websocket
        if self.http:
            await self.http.disconnect()
            self.http.received.disconnect(self.on_http_data_received)
            self.http.status_changed.disconnect(self.on_http_status_changed)
            del self.http
        await super().cleanup()

    async def _get_hardware_info(self):
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{self.http_base}{hw_info_url}"
            ) as response:
                data = await response.text()
        return data

    async def _get_firmware_info(self):
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{self.http_base}{fw_info_url}"
            ) as response:
                data = await response.text()
        return data

    async def _get_eeprom_info(self):
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{self.http_base}{eeprom_info_url}"
            ) as response:
                data = await response.text()
        return data

    async def _send_gcode_command(self, command):
        async with aiohttp.ClientSession() as session:
            url = command_url.format(command=command)
            async with session.get(
                f"{self.http_base}{url}"
            ) as response:
                data = await response.text()
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
        return data

    async def _execute(self, filename):
        async with aiohttp.ClientSession() as session:
            url = execute_url.format(filename=filename)
            async with session.get(f"{self.http_base}{url}") as response:
                data = await response.text()
        await session.close()
        return data

    async def connect(self):
        self.keep_running = True
        self._connection_task = asyncio.create_task(self._connection_loop())

    async def _connection_loop(self) -> None:
        while self.keep_running:
            self._on_connection_status_changed(TransportStatus.CONNECTING)
            try:
                hw_info = await self._get_hardware_info()
                self._log(hw_info)
                fw_info = await self._get_firmware_info()
                self._log(fw_info)
                eeprom_info = await self._get_eeprom_info()
                self._log(eeprom_info)

                async with asyncio.TaskGroup() as tg:
                    http = tg.create_task(self.http.connect())
                    socket = tg.create_task(self.websocket.connect())
            except Exception as e:
                self._on_connection_status_changed(
                    TransportStatus.ERROR,
                    str(e)
                )
            finally:
                await self.websocket.disconnect()
                await self.http.disconnect()

            self._on_connection_status_changed(TransportStatus.SLEEPING)
            await asyncio.sleep(5)

    async def run(self, ops: Ops, machine: Machine) -> None:
        gcode = self.encoder.encode(ops, machine)

        try:
            await self._upload(gcode, 'rayforge.gcode')
            await self._execute('rayforge.gcode')
        except Exception as e:
            self._on_connection_status_changed(
                TransportStatus.ERROR,
                str(e)
            )
            raise

    async def move_to(self, pos_x, pos_y) -> None:
        cmd = f"$J=G90 G21 F1500 X{float(pos_x)} Y{float(pos_y)}"
        await self._send_gcode_command(cmd)

    def on_http_data_received(self, sender, data: bytes):
        pass

    def on_http_status_changed(self,
                               sender,
                               status: TransportStatus,
                               message: Optional[str] = None):
        self._on_command_status_changed(status, message)

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
                    self._on_position_changed(mpos[:2])
            self._log(line)

    def on_websocket_status_changed(self,
                                    sender,
                                    status: TransportStatus,
                                    message: Optional[str] = None):
        self._on_connection_status_changed(status, message)
