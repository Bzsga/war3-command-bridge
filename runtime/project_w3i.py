import struct
def require(value,message):
    if not value:raise ValueError(message)

class Reader:
    def __init__(self, data):
        self.data, self.pos = data, 0

    def take(self, size):
        result = self.data[self.pos:self.pos + size]
        require(len(result) == size, 'Truncated W3I')
        self.pos += size
        return result

    def unpack(self, fmt):
        return struct.unpack('<' + fmt, self.take(struct.calcsize('<' + fmt)))

    def integer(self):
        return self.unpack('I')[0]

    def string(self):
        start = self.pos
        end = self.data.find(b'\0', start)
        require(end >= start, 'Unterminated W3I string')
        self.pos = end + 1
        return self.data[start:end].decode('utf8')


def room_layout(data):
    r = Reader(data)
    require(r.integer() == 25, 'Only reviewed W3I version 25 is supported')
    r.take(8)  # save count and editor version
    strings = {}
    for name in ('name', 'author', 'description', 'recommended_players'):
        start = r.pos
        value = r.string()
        strings[name] = {'start': start, 'end': r.pos, 'value': value}
    r.take(8 * 4 + 4 * 4 + 2 * 4)  # camera bounds/margins and map dimensions
    flag_offset = r.pos
    flags = r.integer()
    r.take(1 + 4)  # tileset and loading screen background
    for _ in range(4):
        r.string()
    r.take(4)  # game data set
    for _ in range(4):
        r.string()
    r.take(4 + 3 * 4 + 4 + 4)  # terrain fog, fog color, global weather
    r.string()  # sound environment
    r.take(1 + 4)  # light environment and water tint
    room_start = r.pos
    count = r.integer()
    require(0 < count <= 12, 'Invalid W3I player count')
    players = []
    for _ in range(count):
        slot, controller, race, fixed = r.unpack('4I')
        name = r.string()
        x, y, low, high = r.unpack('2f2I')
        players.append(dict(slot=slot, controller=controller, race=race,
                            fixed_start=fixed, name=name, x=x, y=y,
                            ally_low=low, ally_high=high))
    count = r.integer()
    require(0 < count <= 12, 'Invalid W3I force count')
    forces = []
    for _ in range(count):
        force_flags, mask = r.unpack('2I')
        forces.append(dict(flags=force_flags, players=mask, name=r.string()))
    require(r.pos < len(data), 'Missing W3I tech/random tail')
    return dict(strings=strings, flags=flags, flag_offset=flag_offset,
                room_start=room_start, room_end=r.pos, players=players, forces=forces)

