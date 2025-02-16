import re
import asyncio
import aiohttp
from copy import copy
from typing import Optional
from ..transport import HttpTransport, WebSocketTransport, TransportStatus
from ..opsencoder.gcode import GcodeEncoder
from ..models.ops import Ops
from ..models.machine import Machine
from .driver import Driver, DeviceStatus


hw_info_url = '/command?plain=%5BESP420%5D&PAGEID='
fw_info_url = '/command?plain=%5BESP800%5D&PAGEID='
eeprom_info_url = '/command?plain=%5BESP400%5D&PAGEID='
command_url = '/command?commandText=?&PAGEID={command}'
upload_url = '/upload'
upload_list_url = '/upload?path=/&PAGEID=0'
execute_url = '/command?commandText=%5BESP220%5D/{filename}'
status_url = command_url.format(command='')

pos_re = re.compile(r':(\d+\.\d+),(\d+\.\d+),(\d+\.\d+)')
fs_re = re.compile(r'FS:(\d+),(\d+)')

def _parse_pos_triplet(pos, default=None):
    match = pos_re.search(pos)
    if not match or match.lastindex != 3:
        return default
    return [float(i) for i in match.groups()]

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

    def _parse_state(self, state_str):
        """
        Example state_str:
        Run|MPos:10.0,20.0,0.0|WPos:10.0,20.0,0.0|W0:10.0,20.0,0.0|FS:1500,0

        - First field is always the status.
        - MPos is position in machine coords.
        - WPos is position in work coords.
        - No idea what W0 is.
        - FS: the first value looks like a speed. The second probably also
          is, but I have never seen it >0, so no idea.

        Also note that not always all fields are included, and sometimes
        others not listed here appear.
        """
        # Split out the status.
        try:
            status, *attribs = state_str.split('|')
        except ValueError:
            return

        state = copy(self.state)
        try:
            state.status = DeviceStatus[status.upper()]
        except KeyError:
            self.log_received.send(
                self,
                message=f"device sent an unupported status: {status}"
            )

        # Parse the substrings.
        for attrib in attribs:
            if attrib.startswith('MPos:'):
                state.machine_pos = _parse_pos_triplet(
                    attrib,
                    state.machine_pos
                )

            elif attrib.startswith('WPos:'):
                state.work_pos = _parse_pos_triplet(attrib, state.work_pos)

            elif attrib.startswith('FS:'):
                # This attribute is not actually used yet.
                try:
                    match = fs_re.match(attrib)
                    fs = [int(i) for i in match.groups()]
                except ValueError:
                    pass

            else:
                pass # Ignore everything else

        return state

    def on_websocket_data_received(self, sender, data: bytes):
        data = data.decode('utf-8')
        for line in data.splitlines():
            if not line.startswith('<') or not line.endswith('>'):
                self._log(line)
                continue
            state = self._parse_state(line[1:-1])
            if state != self.state:
                self.state = state
                self._on_state_changed()

    def on_websocket_status_changed(self,
                                    sender,
                                    status: TransportStatus,
                                    message: Optional[str] = None):
        self._on_connection_status_changed(status, message)
