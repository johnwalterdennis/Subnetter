
from ipaddress import IPv4Network
from fastapi import FastAPI, HTTPException 
from pydantic import BaseModel
from typing import List, Optional
from subnetter import * 
from fastapi.staticfiles import StaticFiles
from pathlib import Path

app = FastAPI(title="Subnet Planner") 
static_dir = Path(__file__).parent / "static"

app.mount(
    "/static",                    
    StaticFiles(directory=static_dir, html=True),
    name="static",
) 
class SubnetRequest(BaseModel):
    cidr: str
    floors: int 
    av: bool = True
    bms: bool = False

class SubnetResponse(BaseModel):
    network_devices: str
    servers: str
    voice: str
    security: str
    av: Optional[str]
    bms: Optional[str]
    floors: List[List[str]]
    ladder: List[str]
    leftover: List[str]

def net2str(net: Optional[IPv4Network]) -> Optional[str]:
    return None if net is None else net.with_prefixlen

@app.post("/plan", response_model=SubnetResponse)
def make_plan(req: SubnetRequest):
    try:
        plan = subnetter(req.cidr, floors=req.floors, av=req.av, bms=req.bms)
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err)) 
    return SubnetResponse(
        network_devices=plan.network_devices.with_prefixlen,
        servers=plan.network_devices.with_prefixlen,
        voice=plan.voice.with_prefixlen,
        security=plan.security.with_prefixlen,
        av=net2str(plan.av),
        bms=net2str(plan.bms),
        floors=[
            [f.wired.with_prefixlen, f.wireless.with_prefixlen]
            for f in plan.floor_pairs
        ],
        leftover=[n.with_prefixlen for n in plan.leftover],
        ladder= [n.with_prefixlen for n in plan.ladder]
    )