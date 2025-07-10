
from dataclasses import dataclass
from ipaddress import ip_network, IPv4Network, IPv4Address
from typing import Optional, List

_LADDER = [24, 25, 26, 27, 28, 29, 30, 30]

@dataclass(frozen =True)
class FloorSubnets:
    wired: IPv4Network
    wireless: IPv4Network

@dataclass(frozen =True)
class SubnetPlan:
    network_devices: IPv4Network
    servers: IPv4Network
    voice: IPv4Network
    security: IPv4Network
    av: Optional[IPv4Network]
    bms: Optional[IPv4Network]
    floor_pairs: List[FloorSubnets]
    leftover: List[IPv4Network]
    ladder: List[IPv4Network]


def subnetter(
    ipaddr: str,
    *,
    floors: int,
    new_prefix: int = 22,
    av: bool,
    bms: bool
) -> SubnetPlan:
    parent = ip_network(ipaddr, strict=True)

    if 24 <= parent.prefixlen:
        raise ValueError("Parent  block must be larger than /24")
    
    if new_prefix <= parent.prefixlen or new_prefix >= 32:
         raise ValueError(f"child prefix must be between {parent.prefixlen+1} and /31")

    must_haves = 4
    optionals = int(av) + int(bms)
    needed_24s = must_haves + optionals
    gen24 = parent.subnets(new_prefix=24)
    reserved_24s: List[IPv4Network] = []

    try:
        reserved_24s = [next(gen24) for _ in range(needed_24s)]
    except StopIteration:
        raise ValueError("parent block is too small for the requested /24s")
    
    nd, srv, voip, sec, *opt = reserved_24s
    av_net = opt[0] if av else None
    bms_net = opt[1] if bms else None

    child_pool = [
        net
        for net in parent.subnets(new_prefix=new_prefix)
        if not any(net.overlaps(r) for r in reserved_24s)
    ]

    needed_22s = floors * 2
    if len(child_pool) < needed_22s:
        raise ValueError(
            f"need {needed_22s} /{new_prefix} blocks for {floors} floor(s); "
            f"only {len(child_pool)} available"
        )
    floor_pairs: List[FloorSubnets] = []
    
    for i in range(0, needed_22s, 2):
        floor_pairs.append(
            FloorSubnets(wired=child_pool[i], wireless=child_pool[i+1])
        )

    leftover = child_pool[needed_22s:]
    tail_size = 512
    gap_end   = parent.broadcast_address
    gap_start = gap_end - (tail_size - 1)
    ladder: List[IPv4Network] = []

    if gap_start <= gap_end:
        try: 
            ladder = ladder_subnets(start=gap_start, end=gap_end)
        except ValueError as exc:
            raise RuntimeError(f"ladder carving failed: {exc}") from exc

    return SubnetPlan(
        network_devices= nd,
        servers= srv,
        voice=voip,
        security=sec,
        av=av_net,
        bms=bms_net,
        floor_pairs = floor_pairs,
        leftover= leftover,
        ladder=ladder
    )

def ladder_subnets(start:IPv4Address, end:IPv4Address) -> List[IPv4Network]:
    needed_hosts= 512
    if int(end) - int(start) + 1 != needed_hosts:
        raise ValueError(
            f"pattern needs exactly {needed_hosts} addresses"
            f"availiable addresses are {int(end)-int(start)+1}"
        )
    nets: List[IPv4Network] = []
    cur = start
    for p in _LADDER:
        net = ip_network(f"{cur}/{p}", strict=False)
        if net.network_address !=cur:
            raise ValueError(f"{cur} is not aligned for a /{p}")
        if net.broadcast_address > end: 
            raise ValueError (f"ladder overruns range")
        nets.append(net)
        cur = net.broadcast_address+1
    return nets



if __name__ == "__main__":
    office = "10.58.64.0/19"
    plan = subnetter(office, floors=2, av=False, bms=False)
    print(f"Sub-nets carved from {office}: ")
    print(f"Network Devices : {plan.network_devices.with_prefixlen}")
    print(f"Servers  : {plan.servers.with_prefixlen}")
    print(f"Voice : {plan.voice.with_prefixlen}")
    print(f"Security : {plan.security.with_prefixlen}")
    if plan.av:
        print(f" AV  : {plan.av.with_prefixlen}")
    if plan.bms:
        print(f" BMS : {plan.bms.with_prefixlen}")
    for index, floor in enumerate(plan.floor_pairs, start=1):
        print(f"Floor {index} wired : {floor.wired.with_prefixlen}")
        print(f"Floor {index} wireless : {floor.wireless.with_prefixlen}")
    if plan.leftover:
        print("Room for Growth /22s:")
        for net in plan.leftover:
            print(f"{net.with_prefixlen}")
    # print(f"{plan.ladder}")
    if plan.ladder:
        print("ladder of unused smaller ranges:")
        for net in plan.ladder:
            print(f"{net.with_prefixlen}")
        print(f"Radius : {plan.ladder[-1].with_prefixlen})")



