"""Read process-owned UDP listeners and choose a local discovery destination."""
import ctypes
import socket


def udp_ports(pid):
    if not isinstance(pid,int) or isinstance(pid,bool) or pid<=0:
        raise ValueError('Positive owned game PID required')
    dll=ctypes.WinDLL('iphlpapi')
    call=dll.GetExtendedUdpTable
    call.argtypes=[ctypes.c_void_p,ctypes.POINTER(ctypes.c_uint32),ctypes.c_int,ctypes.c_uint32,ctypes.c_int,ctypes.c_uint32]
    call.restype=ctypes.c_uint32
    size=ctypes.c_uint32(0)
    status=call(None,ctypes.byref(size),False,2,1,0)
    if status not in (0,122):raise OSError(status,'Cannot size UDP owner table')
    for _ in range(3):
        buf=ctypes.create_string_buffer(size.value)
        status=call(buf,ctypes.byref(size),False,2,1,0)
        if status==122:continue
        if status:raise OSError(status,'Cannot read UDP owner table')
        count=ctypes.c_uint32.from_buffer(buf).value
        if 4+12*count>len(buf):raise RuntimeError('Malformed UDP owner table')
        ports=[]
        for i in range(count):
            row=(ctypes.c_uint32*3).from_buffer(buf,4+12*i)
            if row[2]==pid:ports.append(socket.ntohs(row[1]&65535))
        return sorted(set(ports))
    raise RuntimeError('UDP owner table kept changing; retry observation')


def replay_destination(ports, prior_ports):
    # Broadcast only on loopback when native clients share the discovery port.
    # Caller must validate owned GAMEINFO before sending any payload.
    return '127.255.255.255' if set(ports).intersection(prior_ports) else '127.0.0.1'
